"""
Tier 3 — Peer Cohort Builder

Generates anonymised cohort statistics from all user feature vectors
stored in Redis (twin:features:*) and saves them as a Parquet file
at data/features/peer_cohorts.parquet.

Segmentation: income_band × city_tier × age_group
Statistics computed per cohort: mean and std of 5 key features.

Run once after Tier 3 has processed enough events (~1 full generation cycle).
Re-run periodically to refresh cohort baselines.
"""

from __future__ import annotations

import asyncio
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

import polars as pl
import redis.asyncio as aioredis

from config.settings import settings

OUTPUT_PATH = Path(settings.peer_cohort_path)


def _cohort_key(income_band: str, city_tier: str, age_group: str) -> str:
    return f"{income_band}_{city_tier}_{age_group}"


async def build_peer_cohorts() -> int:
    """
    Scan all twin:features:* keys in Redis, aggregate per cohort,
    and write Parquet file. Returns number of cohorts written.
    """
    client = aioredis.from_url(settings.redis_url, decode_responses=True)

    # scan keys
    keys: list[str] = []
    cursor = 0
    while True:
        cursor, batch = await client.scan(cursor, match="twin:features:*", count=100)
        keys.extend(batch)
        if cursor == 0:
            break

    if not keys:
        print("[peer-cohort] no feature vectors found in Redis")
        await client.aclose()
        return 0

    # gather all feature vectors
    pipe = client.pipeline(transaction=False)
    for k in keys:
        pipe.get(k)
    raw_values = await pipe.execute()
    await client.aclose()

    # group by cohort
    cohort_data: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for raw in raw_values:
        if not raw:
            continue
        try:
            fv: dict[str, Any] = json.loads(raw)
            ib = fv.get("income_band", "mid") or "mid"
            ct = str(fv.get("city_tier", "2") or "2")
            ag = fv.get("age_group", "26-35") or "26-35"
            key = _cohort_key(ib, ct, ag)

            for field in [
                "emi_burden_ratio", "savings_rate",
                "spending_volatility_index", "cash_buffer_days",
                "income_stability_score",
            ]:
                val_str = fv.get(field, "0") or "0"
                try:
                    cohort_data[key][field].append(float(val_str))
                except ValueError:
                    pass
        except json.JSONDecodeError:
            continue

    if not cohort_data:
        print("[peer-cohort] no valid feature vectors parsed")
        return 0

    # compute stats
    rows = []
    for cohort_key, fields in cohort_data.items():
        parts = cohort_key.split("_", 2)
        if len(parts) < 3:
            continue

        def _stats(vals: list[float]) -> tuple[float, float]:
            if not vals:
                return 0.0, 1.0
            mu = statistics.mean(vals)
            std = statistics.stdev(vals) if len(vals) > 1 else 1.0
            return round(mu, 4), round(max(std, 1e-6), 4)

        emi_mu, emi_std = _stats(fields.get("emi_burden_ratio", []))
        sav_mu, sav_std = _stats(fields.get("savings_rate", []))
        vol_mu, vol_std = _stats(fields.get("spending_volatility_index", []))
        buf_mu, buf_std = _stats(fields.get("cash_buffer_days", []))
        inc_mu, inc_std = _stats(fields.get("income_stability_score", []))

        rows.append({
            "cohort_key": cohort_key,
            "n_users": len(fields.get("emi_burden_ratio", [])),
            "mean_emi_burden": emi_mu,
            "std_emi_burden": emi_std,
            "mean_savings_rate": sav_mu,
            "std_savings_rate": sav_std,
            "mean_spending_volatility": vol_mu,
            "std_spending_volatility": vol_std,
            "mean_cash_buffer": buf_mu,
            "std_cash_buffer": buf_std,
            "mean_income_stability": inc_mu,
            "std_income_stability": inc_std,
        })

    # write Parquet
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df = pl.DataFrame(rows)
    df.write_parquet(OUTPUT_PATH)
    print(f"[peer-cohort] wrote {len(rows)} cohorts to {OUTPUT_PATH}")
    return len(rows)


if __name__ == "__main__":
    asyncio.run(build_peer_cohorts())
