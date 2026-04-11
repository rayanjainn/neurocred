"""
Airavat — FastAPI entry point

Tiers 1–3 are exposed via REST endpoints for:
  - /ingest/trigger   — run the synthetic data generator + Redis producer
  - /classify/status  — check classifier worker stream lag
  - /features/{user_id} — get latest BehaviouralFeatureVector for a user
  - /windows/{user_id}  — get sliding-window aggregates for a user
  - /cohorts/build    — trigger peer cohort Parquet rebuild
  - /health           — liveness check

Tier 4 + Tier 8 Digital Twin endpoints:
  - GET  /twin/{user_id}              — get current Digital Twin state
  - GET  /twin/{user_id}/history      — get twin version history
  - POST /twin/{user_id}/update       — update twin from a feature vector
  - POST /twin/{user_id}/chat         — chat with the avatar
  - GET  /twin/{user_id}/report       — get end-of-day report
  - POST /twin/bootstrap              — bootstrap all twins from features Parquet
  - GET  /twin/{user_id}/audit        — get audit trail
  - POST /audit/replay                — event-sourced time-travel replay

Tier 7 — Cognitive Credit Engine endpoints:
  - POST /credit/score                — submit async credit scoring request
  - GET  /credit/score/{task_id}      — poll scoring result
  - GET  /credit/score/{task_id}/stream — SSE real-time progress
  - GET  /credit/{user_id}/status     — latest credit state from 24h recalibration cache
  - POST /credit/audit/replay         — point-in-time feature replay (RBI compliance)
  - GET  /credit/health               — model load status + queue depth
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import redis.asyncio as aioredis
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from src.features.schemas import BehaviouralFeatureVector


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    print("[airavat] startup — connecting to Redis")
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis_client.ping()
        print("[airavat] Redis connected")
    except Exception as exc:
        print(f"[airavat] Redis ping failed: {exc}")
    app.state.redis = redis_client
    yield
    print("[airavat] shutdown — closing Redis")
    await redis_client.aclose()


app = FastAPI(
    title="Airavat — Financial Digital Twin Engine",
    version="0.1.0",
    description="Tiers 1–3: Signal Ingestion, Semantic Classifier, Behavioural Feature Engine",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict[str, str]:
    redis: aioredis.Redis = app.state.redis
    try:
        await redis.ping()
        redis_status = "ok"
    except Exception:
        redis_status = "down"
    return {"status": "ok", "redis": redis_status}


# ── Tier 1: ingestion trigger ─────────────────────────────────────────────────

@app.post("/ingest/trigger")
async def trigger_ingestion(
    n_profiles: int = 50,
    history_months: int = 12,
) -> dict[str, Any]:
    """
    Run the synthetic data generator and publish events to Redis Streams.
    This is an async background job — returns immediately after spawning.
    Use /ingest/status to check stream lengths.
    """
    import asyncio
    from src.ingestion.redis_producer import produce

    # Run in background so the HTTP request doesn't time out
    asyncio.create_task(produce(n_profiles, history_months))
    return {
        "status": "started",
        "n_profiles": n_profiles,
        "history_months": history_months,
        "stream": "stream:raw_ingestion",
    }


@app.get("/ingest/status")
async def ingest_status() -> dict[str, Any]:
    """Return stream lengths for all Tier 1 streams."""
    redis: aioredis.Redis = app.state.redis
    streams = {
        "raw_ingestion": "stream:raw_ingestion",
        "bank": settings.stream_bank,
        "upi": settings.stream_upi,
        "sms": settings.stream_sms,
        "emi": settings.stream_emi,
        "open_banking": settings.stream_ob,
        "voice": settings.stream_voice,
    }
    result: dict[str, Any] = {}
    for name, stream_key in streams.items():
        try:
            length = await redis.xlen(stream_key)
            result[name] = length
        except Exception:
            result[name] = 0
    return result


# ── Tier 2: classifier status ─────────────────────────────────────────────────

@app.get("/classify/status")
async def classifier_status() -> dict[str, Any]:
    """Check typed event stream length and classifier consumer group lag."""
    redis: aioredis.Redis = app.state.redis
    try:
        typed_len = await redis.xlen(settings.stream_typed)
        raw_len = await redis.xlen("stream:raw_ingestion")
        lag = raw_len - typed_len
    except Exception:
        typed_len = 0
        raw_len = 0
        lag = 0

    return {
        "raw_stream_length": raw_len,
        "typed_stream_length": typed_len,
        "estimated_lag": max(lag, 0),
    }


# ── Tier 3: feature retrieval ─────────────────────────────────────────────────

@app.get("/features/{user_id}", response_model=BehaviouralFeatureVector)
async def get_features(user_id: str) -> BehaviouralFeatureVector:
    """
    Retrieve the latest computed BehaviouralFeatureVector for a user.
    Features are updated on every new typed event from Tier 2.
    """
    redis: aioredis.Redis = app.state.redis
    raw = await redis.get(f"twin:features:{user_id}")
    if not raw:
        raise HTTPException(
            status_code=404,
            detail=f"No feature vector found for user_id={user_id}. "
                   "Ensure ingestion + classifier have run.",
        )
    data = json.loads(raw)

    # coerce types
    bool_fields = {"salary_day_spike_flag", "anomaly_flag"}
    int_fields = {"subscription_count_30d", "emi_payment_count_90d",
                  "merchant_category_shift_count", "city_tier", "months_active_gst"}
    float_fields = {
        "gst_30d_value", "ewb_30d_value", "gst_filing_compliance_rate",
        "upi_p2m_ratio_30d", "gst_upi_receivables_gap", "hsn_entropy_90d",
        "statutory_payment_regularity_score"
    }
    float_fields.update({k for k in data if k not in bool_fields and k not in int_fields
                         and k not in ("user_id", "computed_at", "income_band", "age_group", "gstin")})

    for f in bool_fields:
        if f in data:
            data[f] = data[f] in ("1", "True", "true", True)
    for f in int_fields:
        if f in data and data[f]:
            try:
                data[f] = int(float(data[f]))
            except (ValueError, TypeError):
                data[f] = 0
    for f in float_fields:
        if f in data and data[f] != "":
            try:
                data[f] = float(data[f])
            except (ValueError, TypeError):
                data[f] = 0.0

    return BehaviouralFeatureVector.model_validate(data)


@app.get("/windows/{user_id}")
async def get_windows(user_id: str) -> dict[str, Any]:
    """
    Retrieve 7d / 30d / 90d sliding-window aggregates for a user.
    Updated by the Tier 2 classifier on every event.
    """
    redis: aioredis.Redis = app.state.redis
    raw = await redis.get(f"twin:windows:{user_id}")
    if not raw:
        raise HTTPException(
            status_code=404,
            detail=f"No window data for user_id={user_id}.",
        )
    return json.loads(raw)


@app.get("/users")
async def list_users(limit: int = 100) -> dict[str, Any]:
    """List user IDs that have feature vectors computed."""
    redis: aioredis.Redis = app.state.redis
    cursor = 0
    keys: list[str] = []
    while True:
        cursor, batch = await redis.scan(
            cursor, match="twin:features:*", count=200
        )
        keys.extend(batch)
        if cursor == 0 or len(keys) >= limit:
            break
    user_ids = [k.removeprefix("twin:features:") for k in keys[:limit]]
    return {"count": len(user_ids), "user_ids": user_ids}


# ── peer cohort rebuild ───────────────────────────────────────────────────────

@app.post("/cohorts/build")
async def build_cohorts() -> dict[str, Any]:
    """Rebuild peer cohort statistics from all current feature vectors."""
    from src.features.peer_cohort import build_peer_cohorts
    n = await build_peer_cohorts()
    return {"status": "ok", "cohorts_written": n}


# ── Tier 4: Digital Twin endpoints ───────────────────────────────────────────

@app.get("/twin/{user_id}")
async def get_twin(user_id: str) -> dict[str, Any]:
    """
    Get current Digital Twin state for a user.
    Includes risk score, liquidity health, financial DNA, avatar state, CIBIL-like score.
    """
    from src.twin.twin_service import TwinService
    svc = TwinService(app.state.redis)
    twin = await svc.get(user_id)
    if twin is None:
        raise HTTPException(
            status_code=404,
            detail=f"No Digital Twin found for user_id={user_id}. Run /twin/bootstrap first.",
        )
    data = twin.model_dump()
    data["cibil_like_score"] = twin.cibil_like_score()
    return data


@app.get("/twin/{user_id}/history")
async def get_twin_history(user_id: str, limit: int = 20) -> dict[str, Any]:
    """Get the version history of a Digital Twin (newest first)."""
    from src.twin.twin_service import TwinService
    svc = TwinService(app.state.redis)
    history = await svc.get_history(user_id, limit=limit)
    return {"user_id": user_id, "count": len(history), "history": history}


@app.post("/twin/{user_id}/update")
async def update_twin(user_id: str) -> dict[str, Any]:
    """
    Trigger a Digital Twin update from the latest feature vector stored in Redis.
    Fetches twin:features:{user_id}, recomputes derived metrics, saves new version.
    """
    from src.twin.twin_service import TwinService
    redis: aioredis.Redis = app.state.redis
    raw = await redis.get(f"twin:features:{user_id}")
    if not raw:
        raise HTTPException(
            status_code=404,
            detail=f"No feature vector found for user_id={user_id}.",
        )
    data = json.loads(raw)

    # Coerce types (same logic as /features/{user_id})
    bool_fields = {"salary_day_spike_flag", "anomaly_flag"}
    int_fields = {"subscription_count_30d", "emi_payment_count_90d",
                  "merchant_category_shift_count", "city_tier", "months_active_gst"}
    for f in bool_fields:
        if f in data:
            data[f] = data[f] in ("1", "True", "true", True)
    for f in int_fields:
        if f in data and data[f]:
            try:
                data[f] = int(float(data[f]))
            except (ValueError, TypeError):
                data[f] = 0

    fv = BehaviouralFeatureVector.model_validate(data)
    svc = TwinService(app.state.redis)
    twin = await svc.update_from_features(fv)
    return {
        "status": "updated",
        "user_id": twin.user_id,
        "version": twin.version,
        "risk_score": twin.risk_score,
        "liquidity_health": twin.liquidity_health,
        "cibil_like_score": twin.cibil_like_score(),
        "persona": twin.persona,
        "avatar_expression": twin.avatar_state.expression,
    }


@app.post("/twin/{user_id}/chat")
async def chat_with_twin(user_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """
    Send a message to the Digital Twin avatar and get a response.

    Request body: {"message": "What does my financial future look like?"}
    Response: {role, content, intent, avatar_expression, cibil_score, ts}
    """
    from src.intervention.dialogue_manager import DialogueManager
    from src.twin.twin_service import TwinService

    message: str = body.get("message", "")
    if not message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")

    svc = TwinService(app.state.redis)
    twin = await svc.get(user_id)
    if twin is None:
        raise HTTPException(
            status_code=404,
            detail=f"No Digital Twin for user_id={user_id}. Run /twin/bootstrap first.",
        )

    dm = DialogueManager()
    response = dm.chat(message, twin)
    return response


@app.get("/twin/{user_id}/report")
async def get_twin_report(
    user_id: str,
    report_type: str = "daily_summary",
) -> dict[str, Any]:
    """
    Generate an end-of-day or weekly report for the user's Digital Twin.
    Returns structured report with key insights, suggested actions, and CIBIL-like score.
    """
    from src.intervention.report_generator import generate_report
    from src.twin.twin_service import TwinService

    svc = TwinService(app.state.redis)
    twin = await svc.get(user_id)
    if twin is None:
        raise HTTPException(
            status_code=404,
            detail=f"No Digital Twin for user_id={user_id}.",
        )

    rtype = report_type if report_type in ("daily_summary", "weekly_summary") else "daily_summary"
    report = generate_report(twin, report_type=rtype)  # type: ignore[arg-type]
    return report


@app.get("/twin/{user_id}/triggers")
async def evaluate_twin_triggers(user_id: str) -> dict[str, Any]:
    """
    Evaluate and return all fired intervention triggers for a user's twin state.
    Useful for debugging the Tier 8 trigger engine.
    """
    from src.intervention.trigger_engine import evaluate_triggers
    from src.twin.twin_service import TwinService

    svc = TwinService(app.state.redis)
    twin = await svc.get(user_id)
    if twin is None:
        raise HTTPException(status_code=404, detail=f"No twin for user_id={user_id}.")

    fired = evaluate_triggers(twin)
    return {
        "user_id": user_id,
        "twin_version": twin.version,
        "fired_count": len(fired),
        "triggers": [
            {
                "type": t.trigger_type,
                "priority": t.priority,
                "urgency": t.urgency,
                "reason": t.reason,
                "channels": t.channels,
                "suggested_actions": t.suggested_actions,
            }
            for t in fired
        ],
    }


@app.post("/twin/bootstrap")
async def bootstrap_twins() -> dict[str, Any]:
    """
    One-time offline bootstrap: read all features Parquet partitions,
    create/update Digital Twins for every user, save to Redis.
    """
    from src.twin.twin_service import TwinService
    svc = TwinService(app.state.redis)
    count = await svc.bootstrap_from_features_parquet()
    return {"status": "ok", "twins_bootstrapped": count}


# ── Tier 8: Audit / replay endpoint ──────────────────────────────────────────

@app.get("/twin/{user_id}/audit")
async def get_audit_trail(user_id: str, limit: int = 50) -> dict[str, Any]:
    """
    Retrieve the immutable audit trail for a user (RBI event-sourced replay).
    Returns all twin updates, intervention triggers, notifications, and chat sessions.
    """
    from src.intervention.audit_logger import AuditLogger
    auditor = AuditLogger(app.state.redis)
    records = await auditor.get_user_audit(user_id, limit=limit)
    return {"user_id": user_id, "count": len(records), "records": records}


@app.post("/audit/replay")
async def audit_replay(body: dict[str, Any]) -> dict[str, Any]:
    """
    Event-sourced time-travel replay (tier4_tier8.md §8).
    Returns all audit events for a user since a given timestamp.

    Request body: {"user_id": "u_0001", "since": "2026-04-01T00:00:00"}
    """
    from datetime import datetime
    from src.intervention.audit_logger import AuditLogger

    user_id: str = body.get("user_id", "")
    since_str: str = body.get("since", "")
    if not user_id or not since_str:
        raise HTTPException(status_code=400, detail="user_id and since are required")
    try:
        since_ts = datetime.fromisoformat(since_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="since must be ISO 8601 datetime")

    auditor = AuditLogger(app.state.redis)
    records = await auditor.replay_since(user_id, since_ts)
    return {
        "user_id": user_id,
        "since": since_str,
        "event_count": len(records),
        "events": records,
    }


# ── Tier 7: Cognitive Credit Engine endpoints ─────────────────────────────────

@app.post("/credit/score")
async def submit_credit_score(body: dict[str, Any]) -> dict[str, Any]:
    """
    Submit an async credit scoring request for a retail consumer.

    Request body: {"user_id": "u_0001"}
    Response: {"task_id": "...", "status": "pending"}

    The worker picks this up from stream:credit_score_requests and writes
    the result to score:{task_id}. Poll /credit/score/{task_id} for the result.
    """
    import uuid
    redis: aioredis.Redis = app.state.redis
    user_id: str = body.get("user_id", "")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    task_id = str(uuid.uuid4())
    await redis.hset(f"score:{task_id}", mapping={"status": "pending", "user_id": user_id})
    await redis.xadd(
        "stream:credit_score_requests",
        {"task_id": task_id, "user_id": user_id},
    )
    return {"task_id": task_id, "status": "pending", "user_id": user_id}


@app.get("/credit/score/{task_id}")
async def get_credit_score(task_id: str) -> dict[str, Any]:
    """
    Poll the result of a credit scoring request.

    Returns the full scoring payload when status=complete, including:
    credit_score (300–900), risk_band, recommended_personal_loan_amount,
    annual_percentage_rate, top-5 SHAP features, machine-readable rule_trace,
    behavioural_override trace.
    """
    redis: aioredis.Redis = app.state.redis
    result = await redis.hgetall(f"score:{task_id}")
    if not result:
        raise HTTPException(status_code=404, detail=f"task_id={task_id} not found")

    # Parse JSON sub-fields
    for field in ("shap_top5", "shap_waterfall", "rule_trace", "behavioural_override"):
        if field in result:
            try:
                result[field] = json.loads(result[field])
            except (json.JSONDecodeError, TypeError):
                pass

    return result


@app.get("/credit/score/{task_id}/stream")
async def stream_credit_score(task_id: str):
    """
    Server-Sent Events stream for real-time credit scoring progress.
    Subscribe to updates:{task_id} Redis pub/sub and forward to client.
    """
    from fastapi.responses import StreamingResponse

    redis: aioredis.Redis = app.state.redis

    async def event_generator():
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"updates:{task_id}")
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    yield f"data: {data}\n\n"
                    try:
                        parsed = json.loads(data)
                        if parsed.get("status") in ("complete", "failed"):
                            break
                    except (json.JSONDecodeError, TypeError):
                        pass
        finally:
            await pubsub.unsubscribe(f"updates:{task_id}")
            await pubsub.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/credit/{user_id}/status")
async def get_credit_status(user_id: str) -> dict[str, Any]:
    """
    Return the latest credit state for a user from the 24h recalibration cache.
    Includes credit_score, risk_band, recommended_personal_loan_amount, refreshed_at.
    """
    redis: aioredis.Redis = app.state.redis
    result = await redis.hgetall(f"credit:user:{user_id}")
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No credit record for user_id={user_id}. "
                   "Submit a /credit/score request first.",
        )
    return {"user_id": user_id, **result}


@app.post("/credit/audit/replay")
async def credit_audit_replay(body: dict[str, Any]) -> dict[str, Any]:
    """
    Point-in-time feature replay for RBI compliance.
    Loads the BehaviouralFeatureVector from parquet cache and re-scores
    as it would have been at target_timestamp.

    Request body: {"user_id": "u_0001", "target_timestamp": "2026-03-01T00:00:00"}

    Note: full event-sourced replay requires the raw Parquet history.
    This endpoint returns the cached feature state closest to target_timestamp.
    """
    from datetime import datetime

    user_id: str        = body.get("user_id", "")
    ts_str: str         = body.get("target_timestamp", "")
    if not user_id or not ts_str:
        raise HTTPException(status_code=400, detail="user_id and target_timestamp required")
    try:
        target_ts = datetime.fromisoformat(ts_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="target_timestamp must be ISO 8601")

    from pathlib import Path
    import polars as pl
    from src.features.schemas import BehaviouralFeatureVector as BFV
    from src.credit.credit_scorer import CreditScorer

    # Load feature parquet
    cache = Path(settings.features_path) / f"user_id={user_id}" / "features.parquet"
    if not cache.exists():
        raise HTTPException(status_code=404, detail=f"No feature cache for user_id={user_id}")

    df = pl.read_parquet(cache)
    if df.height == 0:
        raise HTTPException(status_code=404, detail="Feature cache is empty")

    row = df.row(0, named=True)
    row["user_id"]     = user_id
    row["computed_at"] = row.get("computed_at", target_ts)
    try:
        fv = BFV(**{k: v for k, v in row.items() if k in BFV.model_fields})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Feature parse error: {exc}")

    try:
        scorer = CreditScorer("data/models")
        result = scorer.score(fv)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Scorer unavailable: {exc}")

    return {
        "user_id":          user_id,
        "target_timestamp": ts_str,
        "replayed_at":      target_ts.isoformat(),
        "credit_score":     result["credit_score"],
        "risk_band":        result["risk_band"],
        "probability_of_default": result["probability_of_default"],
        "rule_trace":       result["rule_trace"],
        "note":             "feature state from parquet cache — raw event replay requires full history",
    }


@app.get("/credit/health")
async def credit_health() -> dict[str, Any]:
    """
    Check Tier 7 model load status and scoring queue depth.
    """
    from pathlib import Path
    redis: aioredis.Redis = app.state.redis

    model_dir = Path("data/models")
    full_ok   = (model_dir / "xgb_digital_twin.ubj").exists()
    income_ok = (model_dir / "xgb_digital_twin_income_heavy.ubj").exists()

    try:
        queue_depth = await redis.xlen("stream:credit_score_requests")
    except Exception:
        queue_depth = -1

    try:
        active_users = await redis.scard("credit:active")
    except Exception:
        active_users = -1

    return {
        "models": {
            "xgb_digital_twin":              "ok" if full_ok   else "missing",
            "xgb_digital_twin_income_heavy": "ok" if income_ok else "missing",
        },
        "queue_depth":  queue_depth,
        "active_users": active_users,
        "status":       "ok" if (full_ok and income_ok) else "degraded",
    }


if __name__ == "__main__":
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )
