"""
Tier 7 — Cognitive Credit Engine: Schemas

All scoring is done on retail consumers using the 28-feature
BehaviouralFeatureVector already produced by Tiers 1-3.

No MSME / GST / EWB inputs — purely behavioural signals.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SHAPFeature(BaseModel):
    feature_name: str
    shap_value: float
    direction: Literal["increases_risk", "decreases_risk"]
    abs_magnitude: float


class BehaviouralOverride(BaseModel):
    """
    Trajectory-boost override: applied when the Digital Twin shows an
    improving risk trajectory (e.g. rising savings_rate, falling debit failures).
    Logged as a 'Trajectory Boost Trace' in the rule_trace for audit.
    """
    applied: bool = False
    trajectory_score_delta: float = 0.0   # score points added
    reasons: list[str] = Field(default_factory=list)


class CreditScoreResult(BaseModel):
    user_id: str
    credit_score: int                                  # 300–900
    risk_band: Literal["very_low_risk", "low_risk", "medium_risk", "high_risk"]
    probability_of_default: float
    recommended_personal_loan_amount: float            # INR
    recommended_tenure_months: int
    annual_percentage_rate: float                      # %
    cgtmse_eligible: bool
    top_5_shap_features: list[SHAPFeature]
    rule_trace: dict                                   # machine-readable audit
    model_used: Literal["full", "income_heavy"]
    behavioural_override: BehaviouralOverride
    score_freshness: str                               # ISO timestamp


class ScoreRequest(BaseModel):
    user_id: str
    force_income_model: bool = False    # override auto-routing


class ScoreStatusResponse(BaseModel):
    task_id: str
    status: Literal["pending", "processing", "complete", "failed"]
    result: CreditScoreResult | None = None
    error: str | None = None


class AuditReplayRequest(BaseModel):
    user_id: str
    target_timestamp: datetime
