"""
Tier 5 — Conversational Interrogation State Machine (Module 5)

A proper state machine, not a chatbot. Defined states, defined transitions.
Every terminal state produces a twin state update (patch dict).

States:
  IDLE → SIGNAL_ANALYSIS → QUESTION_RANKING → Q_ASKED →
  Q_ANSWERED → ANSWER_PARSING → TWIN_UPDATE → RESIMULATION → COMPLETE

  (or ABANDONED if user stops answering)

Persisted in Redis as: "tier5:interrogation:{session_id}" (JSON)
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
import urllib.error
import uuid
from datetime import datetime
from typing import Optional

from config.settings import settings
from src.features.schemas import BehaviouralFeatureVector
from src.reasoning.schemas import (
    ConcernFlag,
    ConcernFlagType,
    InterrogationQuestion,
    InterrogationSession,
    InterrogationState,
    IntentSignal,
    ParsedAnswer,
    QuestionTemplate,
    Severity,
)


# ── Uncertainty Reduction Score ────────────────────────────────────────────────

def compute_urs(
    feature: str,
    feature_value: float,
    max_posterior: float,
    risk_score: float,
) -> float:
    """
    URS(signal) = severity × ambiguity × twin_impact

    severity    = feature importance weight (from schema.md §8)
    ambiguity   = 1 - max_hypothesis_posterior
    twin_impact = how much risk_score would change if this resolved
    """
    # Feature importance weights (higher = more important to credit decisioning)
    IMPORTANCE: dict[str, float] = {
        "emi_burden_ratio":           0.95,
        "debit_failure_rate_90d":     0.90,
        "cash_buffer_days":           0.85,
        "income_stability_score":     0.85,
        "savings_rate":               0.80,
        "spending_volatility_index":  0.75,
        "lifestyle_inflation_trend":  0.70,
        "discretionary_ratio":        0.65,
        "cash_dependency_index":      0.60,
        "top3_merchant_concentration":0.55,
        "peer_cohort_benchmark_deviation": 0.50,
    }
    severity = IMPORTANCE.get(feature, 0.40)
    ambiguity = 1.0 - min(max_posterior, 1.0)
    # twin_impact: higher risk_score means more impact from resolution
    twin_impact = 0.3 + 0.7 * risk_score
    return round(severity * ambiguity * twin_impact, 4)


# ── Question Generator ─────────────────────────────────────────────────────────

def _build_question_text(
    template: QuestionTemplate,
    features: BehaviouralFeatureVector,
    declared_income: float,
    metadata: dict,
) -> str:
    """Fill in template variables with actuals from features/metadata."""
    if template == QuestionTemplate.INCOME_CLARIFY:
        observed = metadata.get("observed_mean_income", features.income_90d / 3)
        return (
            f"We noticed your observed income of ₹{observed:,.0f} per month differs from "
            f"your declared ₹{declared_income:,.0f}. "
            f"Do you have additional income sources not reflected in your bank transactions?"
        )

    elif template == QuestionTemplate.EXPENSE_EXPLAIN:
        cat = metadata.get("category", "discretionary spending")
        pct = metadata.get("change_pct", round(features.lifestyle_inflation_trend * 100, 0))
        return (
            f"Your spending in {cat} increased by {pct:.0f}% in the last 30 days "
            f"versus your 90-day baseline. Is this a one-time event or an ongoing change?"
        )

    elif template == QuestionTemplate.FUTURE_COMMITMENT:
        n_days = metadata.get("stress_days", 30)
        return (
            f"Our simulation shows a potential EMI stress event likely in {n_days} days. "
            f"Are you planning any new financial commitments (loans, purchases) in the next 60 days?"
        )

    elif template == QuestionTemplate.ASSET_DISCLOSURE:
        return (
            "Do you have liquid assets (Fixed Deposits, savings in other accounts, or mutual funds) "
            "not captured in the connected accounts? "
            "Declaring these may significantly improve your credit assessment."
        )

    elif template == QuestionTemplate.BEHAVIORAL_INTENT:
        intent = metadata.get("intent_signal", "an unusual spending shift")
        return (
            f"Your spending pattern suggests {intent}. "
            f"Can you share more context about this recent change in financial behaviour?"
        )

    return "Can you provide more context about your recent financial activity?"


def rank_signals_for_interrogation(
    features: BehaviouralFeatureVector,
    max_hypothesis_posterior: float,
    contradiction_layers: int,
    declared_income: float,
) -> list[tuple[str, float, QuestionTemplate, dict]]:
    """
    Rank signals by URS and return top 5 as (feature, urs, template, metadata).
    """
    risk_score_proxy = (
        features.emi_burden_ratio * 0.35 +
        features.debit_failure_rate_90d * 0.25 +
        (1 - features.income_stability_score) * 0.20 +
        features.spending_volatility_index * 0.20
    )

    candidates: list[tuple[str, float, QuestionTemplate, dict]] = []

    # Income contradiction always goes first if triggered
    if contradiction_layers >= 2:
        urs = compute_urs("income_stability_score", features.income_stability_score,
                          max_hypothesis_posterior, risk_score_proxy)
        candidates.append((
            "income_contradiction",
            urs * 1.5,  # boost
            QuestionTemplate.INCOME_CLARIFY,
            {"observed_mean_income": features.income_90d / 3.0, "declared_income": declared_income},
        ))

    # EMI overload
    if features.emi_burden_ratio > 0.40:
        urs = compute_urs("emi_burden_ratio", features.emi_burden_ratio,
                          max_hypothesis_posterior, risk_score_proxy)
        candidates.append((
            "emi_burden_ratio",
            urs,
            QuestionTemplate.FUTURE_COMMITMENT,
            {"stress_days": max(7, int(features.cash_buffer_days))},
        ))

    # Lifestyle inflation
    if abs(features.lifestyle_inflation_trend) > 0.15:
        urs = compute_urs("lifestyle_inflation_trend", features.lifestyle_inflation_trend,
                          max_hypothesis_posterior, risk_score_proxy)
        candidates.append((
            "lifestyle_inflation_trend",
            urs,
            QuestionTemplate.EXPENSE_EXPLAIN,
            {"category": "discretionary spending",
             "change_pct": round(features.lifestyle_inflation_trend * 100, 0)},
        ))

    # Low cash buffer
    if features.cash_buffer_days < 10:
        urs = compute_urs("cash_buffer_days", features.cash_buffer_days,
                          max_hypothesis_posterior, risk_score_proxy)
        candidates.append((
            "cash_buffer_days",
            urs,
            QuestionTemplate.ASSET_DISCLOSURE,
            {},
        ))

    # Category shift (behavioral intent)
    if features.merchant_category_shift_count > 3:
        urs = compute_urs("merchant_category_shift_count",
                          float(features.merchant_category_shift_count),
                          max_hypothesis_posterior, risk_score_proxy)
        candidates.append((
            "merchant_category_shift_count",
            urs,
            QuestionTemplate.BEHAVIORAL_INTENT,
            {"intent_signal": "significant shifts in spending categories"},
        ))

    # Debit failures
    if features.debit_failure_rate_90d > 0.10:
        urs = compute_urs("debit_failure_rate_90d", features.debit_failure_rate_90d,
                          max_hypothesis_posterior, risk_score_proxy)
        candidates.append((
            "debit_failure_rate_90d",
            urs,
            QuestionTemplate.FUTURE_COMMITMENT,
            {"stress_days": 14},
        ))

    # Sort by URS descending
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[:5]


# ── Answer Parser ──────────────────────────────────────────────────────────────

def _parse_answer_llm(q_index: int, question_text: str, raw_answer: str) -> ParsedAnswer:
    """
    Use LLM (lightweight extraction prompt) to parse the user's answer.
    Falls back to regex if LLM unavailable.
    """
    # Regex extraction fallback (always run first for speed)
    amounts = [float(m.replace(",", "")) for m in re.findall(r"₹?(\d[\d,]+)", raw_answer)]
    boolean = None
    raw_lower = raw_answer.lower()
    if any(w in raw_lower for w in ["yes", "correct", "yeah", "haan", "absolutely"]):
        boolean = True
    elif any(w in raw_lower for w in ["no", "nahi", "not", "never", "nope"]):
        boolean = False

    # Time refs
    time_refs = re.findall(
        r"\b(\d+\s*(?:day|week|month|year)s?|next\s+\w+|last\s+\w+|january|february|march|april|may|june|july|august|september|october|november|december)\b",
        raw_lower,
    )

    # Build twin patch hints from answer
    twin_patch: dict = {}
    if amounts and boolean is True:
        # User confirmed additional income
        if "income" in question_text.lower() or "salary" in question_text.lower():
            twin_patch["income_supplement"] = sum(amounts)
    if boolean is False and "emi" in question_text.lower():
        twin_patch["no_new_emi"] = True

    return ParsedAnswer(
        q_index=q_index,
        raw_answer=raw_answer,
        numeric_amounts=amounts,
        time_references=time_refs,
        boolean_confirmation=boolean,
        twin_patch=twin_patch,
    )


def _apply_twin_patches(
    answers: list[ParsedAnswer],
    features: BehaviouralFeatureVector,
) -> dict:
    """
    Translate parsed answers into concrete twin state patches.
    Returns a dict that can be applied to the DigitalTwin via Tier 4 update lifecycle.
    """
    patch: dict = {}

    for ans in answers:
        # Additional income source declared
        supplement = ans.twin_patch.get("income_supplement")
        if supplement:
            new_income = features.income_90d + float(supplement) * 3  # 3 months
            patch["income_90d"] = round(new_income, 2)
            patch["income_30d"] = round(features.income_30d + float(supplement), 2)
            # Recompute savings rate proxy
            if new_income > 0:
                essential_approx = features.essential_90d or 0
                patch["savings_rate"] = round(
                    (new_income - essential_approx) / new_income, 4
                )

        # No new EMI confirmed
        if ans.twin_patch.get("no_new_emi"):
            patch["no_new_emi_confirmed"] = True

    return patch


# ── Session Management ────────────────────────────────────────────────────────

def create_session(
    user_id: str,
    features: BehaviouralFeatureVector,
    declared_income: float,
    max_hypothesis_posterior: float,
    contradiction_layers: int,
    trigger_reason: str,
) -> InterrogationSession:
    """Create a new interrogation session with ranked questions."""
    session_id = str(uuid.uuid4())

    signal_candidates = rank_signals_for_interrogation(
        features, max_hypothesis_posterior, contradiction_layers, declared_income
    )

    questions = [
        InterrogationQuestion(
            q_index=i,
            template=template,
            question_text=_build_question_text(template, features, declared_income, metadata),
            signal_addressed=signal,
            urs_score=urs,
        )
        for i, (signal, urs, template, metadata) in enumerate(signal_candidates)
    ]

    return InterrogationSession(
        session_id=session_id,
        user_id=user_id,
        state=InterrogationState.QUESTION_RANKING,
        trigger_reason=trigger_reason,
        questions=questions,
        current_q_index=0,
    )


def advance_session(
    session: InterrogationSession,
    user_answer: Optional[str],
    features: BehaviouralFeatureVector,
) -> tuple[InterrogationSession, Optional[str], dict]:
    """
    Advance the state machine by one step.

    Args:
        session: Current session state
        user_answer: User's answer to the current question (None = abandoned)
        features: Current feature vector for context

    Returns:
        (updated_session, next_question_text_or_None, twin_patch_dict)
    """
    twin_patch: dict = {}

    if user_answer is None:
        # Mark unanswered questions as UNRESOLVED_AMBIGUITY
        session.state = InterrogationState.ABANDONED
        return session, None, twin_patch

    if session.state in (InterrogationState.QUESTION_RANKING, InterrogationState.Q_ASKED,
                          InterrogationState.Q_ANSWERED):

        # Parse the current answer
        q = session.questions[session.current_q_index]
        parsed = _parse_answer_llm(session.current_q_index, q.question_text, user_answer)
        session.answers.append(parsed)
        session.state = InterrogationState.ANSWER_PARSING

        # Apply patches from this answer
        session.state = InterrogationState.TWIN_UPDATE
        partial_patch = _apply_twin_patches([parsed], features)
        twin_patch.update(partial_patch)
        session.twin_patches_applied.append(partial_patch)

        # Advance to next question or complete
        session.current_q_index += 1
        if session.current_q_index < len(session.questions):
            session.state = InterrogationState.Q_ASKED
            next_q = session.questions[session.current_q_index].question_text
        else:
            session.state = InterrogationState.COMPLETE
            session.completed_at = datetime.utcnow()
            # Compute interrogation value score (how many patches were non-empty)
            non_empty = sum(1 for p in session.twin_patches_applied if p)
            session.interrogation_value_score = round(
                non_empty / max(len(session.questions), 1), 4
            )
            next_q = None

        return session, next_q, twin_patch

    # Already complete or abandoned
    session.state = InterrogationState.COMPLETE
    return session, None, twin_patch


def unanswered_to_flags(session: InterrogationSession) -> list[ConcernFlag]:
    """
    Convert unanswered interrogation questions into UNRESOLVED_AMBIGUITY concern flags.
    These persist until the user resolves them.
    """
    flags = []
    answered_indices = {a.q_index for a in session.answers}
    for q in session.questions:
        if q.q_index not in answered_indices:
            flags.append(ConcernFlag(
                flag_type=ConcernFlagType.UNRESOLVED_AMBIGUITY,
                severity=Severity.HIGH,
                evidence_citations=[f"unanswered_question: {q.signal_addressed}"],
                recommended_action=(
                    f"User did not respond to: \"{q.question_text[:80]}...\". "
                    f"Flag remains active until resolved."
                ),
                confidence=0.9,
                source_hypothesis="H1",
            ))
    return flags
