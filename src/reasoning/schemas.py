"""
Tier 5 — Reasoning Agent Schemas

All Pydantic models for:
  - ContradictionDetectorResult   (Module 3 — three-layer statistical analysis)
  - CoTTrace                      (Module 2 — 6-step structured chain of thought)
  - RiskNarrative / BehavDelta    (Module 3 primary outputs)
  - IntentSignal / ConcernFlag    (Module 3 — machine-readable outputs)
  - InterrogationSession          (Module 5 — state machine)
  - Tier5Result                   (top-level composite output emitted to Tier 4 / Redis)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class FinancialSituation(str, Enum):
    STABLE_IMPROVING       = "STABLE_IMPROVING"
    STABLE_FLAT            = "STABLE_FLAT"
    STABLE_DEGRADING       = "STABLE_DEGRADING"
    STRESSED_RECOVERABLE   = "STRESSED_RECOVERABLE"
    STRESSED_CRITICAL      = "STRESSED_CRITICAL"
    CRISIS_ACUTE           = "CRISIS_ACUTE"
    CRISIS_SYSTEMIC        = "CRISIS_SYSTEMIC"
    ANOMALOUS_UNCLASSIFIABLE = "ANOMALOUS_UNCLASSIFIABLE"


class Severity(str, Enum):
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


class IncomeDirection(str, Enum):
    OVER_REPORTED  = "OVER_REPORTED"
    UNDER_REPORTED = "UNDER_REPORTED"
    CONSISTENT     = "CONSISTENT"


class InterrogationState(str, Enum):
    IDLE             = "IDLE"
    SIGNAL_ANALYSIS  = "SIGNAL_ANALYSIS"
    QUESTION_RANKING = "QUESTION_RANKING"
    Q_ASKED          = "Q_ASKED"
    Q_ANSWERED       = "Q_ANSWERED"
    ANSWER_PARSING   = "ANSWER_PARSING"
    TWIN_UPDATE      = "TWIN_UPDATE"
    RESIMULATION     = "RESIMULATION"
    COMPLETE         = "COMPLETE"
    ABANDONED        = "ABANDONED"


class IntentSignalType(str, Enum):
    LARGE_PURCHASE_IMMINENT = "LARGE_PURCHASE_IMMINENT"
    NEW_CREDIT_SEEKING      = "NEW_CREDIT_SEEKING"
    INCOME_TRANSITION       = "INCOME_TRANSITION"
    EMI_STRESS_IMMINENT     = "EMI_STRESS_IMMINENT"
    CASH_DEPENDENCY_RISING  = "CASH_DEPENDENCY_RISING"


class ConcernFlagType(str, Enum):
    INCOME_CONTRADICTION   = "INCOME_CONTRADICTION"
    HIGH_CASCADE_RISK      = "HIGH_CASCADE_RISK"
    EMI_OVERLOAD           = "EMI_OVERLOAD"
    LIQUIDITY_CRISIS       = "LIQUIDITY_CRISIS"
    FRAUD_ANOMALY          = "FRAUD_ANOMALY"
    LIFESTYLE_INFLATION    = "LIFESTYLE_INFLATION"
    UNRESOLVED_AMBIGUITY   = "UNRESOLVED_AMBIGUITY"
    CIRCULAR_FLOW_DETECTED = "CIRCULAR_FLOW_DETECTED"
    SALARY_IRREGULARITY    = "SALARY_IRREGULARITY"


# ── Contradiction Detector ─────────────────────────────────────────────────────

class ContradictionDetectorResult(BaseModel):
    """Output of the 3-layer income contradiction statistical analysis."""
    contradiction_detected: bool = False
    z_score: float = 0.0
    direction: IncomeDirection = IncomeDirection.CONSISTENT
    layer1_flag: bool = False   # Z-test on monthly income
    layer2_flag: bool = False   # Income source consistency (P2P vs P2M)
    layer3_lci: float = 0.0    # Lifestyle Consistency Index
    layer3_flag: bool = False
    layers_triggered: int = 0
    severity: Severity = Severity.LOW
    declared_income: float = 0.0
    observed_mean_income: float = 0.0
    confidence: float = 0.0
    details: str = ""


# ── Delta Packet (from Tier 4 history) ────────────────────────────────────────

class FeatureDelta(BaseModel):
    """A single feature's change between twin versions."""
    feature: str
    previous: float
    current: float
    z_change: float  # how many std devs it moved
    direction: Literal["improved", "degraded", "stable"] = "stable"


class DeltaPacket(BaseModel):
    """Priority 1 context: diff between latest and previous twin version."""
    changed_features: list[FeatureDelta] = Field(default_factory=list)
    regime_changed: bool = False
    new_event_types: list[str] = Field(default_factory=list)
    hours_since_last_update: float = 0.0


# ── CoT Schemas ───────────────────────────────────────────────────────────────

class Hypothesis(BaseModel):
    id: str                     # H1, H2, H3
    statement: str
    prior_probability: float
    posterior_probability: float = 0.0
    confirming_evidence: list[str] = Field(default_factory=list)
    disconfirming_evidence: list[str] = Field(default_factory=list)


class CoTTrace(BaseModel):
    """The full 6-step structured chain of thought from the LLM."""
    # Step 1: Signal observation (raw numeric listings)
    observe: str = ""
    # Step 2: Situation classification
    classify: FinancialSituation = FinancialSituation.ANOMALOUS_UNCLASSIFIABLE
    # Step 3: Competing hypotheses
    hypothesize: list[Hypothesis] = Field(default_factory=list)
    # Step 4: Evidence test — already embedded as posteriors in hypotheses
    test_summary: str = ""
    # Step 5: Synthesis — which hypothesis drove the output
    winning_hypothesis_id: str = "H1"
    synthesize_reasoning: str = ""
    # Step 6: Confidence + interrogation decision
    confidence: float = 0.5
    trigger_interrogation: bool = False
    # Metadata
    model_used: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    token_budget_used: int = 0


# ── Primary Outputs ───────────────────────────────────────────────────────────

class BehavDeltaItem(BaseModel):
    feature: str
    direction: Literal["improved", "degraded", "stable"]
    change_pct: float
    color: Literal["green", "red", "neutral"]


class BehaviouralChangeSummary(BaseModel):
    improved: list[BehavDeltaItem] = Field(default_factory=list)
    degraded: list[BehavDeltaItem] = Field(default_factory=list)
    stable: list[BehavDeltaItem] = Field(default_factory=list)
    net_direction: Literal["improving", "degrading", "flat"] = "flat"
    source_hypothesis: str = "H1"


class IntentSignal(BaseModel):
    signal_type: IntentSignalType
    probability: float
    expires_at: datetime
    trigger_tier8: bool = True
    reasoning: str = ""
    source_hypothesis: str = "H1"


class ConcernFlag(BaseModel):
    flag_type: ConcernFlagType
    severity: Severity
    evidence_citations: list[str] = Field(default_factory=list)
    recommended_action: str = ""
    confidence: float = 0.5
    source_hypothesis: str = "H1"


# ── Interrogation State Machine ────────────────────────────────────────────────

class QuestionTemplate(str, Enum):
    INCOME_CLARIFY      = "INCOME_CLARIFY"
    EXPENSE_EXPLAIN     = "EXPENSE_EXPLAIN"
    FUTURE_COMMITMENT   = "FUTURE_COMMITMENT"
    ASSET_DISCLOSURE    = "ASSET_DISCLOSURE"
    BEHAVIORAL_INTENT   = "BEHAVIORAL_INTENT"


class InterrogationQuestion(BaseModel):
    q_index: int                     # 0-4
    template: QuestionTemplate
    question_text: str
    signal_addressed: str
    urs_score: float = 0.0           # Uncertainty Reduction Score


class ParsedAnswer(BaseModel):
    q_index: int
    raw_answer: str
    numeric_amounts: list[float] = Field(default_factory=list)
    time_references: list[str] = Field(default_factory=list)
    boolean_confirmation: Optional[bool] = None
    new_entities: list[str] = Field(default_factory=list)
    twin_patch: dict = Field(default_factory=dict)  # direct patch to apply


class InterrogationSession(BaseModel):
    """Full state machine for one interrogation session."""
    session_id: str
    user_id: str
    state: InterrogationState = InterrogationState.IDLE
    trigger_reason: str = ""

    questions: list[InterrogationQuestion] = Field(default_factory=list)
    answers: list[ParsedAnswer] = Field(default_factory=list)
    current_q_index: int = 0

    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    interrogation_value_score: float = 0.0  # uncertainty reduction achieved

    twin_patches_applied: list[dict] = Field(default_factory=list)
    resimulation_triggered: bool = False


# ── Top-level Tier 5 Result ───────────────────────────────────────────────────

class Tier5Result(BaseModel):
    """
    Full output of a Tier 5 reasoning run.
    Emitted to:
      - Redis stream: stream:reasoning_events  (event: reasoning_completed)
      - Twin fields: last_narrative, active_flags, intent_signals, last_cot_trace
      - Audit log: full CoT + contradiction result
    """
    user_id: str
    run_id: str
    computed_at: datetime = Field(default_factory=datetime.utcnow)

    # Context assembly metadata
    context_tokens_used: int = 0
    delta_packet: Optional[DeltaPacket] = None
    contradiction: ContradictionDetectorResult = Field(
        default_factory=ContradictionDetectorResult
    )

    # CoT reasoning trace
    cot_trace: CoTTrace = Field(default_factory=CoTTrace)

    # Four primary outputs
    risk_narrative: str = ""
    behavioural_change_summary: BehaviouralChangeSummary = Field(
        default_factory=BehaviouralChangeSummary
    )
    intent_signals: list[IntentSignal] = Field(default_factory=list)
    concern_flags: list[ConcernFlag] = Field(default_factory=list)

    # Interrogation
    interrogation_needed: bool = False
    interrogation_session_id: Optional[str] = None

    # Error handling
    error: Optional[str] = None
    fallback_used: bool = False
