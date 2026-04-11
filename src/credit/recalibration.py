"""
Tier 7 — Cognitive Credit Engine: 24-Hour Recalibration Scheduler

Implements tier7.md §7 "Temporal State Refresh":
  - APScheduler fires every 24 hours
  - Scans all users with a credit state in Redis (credit:active set)
  - If daily_avg_throughput_30d changed ±15% → recompute score
  - Pushes new limit to Redis hash credit:user:{user_id}
  - If limit REDUCED → publishes LIMIT_REDUCED_EVENT on channel credit_events
    (Tier 8 notification engine picks this up)

Redis key layout (Tier 7):
  credit:user:{user_id}   — Hash  (latest credit state per user)
  credit:active           — Set   (all user_ids with a credit record)

Embed in FastAPI lifespan via start_scheduler() / stop_scheduler().
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
import polars as pl
import redis.asyncio as aioredis

from config.settings import settings
from src.features.schemas import BehaviouralFeatureVector

logger = logging.getLogger(__name__)

_THROUGHPUT_CHANGE_THRESHOLD = 0.15   # 15% → recalibrate
_ACTIVE_KEY = "credit:active"
_CREDIT_KEY = "credit:user:{uid}"


async def _recalibrate_one(
    redis: aioredis.Redis,
    user_id: str,
    scorer,           # CreditScorer — passed in to avoid circular import at module load
) -> None:
    key = _CREDIT_KEY.format(uid=user_id)
    existing = await redis.hgetall(key)
    if not existing:
        return

    try:
        prev_loan   = float(existing.get("recommended_personal_loan_amount", 0))
        prev_tp     = float(existing.get("daily_avg_throughput_30d", 0))

        # Load latest features from parquet cache
        cache_path = Path(settings.features_path) / f"user_id={user_id}" / "features.parquet"
        if not cache_path.exists():
            return

        df = pl.read_parquet(cache_path)
        if df.height == 0:
            return

        row = df.row(0, named=True)
        row["user_id"]     = user_id
        row["computed_at"] = row.get("computed_at", datetime.now(timezone.utc))
        fv = BehaviouralFeatureVector(**{
            k: v for k, v in row.items()
            if k in BehaviouralFeatureVector.model_fields
        })

        curr_tp = fv.daily_avg_throughput_30d

        # Skip if throughput unchanged
        if prev_tp > 0:
            change = abs(curr_tp - prev_tp) / prev_tp
            if change < _THROUGHPUT_CHANGE_THRESHOLD:
                return

        result = scorer.score(fv)
        new_loan = result["recommended_personal_loan_amount"]

        await redis.hset(key, mapping={
            "credit_score":                      str(result["credit_score"]),
            "risk_band":                         result["risk_band"],
            "probability_of_default":            str(result["probability_of_default"]),
            "recommended_personal_loan_amount":  str(new_loan),
            "daily_avg_throughput_30d":          str(curr_tp),
            "refreshed_at":                      datetime.now(timezone.utc).isoformat(),
        })

        # Emit LIMIT_REDUCED_EVENT if loan limit dropped >5%
        if prev_loan > 0 and new_loan < prev_loan * 0.95:
            event = json.dumps({
                "event_type":    "LIMIT_REDUCED_EVENT",
                "user_id":       user_id,
                "prev_loan":     prev_loan,
                "new_loan":      new_loan,
                "reduction_pct": round((prev_loan - new_loan) / prev_loan * 100, 1),
                "timestamp":     datetime.now(timezone.utc).isoformat(),
            })
            await redis.publish("credit_events", event)
            logger.info(
                "[recalibration] LIMIT_REDUCED user=%s %.0f→%.0f",
                user_id, prev_loan, new_loan,
            )
        else:
            logger.info(
                "[recalibration] updated user=%s score=%s",
                user_id, result["credit_score"],
            )

    except Exception as exc:
        logger.warning("[recalibration] failed for %s: %s", user_id, exc)
        raise


async def run_recalibration_sweep(redis: aioredis.Redis, scorer) -> None:
    """Batch sweep all active users. Called by APScheduler every 24h."""
    active = await redis.smembers(_ACTIVE_KEY)
    if not active:
        logger.info("[recalibration] no active users to sweep")
        return

    logger.info("[recalibration] sweeping %d users", len(active))
    await asyncio.gather(
        *[_recalibrate_one(redis, uid, scorer) for uid in active],
        return_exceptions=True,
    )
    logger.info("[recalibration] sweep complete")


def start_scheduler(redis_url: str, scorer) -> object | None:
    """
    Start APScheduler 24-hour recalibration job.
    Returns the scheduler instance (keep a reference so it isn't GC'd).
    """
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except ImportError:
        logger.warning("[recalibration] apscheduler not installed — 24h sweep disabled")
        return None

    scheduler = AsyncIOScheduler()

    async def _job() -> None:
        r = aioredis.from_url(redis_url, decode_responses=True)
        try:
            await run_recalibration_sweep(r, scorer)
        finally:
            await r.aclose()

    scheduler.add_job(_job, "interval", hours=24, id="credit_recalibration")
    scheduler.start()
    logger.info("[recalibration] APScheduler started — 24h sweep active")
    return scheduler


def stop_scheduler(scheduler) -> None:
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        logger.info("[recalibration] scheduler stopped")
