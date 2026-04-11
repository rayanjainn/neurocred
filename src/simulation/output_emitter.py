"""
Tier 6 — Simulation Output Emitter

On simulation_completed:
  1. Publish `simulation_completed` event to Redis channel
  2. Update twin.predicted_risk_trajectory in Redis hash twin:{user_id}
  3. Cache fan chart at sim:fan:{user_id}:{sim_id} (Redis hash, TTL 24h)
  4. Store EWS at sim:ews:{user_id} for streaming endpoint (TTL 24h)
  5. Cache full simulation result at sim:{user_id}:{sim_id} (TTL 24h)

Twin update payload:
  {
    "predicted_risk_trajectory": [...],
    "ews_14d": 0.38,
    "regime_distribution": {"STABLE": ..., "STRESSED": ..., "CRISIS": ...},
    "recovery_plan_active": true,
    "fan_chart_cache_key": "sim:fan:..."
  }
"""

from __future__ import annotations

import json
from datetime import timedelta

import redis.asyncio as aioredis

_TTL = int(timedelta(hours=24).total_seconds())


async def emit_simulation_completed(
    redis: aioredis.Redis,
    user_id: str,
    sim_result: dict,
) -> None:
    """
    Publish simulation results to Redis and update twin state.
    Mutates sim_result["twin_update_emitted"] = True on success.
    """
    sim_id = sim_result.get("simulation_id", "unknown")

    # ── 1. Store full simulation result ──────────────────────────────────────
    cache_key = f"sim:{user_id}:{sim_id}"
    await redis.setex(cache_key, _TTL, json.dumps(sim_result))

    # ── 2. Cache fan chart ────────────────────────────────────────────────────
    fan = sim_result.get("fan_chart", {})
    fan_key = f"sim:fan:{user_id}"
    await redis.setex(fan_key, _TTL, json.dumps({
        "simulation_id": sim_id,
        "horizon_days":  fan.get("horizon_days", 90),
        "today_index":   0,
        "currency":      "INR",
        "fan_chart":     {k: v for k, v in fan.items() if k != "horizon_days"},
    }))

    # ── 3. Store EWS for streaming endpoint ──────────────────────────────────
    ews = sim_result.get("ews", {})
    ews_key = f"sim:ews:{user_id}"
    await redis.setex(ews_key, _TTL, json.dumps({
        "user_id":            user_id,
        "computed_at":        sim_result.get("timestamp", ""),
        "ews_7d":             ews.get("ews_7d"),
        "ews_14d":            ews.get("ews_14d"),
        "ews_30d":            ews.get("ews_30d"),
        "severity":           ews.get("severity"),
        "leading_indicators": [],
        "simulation_id_source": sim_id,
    }))

    # ── 4. Build twin trajectory update ──────────────────────────────────────
    # Extract median risk trajectory from fan chart P50 (normalised to [0,1])
    p50 = fan.get("p50", [])
    initial_cash = float(sim_result.get("fan_chart", {}).get("p50", [40000])[0]) or 40000.0
    if p50 and initial_cash > 0:
        # Normalise: low cash = high risk
        max_cash = max(abs(initial_cash), 1.0)
        trajectory = [
            round(max(0.0, min(1.0, 1.0 - v / max_cash)), 4)
            for v in p50[:30]   # first 30 days
        ]
    else:
        trajectory = []

    regime_dist = sim_result.get("regime_distribution_at_90d", {})

    twin_update = {
        "predicted_risk_trajectory": json.dumps(trajectory),
        "ews_14d":                   str(ews.get("ews_14d", 0)),
        "regime_distribution":       json.dumps(regime_dist),
        "recovery_plan_active":      "true" if sim_result.get("recovery_plan", {}).get("steps") else "false",
        "fan_chart_cache_key":       fan_key,
        "last_simulation_id":        sim_id,
    }
    await redis.hset(f"twin:{user_id}", mapping=twin_update)

    # ── 5. Publish simulation_completed event ─────────────────────────────────
    event = json.dumps({
        "event":         "simulation_completed",
        "user_id":       user_id,
        "simulation_id": sim_id,
        "twin_update": {
            "predicted_risk_trajectory": trajectory[:10],   # abbreviated for pub/sub
            "ews_14d":         ews.get("ews_14d"),
            "regime_distribution": regime_dist,
            "recovery_plan_active": bool(sim_result.get("recovery_plan", {}).get("steps")),
            "fan_chart_cache_key": fan_key,
        },
    })
    await redis.publish("simulation_completed", event)

    sim_result["twin_update_emitted"] = True


async def get_cached_simulation(
    redis: aioredis.Redis,
    user_id: str,
    sim_id: str,
) -> dict | None:
    """Retrieve a cached simulation result by ID."""
    raw = await redis.get(f"sim:{user_id}:{sim_id}")
    if raw is None:
        return None
    return json.loads(raw)


async def get_ews_snapshot(
    redis: aioredis.Redis,
    user_id: str,
) -> dict | None:
    """Retrieve latest EWS snapshot for streaming endpoint."""
    raw = await redis.get(f"sim:ews:{user_id}")
    if raw is None:
        return None
    return json.loads(raw)


async def get_fan_chart(
    redis: aioredis.Redis,
    user_id: str,
) -> dict | None:
    """Retrieve cached fan chart for dashboard rendering."""
    raw = await redis.get(f"sim:fan:{user_id}")
    if raw is None:
        return None
    return json.loads(raw)
