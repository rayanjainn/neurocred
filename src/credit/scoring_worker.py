"""
Tier 7 — Cognitive Credit Engine: Async Scoring Saga Worker

Consumes stream:credit_score_requests via XREADGROUP.
Full pipeline per request:
  1. Load BehaviouralFeatureVector from Tier 3 parquet cache
  2. Auto-route to full vs income-heavy model (data_completeness_score < 0.7)
  3. Read Digital Twin risk_history for trajectory delta (behavioural override)
  4. Score via CreditScorer (EL sizing + rule trace)
  5. Explain via CreditExplainer (SHAP top-5 + waterfall)
  6. Write result hash score:{task_id}
  7. Register user in credit:active for 24h recalibration sweep
  8. Publish progress on updates:{task_id} pubsub

Run standalone:
  python -m src.credit.scoring_worker
"""

from __future__ import annotations

import asyncio
import json
import socket
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import redis.asyncio as aioredis

from config.settings import settings
from src.credit.credit_scorer import CreditScorer
from src.features.schemas import BehaviouralFeatureVector

CONSUMER_GROUP  = "cg_credit_worker"
CONSUMER_NAME   = f"credit-worker-{socket.gethostname()}"
BLOCK_MS        = 5_000
MAX_RETRY_SLEEP = 5.0
STREAM_REQUESTS = "stream:credit_score_requests"
ACTIVE_KEY      = "credit:active"
CREDIT_KEY      = "credit:user:{uid}"


# ── feature resolution ────────────────────────────────────────────────────────

def _load_fv(user_id: str) -> BehaviouralFeatureVector | None:
    """Load BehaviouralFeatureVector from Tier 3 parquet cache."""
    path = Path(settings.features_path) / f"user_id={user_id}" / "features.parquet"
    if not path.exists():
        return None
    df = pl.read_parquet(path)
    if df.height == 0:
        return None
    row = df.row(0, named=True)
    row["user_id"]     = user_id
    row["computed_at"] = row.get("computed_at", datetime.now(timezone.utc))
    try:
        return BehaviouralFeatureVector(**{
            k: v for k, v in row.items()
            if k in BehaviouralFeatureVector.model_fields
        })
    except Exception:
        return None


def _load_demo_fv(user_id: str) -> BehaviouralFeatureVector | None:
    """Deterministic demo fallback — pick any cached user by hash."""
    import random
    cache = Path(settings.features_path)
    existing = sorted(cache.glob("user_id=*/features.parquet"))
    if not existing:
        return None
    chosen = random.Random(user_id).choice(existing)
    df = pl.read_parquet(chosen)
    if df.height == 0:
        return None
    row = df.row(0, named=True)
    row["user_id"]     = user_id
    row["computed_at"] = row.get("computed_at", datetime.now(timezone.utc))
    print(f"[scoring_worker] demo fallback for {user_id}")
    try:
        return BehaviouralFeatureVector(**{
            k: v for k, v in row.items()
            if k in BehaviouralFeatureVector.model_fields
        })
    except Exception:
        return None


def _resolve_fv(user_id: str) -> BehaviouralFeatureVector:
    fv = _load_fv(user_id) or _load_demo_fv(user_id)
    if fv is None:
        raise RuntimeError(f"no feature data for user {user_id}")
    return fv


def _get_twin_delta(user_id: str) -> float:
    """
    Read Digital Twin risk_history from Redis synchronously.
    Returns positive delta if risk is improving (decreasing).
    """
    import redis as sync_redis
    try:
        r = sync_redis.from_url(settings.redis_url, decode_responses=True)
        raw = r.get(f"twin:{user_id}")
        r.close()
        if raw is None:
            return 0.0
        twin = json.loads(raw)
        history = twin.get("risk_history", [])
        if len(history) >= 2:
            # positive when newest risk < oldest risk (improvement)
            return float(max(history[-1] - history[0], 0.0))
    except Exception:
        pass
    return 0.0


# ── saga ──────────────────────────────────────────────────────────────────────

async def run_scoring_saga(
    redis: aioredis.Redis,
    task_id: str,
    user_id: str,
    scorer: CreditScorer,
    explainer,   # CreditExplainer | None
) -> None:
    await redis.hset(f"score:{task_id}", "status", "processing")
    await redis.publish(
        f"updates:{task_id}",
        json.dumps({"status": "processing", "step": "starting"}),
    )

    try:
        loop = asyncio.get_running_loop()

        # 1. features
        await redis.publish(f"updates:{task_id}", json.dumps({"step": "resolving features"}))
        fv = await loop.run_in_executor(None, _resolve_fv, user_id)

        # 2. twin trajectory delta
        twin_delta = await loop.run_in_executor(None, _get_twin_delta, user_id)

        # 3. model routing
        use_income = fv.data_completeness_score < 0.7
        model_name = "income_heavy" if use_income else "full"
        await redis.publish(
            f"updates:{task_id}",
            json.dumps({"step": f"scoring ({model_name})"}),
        )

        # 4. score
        result = await loop.run_in_executor(
            None, scorer.score, fv, use_income, twin_delta
        )

        # 5. SHAP explanation
        top5: list[dict] = []
        waterfall: dict = {}
        if explainer is not None:
            await redis.publish(f"updates:{task_id}", json.dumps({"step": "shap"}))
            explain = await loop.run_in_executor(
                None,
                explainer.explain_single,
                fv.model_dump(),
                explainer.feature_columns,
                use_income,
            )
            top5      = explain["top_5_features"]
            waterfall = explain["waterfall_data"]

        override = result["behavioural_override"]

        # 6. write result
        await redis.hset(
            f"score:{task_id}",
            mapping={
                "status":                            "complete",
                "user_id":                           user_id,
                "credit_score":                      str(result["credit_score"]),
                "risk_band":                         result["risk_band"],
                "probability_of_default":            str(result["probability_of_default"]),
                "recommended_personal_loan_amount":  str(result["recommended_personal_loan_amount"]),
                "recommended_tenure_months":         str(result["recommended_tenure_months"]),
                "annual_percentage_rate":            str(result["annual_percentage_rate"]),
                "cgtmse_eligible":                   "true" if result["cgtmse_eligible"] else "false",
                "model_used":                        result["model_used"],
                "shap_top5":                         json.dumps(top5),
                "shap_waterfall":                    json.dumps(waterfall),
                "rule_trace":                        json.dumps(result["rule_trace"]),
                "behavioural_override":              json.dumps(override.model_dump()),
                "score_freshness":                   datetime.now(timezone.utc).isoformat(),
            },
        )

        # 7. register in active set + per-user credit hash (for recalibration)
        await redis.sadd(ACTIVE_KEY, user_id)
        await redis.hset(
            CREDIT_KEY.format(uid=user_id),
            mapping={
                "credit_score":                     str(result["credit_score"]),
                "risk_band":                        result["risk_band"],
                "recommended_personal_loan_amount": str(result["recommended_personal_loan_amount"]),
                "daily_avg_throughput_30d":         str(fv.daily_avg_throughput_30d),
                "shap_top5":                         json.dumps(top5),
                "shap_waterfall":                    json.dumps(waterfall),
                "refreshed_at":                     datetime.now(timezone.utc).isoformat(),
            },
        )

        print(f"[scoring_worker] complete task={task_id} user={user_id} score={result['credit_score']}")
        await redis.publish(f"updates:{task_id}", json.dumps({"status": "complete"}))

    except Exception as exc:
        print(f"[scoring_worker] failed task={task_id}: {exc}")
        await redis.hset(
            f"score:{task_id}",
            mapping={"status": "failed", "error": str(exc)},
        )
        await redis.publish(
            f"updates:{task_id}",
            json.dumps({"status": "failed", "error": str(exc)}),
        )


# ── consumer loop ─────────────────────────────────────────────────────────────

async def _ensure_group(redis: aioredis.Redis) -> None:
    try:
        await redis.xgroup_create(STREAM_REQUESTS, CONSUMER_GROUP, id="0", mkstream=True)
    except Exception as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def main() -> None:
    print(f"[scoring_worker] starting consumer={CONSUMER_NAME}")
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    await _ensure_group(redis)

    loop = asyncio.get_event_loop()
    scorer: CreditScorer | None = None
    explainer = None

    try:
        scorer = await loop.run_in_executor(None, CreditScorer, "data/models")
        from src.credit.shap_explainer import CreditExplainer
        explainer = await loop.run_in_executor(None, CreditExplainer, scorer)
    except Exception as exc:
        print(f"[scoring_worker] model load failed: {exc}")
        if scorer is None:
            await redis.aclose()
            return

    print("[scoring_worker] ready — consuming stream:credit_score_requests")

    while True:
        try:
            result = await redis.xreadgroup(
                groupname=CONSUMER_GROUP,
                consumername=CONSUMER_NAME,
                streams={STREAM_REQUESTS: ">"},
                count=1,
                block=BLOCK_MS,
            )
            if not result:
                continue
            for _, messages in result:
                for msg_id, fields in messages:
                    task_id = fields.get("task_id", "")
                    user_id = fields.get("user_id", "")
                    if not task_id or not user_id:
                        await redis.xack(STREAM_REQUESTS, CONSUMER_GROUP, msg_id)
                        continue
                    await run_scoring_saga(redis, task_id, user_id, scorer, explainer)
                    await redis.xack(STREAM_REQUESTS, CONSUMER_GROUP, msg_id)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            print(f"[scoring_worker] loop error: {exc}")
            await asyncio.sleep(MAX_RETRY_SLEEP)

    await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
