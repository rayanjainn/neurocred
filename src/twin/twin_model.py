"""
Tier 4 — Digital Twin Model

Pydantic v2 schema for the Digital Twin state, avatar expression,
and financial DNA embedding. Single source of truth per user.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ── Avatar ────────────────────────────────────────────────────────────────────

AvatarExpression = Literal["calm", "concerned", "urgent", "educational"]

LiquidityHealth = Literal["LOW", "MEDIUM", "HIGH"]

PersonaType = Literal[
    "genuine_healthy",
    "genuine_struggling",
    "shell_circular",
    "paper_trader",
    "new_to_credit",
    "unknown",
]


_EXPRESSION_MAP: dict[str, AvatarExpression] = {
    "LOW": "urgent",
    "MEDIUM": "concerned",
    "HIGH": "calm",
}

_PERSONA_EXPRESSION_OVERRIDE: dict[str, AvatarExpression] = {
    "new_to_credit": "educational",
    "shell_circular": "concerned",
}

_PERSONA_MOOD: dict[str, str] = {
    "genuine_healthy": "Your financial health looks stable today.",
    "genuine_struggling": "There are some areas to watch. Let's work on it together.",
    "shell_circular": "Unusual activity detected. Please review your recent transactions.",
    "paper_trader": "High volatility patterns observed. Stay cautious.",
    "new_to_credit": "You're building your financial profile. Keep it up!",
    "unknown": "Analysing your financial patterns…",
}


class AvatarState(BaseModel):
    expression: AvatarExpression = "calm"
    mood_message: str = "Analysing your financial patterns…"
    liquidity_label: LiquidityHealth = "HIGH"


# ── Financial DNA ─────────────────────────────────────────────────────────────

DNA_DIM = 32

_DNA_FEATURE_KEYS = [
    "emi_burden_ratio",
    "savings_rate",
    "income_stability_score",
    "spending_volatility_index",
    "cash_buffer_days",
    "discretionary_ratio",
    "debit_failure_rate_90d",
    "lifestyle_inflation_trend",
    "daily_avg_throughput_30d",
    "end_of_month_liquidity_dip",
    "subscription_count_30d",
    "emi_payment_count_90d",
    "top3_merchant_concentration",
    "cash_dependency_index",
    "peer_cohort_benchmark_deviation",
    "income_7d",
    "income_30d",
    "income_90d",
    "net_cashflow_30d",
    "net_cashflow_90d",
]

# Interaction pairs: (feat_a_idx, feat_b_idx)
_INTERACTION_PAIRS: list[tuple[int, int]] = [
    (3, 14),   # spending_volatility × peer_deviation
    (4, 6),    # cash_buffer × debit_failure
    (2, 7),    # income_stability × lifestyle_inflation
    (0, 1),    # emi_burden × savings_rate
    (8, 9),    # throughput × eom_dip
    (5, 13),   # discretionary_ratio × cash_dependency
    (10, 11),  # subscription_count × emi_count
    (12, 14),  # top3_concentration × peer_deviation
    (16, 18),  # income_30d × net_cashflow_30d
    (17, 19),  # income_90d × net_cashflow_90d
    (1, 4),    # savings_rate × cash_buffer
    (0, 6),    # emi_burden × debit_failure
]

# Weights for the linear projection (seeded, deterministic)
import numpy as _np
_rng = _np.random.default_rng(0xC0FFEE)
_W = _rng.uniform(0.5, 1.5, size=(DNA_DIM, len(_DNA_FEATURE_KEYS) + len(_INTERACTION_PAIRS))).astype(_np.float32)
del _rng


def build_financial_dna(features: dict[str, float]) -> list[float]:
    """
    Build a 32-dim deterministic behavioural embedding from feature dict.

    Steps:
      1. Normalise known features to [0, 1] using fixed range clips.
      2. Compute interaction terms (element-wise products of normalised pairs).
      3. Apply fixed random projection W: dna = W @ x, clip to [0, 1].
    """
    import numpy as np

    _RANGES: dict[str, tuple[float, float]] = {
        "emi_burden_ratio": (0.0, 2.0),
        "savings_rate": (-1.0, 1.0),
        "income_stability_score": (0.0, 1.0),
        "spending_volatility_index": (0.0, 3.0),
        "cash_buffer_days": (0.0, 90.0),
        "discretionary_ratio": (0.0, 1.0),
        "debit_failure_rate_90d": (0.0, 1.0),
        "lifestyle_inflation_trend": (-1.0, 2.0),
        "daily_avg_throughput_30d": (0.0, 500_000.0),
        "end_of_month_liquidity_dip": (0.0, 50_000.0),
        "subscription_count_30d": (0.0, 20.0),
        "emi_payment_count_90d": (0.0, 10.0),
        "top3_merchant_concentration": (0.0, 1.0),
        "cash_dependency_index": (0.0, 1.0),
        "peer_cohort_benchmark_deviation": (-3.0, 3.0),
        "income_7d": (0.0, 200_000.0),
        "income_30d": (0.0, 500_000.0),
        "income_90d": (0.0, 1_500_000.0),
        "net_cashflow_30d": (-300_000.0, 300_000.0),
        "net_cashflow_90d": (-500_000.0, 500_000.0),
    }

    norm = np.zeros(len(_DNA_FEATURE_KEYS), dtype=np.float32)
    for i, key in enumerate(_DNA_FEATURE_KEYS):
        val = features.get(key, 0.0) or 0.0
        lo, hi = _RANGES[key]
        norm[i] = np.clip((val - lo) / (hi - lo + 1e-9), 0.0, 1.0)

    interactions = np.array(
        [norm[a] * norm[b] for a, b in _INTERACTION_PAIRS], dtype=np.float32
    )
    x = np.concatenate([norm, interactions])
    dna = np.clip(_W @ x / (len(x) * 1.0), 0.0, 1.0)
    return dna.tolist()


# ── Digital Twin state ────────────────────────────────────────────────────────

class DigitalTwin(BaseModel):
    """
    Full Digital Twin state for one user.
    Stored in Redis as `twin:{user_id}` (JSON).
    History list: `twin:{user_id}:history` (LPUSH of JSON snapshots).
    """

    user_id: str
    persona: PersonaType = "unknown"

    # Core risk metrics
    risk_score: float = Field(0.5, ge=0.0, le=1.0)
    liquidity_health: LiquidityHealth = "HIGH"
    income_stability: float = Field(0.5, ge=0.0, le=1.0)
    spending_volatility: float = Field(0.3, ge=0.0, le=1.0)
    cash_buffer_days: float = Field(15.0, ge=0.0, le=90.0)
    emi_burden_ratio: float = Field(0.3, ge=0.0)

    # Financial DNA embedding (32-dim)
    financial_dna: list[float] = Field(default_factory=lambda: [0.0] * DNA_DIM)

    # Avatar
    avatar_state: AvatarState = Field(default_factory=AvatarState)

    # Versioning / audit
    version: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    # Rolling history summaries (last 5 versions, lightweight)
    risk_history: list[float] = Field(default_factory=list)
    feature_history_summary: list[dict] = Field(default_factory=list)

    @field_validator("risk_history", mode="before")
    @classmethod
    def _cap_history(cls, v: list[float]) -> list[float]:
        return v[-20:] if len(v) > 20 else v

    @field_validator("feature_history_summary", mode="before")
    @classmethod
    def _cap_feature_summary(cls, v: list[dict]) -> list[dict]:
        return v[-10:] if len(v) > 10 else v

    # ── derived helpers ───────────────────────────────────────────────────────

    def derive_avatar(self) -> None:
        """Recompute avatar_state from current twin metrics."""
        expression: AvatarExpression = _EXPRESSION_MAP.get(self.liquidity_health, "calm")
        if self.persona in _PERSONA_EXPRESSION_OVERRIDE:
            expression = _PERSONA_EXPRESSION_OVERRIDE[self.persona]
        self.avatar_state = AvatarState(
            expression=expression,
            mood_message=_PERSONA_MOOD.get(self.persona, _PERSONA_MOOD["unknown"]),
            liquidity_label=self.liquidity_health,
        )

    def snapshot_summary(self) -> dict:
        """Lightweight dict for risk_history / feature_history_summary entries."""
        return {
            "version": self.version,
            "ts": self.last_updated.isoformat(),
            "risk_score": round(self.risk_score, 4),
            "liquidity_health": self.liquidity_health,
            "income_stability": round(self.income_stability, 4),
        }

    def cibil_like_score(self) -> int:
        """Map risk_score [0,1] → CIBIL-like 300–900 band."""
        # risk_score=0 → 900 (excellent), risk_score=1 → 300 (poor)
        return int(round(900 - self.risk_score * 600))
