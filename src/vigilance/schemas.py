"""
Tier 9 — Schemas for the Vigilance (Anomaly & Deception Detection) Layer

All Pydantic output models for:
  - FraudRingResult          (Module 2 — NetworkX graph cycle detection)
  - ScamProbabilityResult    (Module 3 — Social Engineering Defence)
  - BotDetectorResult        (Module 4 — Synthetic Identity & Bot Detection)
  - StressSignalResult       (Module 5.1 — Hidden Financial Stress)
  - IncomeUnderreportResult  (Module 5.2 — Progressive Income Underreporting)
  - IdentityShiftResult      (Module 5.3 — Identity & Behaviour Shift)
  - Tier9Result              (Top-level aggregated output)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────────

class RiskLevel(str, Enum):
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


class ScamType(str, Enum):
    URGENCY_MANIPULATION  = "urgency_manipulation"
    AUTHORITY_IMPERSONATION = "authority_impersonation"
    OTP_PHISHING          = "otp_phishing"
    UNKNOWN               = "unknown"


# ── Module 2: Fraud Ring Detection ────────────────────────────────────────────

class DetectedCycle(BaseModel):
    """A single temporal fraud cycle found in the transaction graph."""
    nodes: list[str]                            # e.g. ["u_0001", "u_0042", "u_0099"]
    cycle_velocity: float                        # avg daily flow across cycle edges (INR)
    cycle_recurrence: int                        # how many times this cycle recurred (30-90d)
    temporal_consistency: bool                   # all edge timestamps are monotonically ordered
    total_flow_90d: float                        # total INR flowing through cycle in 90d
    suspicious: bool                             # passed all thresholds


class FraudRingResult(BaseModel):
    """Output of the NetworkX Fraud Ring & Cycle Detection engine."""
    user_id: str
    fraud_ring_flag: bool = False
    fraud_confidence: float = 0.0               # [0.0, 1.0]
    pagerank_score: float = 0.0                 # user's PageRank in the transaction graph
    is_shell_hub: bool = False                  # high PageRank + low business maturity
    detected_cycles: list[DetectedCycle] = Field(default_factory=list)
    scc_size: int = 0                           # size of the Strongly Connected Component
    risk_level: RiskLevel = RiskLevel.LOW
    evidence: str = ""


# ── Module 3: Social Engineering Defence ─────────────────────────────────────

class ScamSignal(BaseModel):
    """Individual scam signal with evidence."""
    signal_type: ScamType
    matched_text: str
    confidence: float
    severity: RiskLevel


class ScamProbabilityResult(BaseModel):
    """Output of the Social Engineering Defence Module."""
    user_id: str
    scam_probability: float = 0.0              # [0.0, 1.0] Bayesian combined score
    is_scam_alert: bool = False
    urgency_score: float = 0.0
    authority_score: float = 0.0
    otp_phishing_score: float = 0.0
    signals: list[ScamSignal] = Field(default_factory=list)
    analyzed_text: str = ""
    risk_level: RiskLevel = RiskLevel.LOW
    recommended_action: str = ""


# ── Module 4: Synthetic Identity & Bot Detector ───────────────────────────────

class BotDetectorResult(BaseModel):
    """Output of the Synthetic Identity & Bot Detection engine."""
    user_id: str
    consistency_score: float = 0.0             # [0.0, 1.0] — 1.0 = perfectly bot-like
    is_bot_flag: bool = False
    is_mule_flag: bool = False
    improbable_precision_detected: bool = False # exact interval regularity
    network_improbability_score: float = 0.0   # hub-and-spoke pattern score
    mule_dna_score: float = 0.0                # match to laundering template
    risk_level: RiskLevel = RiskLevel.LOW
    evidence: list[str] = Field(default_factory=list)


# ── Module 5.1: Hidden Financial Stress ───────────────────────────────────────

class StressSignalResult(BaseModel):
    """Logistic regression output for hidden liquidity stress."""
    user_id: str
    stress_confidence_score: float = 0.0       # [0.0, 1.0]
    velocity_stress_spike: bool = False
    cash_buffer_trend: str = "stable"          # "improving" | "stable" | "declining" | "critical"
    debit_failure_trend: str = "stable"
    rolling_features: dict = Field(default_factory=dict)  # audit trace
    risk_level: RiskLevel = RiskLevel.LOW


# ── Module 5.2: Progressive Income Underreporting ────────────────────────────

class IncomeUnderreportResult(BaseModel):
    """Sigmoid-based income underreporting detection."""
    user_id: str
    income_underreport_score: float = 0.0      # [0.0, 1.0]
    is_underreporting: bool = False
    observed_income_proxy: float = 0.0         # sum of non-P2P credits (90d)
    declared_income_proxy: float = 0.0
    cohort_std_income: float = 0.0
    zscore: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW


# ── Module 5.3: Identity & Behaviour Shift ────────────────────────────────────

class IdentityShiftResult(BaseModel):
    """JS-Divergence + XGBoost identity shift detector."""
    user_id: str
    identity_shift_score: float = 0.0          # [0.0, 1.0]
    is_identity_shifted: bool = False
    js_divergence: float = 0.0                 # Jensen-Shannon divergence of category mix
    category_drift_score: float = 0.0
    discretionary_ratio_change: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    top_shifted_categories: list[str] = Field(default_factory=list)


# ── Top-level Tier9Result ─────────────────────────────────────────────────────

class Tier9Result(BaseModel):
    """Aggregated Tier 9 output, consumed by Tier 7 Cognitive Engine."""
    user_id: str
    run_id: str
    computed_at: datetime = Field(default_factory=datetime.utcnow)

    # Module outputs
    fraud_ring:        FraudRingResult
    scam_defence:      ScamProbabilityResult
    bot_detector:      BotDetectorResult
    stress_signal:     StressSignalResult
    income_underreport: IncomeUnderreportResult
    identity_shift:    IdentityShiftResult

    # Decision outputs for Tier 7
    fraud_ring_flag:   bool  = False
    fraud_confidence:  float = 0.0
    scam_probability:  float = 0.0
    pagerank_score:    float = 0.0
    overall_risk_level: RiskLevel = RiskLevel.LOW

    # Computed composite deception score [0, 1]
    deception_score: float = 0.0

    error: Optional[str] = None
