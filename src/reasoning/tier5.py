"""
Tier 5 — Top-level Reasoning Agent entry point

Wires together all 5 modules:
  1. Context Assembly Engine
  2. Structured CoT Engine (6-step)
  3. Contradiction Detector (3-layer statistical)
  4. Primary Output Assembly (narrative, delta, intents, flags)
  5. Interrogation State Machine trigger

Emits:
  - Redis: stream:reasoning_events  (event: reasoning_completed)
  - Redis: tier5:result:{user_id}   (latest result, TTL 24h)
  - Twin fields: last_narrative, active_flags, intent_signals, last_cot_trace
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

import redis.asyncio as aioredis

from src.features.schemas import BehaviouralFeatureVector
from src.reasoning.contradiction_detector import (
    extract_monthly_income_from_features,
    run_contradiction_detector,
)
from src.reasoning.context_assembler import (
    assemble_context,
    build_delta_packet,
)
from src.reasoning.cot_engine import run_cot_engine
from src.reasoning.interrogation import (
    create_session,
    unanswered_to_flags,
)
from src.reasoning.schemas import (
    ConcernFlag,
    ConcernFlagType,
    DeltaPacket,
    InterrogationState,
    Severity,
    Tier5Result,
)


# ── Trigger Conditions for Interrogation ──────────────────────────────────────

def _should_trigger_interrogation(
    cot_trigger: bool,
    contradiction_layers: int,
    features: BehaviouralFeatureVector,
    is_first_run: bool,
) -> tuple[bool, str]:
    """
    Returns (should_trigger, reason_string).
    Any one condition is sufficient (tier5.md Module 5).
    """
    if cot_trigger:
        return True, "low_posterior_confidence"
    if contradiction_layers >= 2:
        return True, "income_contradiction_multi_layer"
    # EWS proxy: use debit_failure + anomaly_flag as stress signal
    if features.debit_failure_rate_90d > 0.12 and features.anomaly_flag:
        return True, "stress_anomaly_combined"
    if features.merchant_category_shift_count > 3:
        return True, "sudden_behavioral_shift"
    if is_first_run:
        return True, "first_run_baseline"
    return False, ""


# ── Main Entry Point ──────────────────────────────────────────────────────────

async def run_tier5(
    features: BehaviouralFeatureVector,
    redis_client: aioredis.Redis,
    declared_income: float = 0.0,
    previous_features: Optional[dict] = None,
    recent_events: Optional[list[dict]] = None,
    simulation_verdict: Optional[dict] = None,
    is_first_run: bool = False,
) -> Tier5Result:
    """
    Full Tier 5 reasoning pipeline for one user.

    Args:
        features:           Latest BehaviouralFeatureVector from Tier 3
        redis_client:       Async Redis client for persistence + event emission
        declared_income:    From onboarding (defaults to income_90d/3 if unknown)
        previous_features:  Previous twin feature snapshot dict (for delta computation)
        recent_events:      Last 15 typed events from Tier 2 (for context)
        simulation_verdict: Tier 6 EWS/CVaR dict (None = not yet implemented)
        is_first_run:       Whether this is the first Tier 5 run for this user

    Returns:
        Tier5Result — full structured output
    """
    run_id = str(uuid.uuid4())
    user_id = features.user_id

    # If no declared income provided, use 90d average as proxy
    if declared_income <= 0:
        declared_income = features.income_90d / 3.0

    result = Tier5Result(user_id=user_id, run_id=run_id)

    # ── Step 1: Contradiction Detector ────────────────────────────────────────
    monthly_obs = extract_monthly_income_from_features(
        features.income_90d,
        features.income_30d,
        features.income_7d,
    )
    # Approximate P2P income fraction from cash dependency (proxy if no event-level data)
    p2p_fraction = min(features.cash_dependency_index * 1.5, 1.0)

    contradiction = run_contradiction_detector(
        declared_income=declared_income,
        monthly_income_observations=monthly_obs,
        income_stability_score=features.income_stability_score,
        p2p_income_fraction=p2p_fraction,
        discretionary_30d=features.discretionary_30d,
        cash_dependency_index=features.cash_dependency_index,
    )
    result.contradiction = contradiction

    # ── Step 2: Delta Packet ──────────────────────────────────────────────────
    delta: Optional[DeltaPacket] = None
    if previous_features:
        current_floats = {
            k: float(v) for k, v in features.model_dump().items()
            if isinstance(v, (int, float)) and k not in ("subscription_count_30d",
                                                           "emi_payment_count_90d",
                                                           "merchant_category_shift_count")
        }
        # Approximate std devs (population-level estimates for Indian retail)
        feature_stds = {
            "emi_burden_ratio": 0.12, "savings_rate": 0.10,
            "income_stability_score": 0.15, "spending_volatility_index": 0.12,
            "cash_buffer_days": 10.0, "discretionary_ratio": 0.09,
            "debit_failure_rate_90d": 0.06, "income_90d": 50_000,
            "income_30d": 20_000, "net_cashflow_30d": 15_000,
        }
        delta = build_delta_packet(current_floats, previous_features, feature_stds)
    result.delta_packet = delta

    # ── Step 3: Context Assembly ───────────────────────────────────────────────
    context = assemble_context(
        features=features,
        declared_income=declared_income,
        contradiction_result=contradiction,
        delta_packet=delta,
        recent_events=recent_events or [],
        simulation_verdict=simulation_verdict,
    )
    result.context_tokens_used = context.total_tokens_used

    # ── Step 4: CoT Engine ────────────────────────────────────────────────────
    try:
        cot, risk_narrative, bcs, intent_signals, concern_flags = run_cot_engine(
            features=features,
            context=context,
        )
        result.cot_trace = cot
        result.risk_narrative = risk_narrative
        result.behavioural_change_summary = bcs
        result.intent_signals = intent_signals
        result.concern_flags = concern_flags
    except Exception as e:
        result.error = f"CoT engine error: {str(e)}"
        result.fallback_used = True
        result.risk_narrative = (
            "Financial analysis is temporarily unavailable. "
            "Your data has been captured and will be processed shortly."
        )

    # Inject contradiction flag into concern flags if detected
    if contradiction.contradiction_detected and contradiction.layers_triggered >= 2:
        existing_types = {f.flag_type for f in result.concern_flags}
        if ConcernFlagType.INCOME_CONTRADICTION not in existing_types:
            result.concern_flags.insert(0, ConcernFlag(
                flag_type=ConcernFlagType.INCOME_CONTRADICTION,
                severity=contradiction.severity,
                evidence_citations=[contradiction.details],
                recommended_action=(
                    "Verify income sources with the user. "
                    "Consider scheduling an interrogation session."
                ),
                confidence=contradiction.confidence,
                source_hypothesis="H1",
            ))
        result.concern_flags = result.concern_flags[:5]

    # ── Step 5: Interrogation Trigger ─────────────────────────────────────────
    max_posterior = max(
        (h.posterior_probability for h in result.cot_trace.hypothesize),
        default=0.5,
    )
    should_interrogate, reason = _should_trigger_interrogation(
        cot_trigger=result.cot_trace.trigger_interrogation,
        contradiction_layers=contradiction.layers_triggered,
        features=features,
        is_first_run=is_first_run,
    )
    result.interrogation_needed = should_interrogate

    if should_interrogate:
        # Create session but don't start it — UI will poll for it
        session = create_session(
            user_id=user_id,
            features=features,
            declared_income=declared_income,
            max_hypothesis_posterior=max_posterior,
            contradiction_layers=contradiction.layers_triggered,
            trigger_reason=reason,
        )
        session_key = f"tier5:interrogation:{session.session_id}"
        await redis_client.setex(
            session_key,
            86400,  # 24h TTL
            session.model_dump_json(),
        )
        result.interrogation_session_id = session.session_id

        # Emit interrogation_started event
        await redis_client.xadd(
            "stream:reasoning_events",
            {
                "event": "interrogation_started",
                "user_id": user_id,
                "session_id": session.session_id,
                "first_question": session.questions[0].question_text if session.questions else "",
                "trigger_reason": reason,
            },
        )

    # ── Step 6: Persist Result ────────────────────────────────────────────────
    result_json = result.model_dump_json()

    # Cache latest result per user (24h TTL)
    await redis_client.setex(f"tier5:result:{user_id}", 86400, result_json)

    # Emit reasoning_completed event to stream
    await redis_client.xadd(
        "stream:reasoning_events",
        {
            "event": "reasoning_completed",
            "user_id": user_id,
            "run_id": run_id,
            "situation": result.cot_trace.classify.value,
            "confidence": str(result.cot_trace.confidence),
            "concern_count": str(len(result.concern_flags)),
            "narrative": result.risk_narrative[:200],
            "interrogation_needed": "1" if should_interrogate else "0",
        },
        maxlen=10_000,
        approximate=True,
    )

    # Emit contradiction_flagged if detected (high priority — consumed by Tier 7 & 9)
    if contradiction.contradiction_detected and contradiction.layers_triggered >= 2:
        await redis_client.xadd(
            "stream:reasoning_events",
            {
                "event": "contradiction_flagged",
                "user_id": user_id,
                "severity": contradiction.severity.value,
                "layers": str(contradiction.layers_triggered),
                "z_score": str(contradiction.z_score),
                "direction": contradiction.direction.value,
            },
        )

    return result


async def get_tier5_result(
    user_id: str,
    redis_client: aioredis.Redis,
) -> Optional[Tier5Result]:
    """Retrieve the latest cached Tier 5 result for a user."""
    raw = await redis_client.get(f"tier5:result:{user_id}")
    if not raw:
        return None
    return Tier5Result.model_validate_json(raw)
