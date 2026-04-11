"""
Tier 4 — Twin Update Service

Core update lifecycle:

  Feature Vector → derive_metrics() → update_twin() → version++ →
  save snapshot → publish twin_updated event → return updated twin

Metric derivation follows the mathematical spec in tier4_tier8.md §3.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any, Optional

import redis.asyncio as aioredis

from src.features.schemas import BehaviouralFeatureVector
from src.twin.twin_model import (
    DigitalTwin,
    LiquidityHealth,
    PersonaType,
    build_financial_dna,
)
from src.twin.twin_store import TwinStore

_PUBSUB_CHANNEL = "twin_updated"


# ── metric derivation ─────────────────────────────────────────────────────────

def _derive_liquidity(cash_buffer_days: float) -> LiquidityHealth:
    """tier4_tier8.md §3.1: LOW<5, MEDIUM 5–15, HIGH>15"""
    if cash_buffer_days < 5.0:
        return "LOW"
    if cash_buffer_days <= 15.0:
        return "MEDIUM"
    return "HIGH"


def _derive_income_stability(fv: BehaviouralFeatureVector) -> float:
    """1 - spending_volatility, blended with income_stability_score."""
    blend = 0.6 * fv.income_stability_score + 0.4 * (1.0 - min(fv.spending_volatility_index, 1.0))
    return max(0.0, min(1.0, blend))


def _derive_risk_score(fv: BehaviouralFeatureVector) -> float:
    """
    Weighted non-linear combination, sigmoid-smoothed.

    Positive risk factors (higher = more risky):
      emi_burden_ratio        weight 0.25
      debit_failure_rate_90d  weight 0.20
      spending_volatility     weight 0.15
      end_of_month_dip        weight 0.10  (normalised by 50k)
      discretionary_ratio     weight 0.05
      cash_dependency_index   weight 0.05

    Negative risk factors (higher = less risky):
      savings_rate            weight -0.15
      income_stability        weight -0.05
    """
    raw = (
          0.25 * min(fv.emi_burden_ratio, 2.0) / 2.0
        + 0.20 * fv.debit_failure_rate_90d
        + 0.15 * min(fv.spending_volatility_index, 3.0) / 3.0
        + 0.10 * min(fv.end_of_month_liquidity_dip, 50_000.0) / 50_000.0
        + 0.05 * fv.discretionary_ratio
        + 0.05 * fv.cash_dependency_index
        - 0.15 * max(fv.savings_rate, 0.0)
        - 0.05 * fv.income_stability_score
    )
    # sigmoid smoother — maps (-∞,+∞) → (0,1) with centre at 0.5
    clipped = max(-6.0, min(6.0, raw * 6.0 - 3.0))
    return 1.0 / (1.0 + math.exp(-clipped))


def _infer_persona(fv: BehaviouralFeatureVector, twin: DigitalTwin) -> PersonaType:
    """
    Simple rule-based persona inference from feature signals.
    Keeps existing persona unless signals are strongly conclusive.
    """
    # shell/circular: very high throughput + high concentration + high debit failures
    if (
        fv.top3_merchant_concentration > 0.80
        and fv.debit_failure_rate_90d > 0.30
        and fv.daily_avg_throughput_30d > 100_000
    ):
        return "shell_circular"
    # paper_trader: high volatility + high throughput + low stability
    if (
        fv.spending_volatility_index > 1.5
        and fv.daily_avg_throughput_30d > 50_000
        and fv.income_stability_score < 0.4
    ):
        return "paper_trader"
    # new_to_credit: very sparse income, low emi count, low throughput
    if (
        fv.income_90d < 30_000
        and fv.emi_payment_count_90d == 0
        and fv.daily_avg_throughput_30d < 2_000
    ):
        return "new_to_credit"
    # genuine_struggling: high burden, low savings, moderate stability
    if fv.emi_burden_ratio > 0.55 and fv.savings_rate < 0.05:
        return "genuine_struggling"
    # keep existing if set
    if twin.persona != "unknown":
        return twin.persona
    return "genuine_healthy"


# ── service ───────────────────────────────────────────────────────────────────

class TwinService:
    """
    Manages the full Digital Twin update lifecycle for one Redis connection.
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        self._store = TwinStore(redis)
        self._redis = redis

    async def get_or_create(self, user_id: str) -> DigitalTwin:
        twin = await self._store.get(user_id)
        if twin is None:
            twin = DigitalTwin(user_id=user_id)
        return twin

    async def update_from_features(
        self,
        fv: BehaviouralFeatureVector,
        *,
        emit_event: bool = True,
    ) -> DigitalTwin:
        """
        Full update lifecycle as per tier4_tier8.md §7:
          1. Load (or create) twin
          2. Compute derived metrics
          3. Update core state + DNA
          4. Append to history summaries
          5. Increment version
          6. Save (Redis set + LPUSH)
          7. Emit twin_updated pub/sub event
        """
        twin = await self.get_or_create(fv.user_id)

        # 2. Derive metrics
        liquidity = _derive_liquidity(fv.cash_buffer_days)
        income_stability = _derive_income_stability(fv)
        spending_volatility = min(fv.spending_volatility_index, 1.0)
        risk_score = _derive_risk_score(fv)

        fv_dict = fv.model_dump()
        dna = build_financial_dna({k: float(v) if isinstance(v, (int, bool)) else v
                                   for k, v in fv_dict.items()
                                   if isinstance(v, (int, float, bool))})

        # 3. Update core state
        twin.liquidity_health = liquidity
        twin.income_stability = income_stability
        twin.spending_volatility = spending_volatility
        twin.risk_score = risk_score
        twin.cash_buffer_days = fv.cash_buffer_days
        twin.emi_burden_ratio = fv.emi_burden_ratio
        twin.financial_dna = dna
        twin.last_updated = datetime.utcnow()

        # Infer persona
        twin.persona = _infer_persona(fv, twin)

        # Update avatar
        twin.derive_avatar()

        # 4. Append summaries
        twin.risk_history.append(round(risk_score, 4))
        twin.feature_history_summary.append(twin.snapshot_summary())

        # 5. Increment version
        twin.version += 1

        # 6. Persist
        await self._store.save(twin)

        # 7. Emit event
        if emit_event:
            await self._emit_twin_updated(twin)

        return twin

    async def _emit_twin_updated(self, twin: DigitalTwin) -> None:
        """Publish a lightweight summary to the twin_updated pub/sub channel."""
        payload = json.dumps({
            "user_id": twin.user_id,
            "version": twin.version,
            "risk_score": twin.risk_score,
            "liquidity_health": twin.liquidity_health,
            "spending_volatility": twin.spending_volatility,
            "income_stability": twin.income_stability,
            "persona": twin.persona,
            "ts": twin.last_updated.isoformat(),
        })
        try:
            await self._redis.publish(_PUBSUB_CHANNEL, payload)
        except Exception:
            pass  # pub/sub is best-effort; twin is already persisted

    async def get(self, user_id: str) -> Optional[DigitalTwin]:
        return await self._store.get(user_id)

    async def get_history(self, user_id: str, limit: int = 20) -> list[dict]:
        return await self._store.get_history(user_id, limit)

    async def reconstruct_at(
        self, user_id: str, target_ts: datetime
    ) -> Optional[dict]:
        return await self._store.reconstruct_at(user_id, target_ts)

    # ── offline bootstrap ─────────────────────────────────────────────────────

    async def bootstrap_from_features_parquet(
        self, features_path: str = "data/features"
    ) -> int:
        """
        One-time offline twin initialisation from the features Parquet store.
        Reads every user_id=* partition, creates/updates twin, saves to Redis.
        Returns count of twins written.
        """
        import glob as _glob

        import polars as pl

        from src.features.schemas import BehaviouralFeatureVector

        partitions = _glob.glob(f"{features_path}/user_id=*/features.parquet")
        count = 0
        for path in partitions:
            try:
                df = pl.read_parquet(path)
            except Exception:
                continue
            for row in df.to_dicts():
                try:
                    fv = BehaviouralFeatureVector(**row)
                    await self.update_from_features(fv, emit_event=False)
                    count += 1
                except Exception:
                    continue
        return count
