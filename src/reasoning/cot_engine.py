"""
Tier 5 — Structured CoT Engine (Module 2)

Calls OpenRouter (same key as CreditIQ uses) with a structured 6-step
chain-of-thought prompt. Returns a fully parsed CoTTrace + the four
primary outputs (narrative, behav delta, intent signals, concern flags).

The LLM is asked to produce JSON — we parse and validate with Pydantic.
On parse failure, a deterministic fallback based purely on feature thresholds
is used (no silent failure).
"""

from __future__ import annotations

import json
import time
import uuid
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from typing import Any, Optional

from config.settings import settings
from src.features.schemas import BehaviouralFeatureVector
from src.reasoning.context_assembler import AssembledContext
from src.reasoning.schemas import (
    BehavDeltaItem,
    BehaviouralChangeSummary,
    ConcernFlag,
    ConcernFlagType,
    CoTTrace,
    FinancialSituation,
    Hypothesis,
    IntentSignal,
    IntentSignalType,
    Severity,
)


# ── System Prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """
You are an advanced financial reasoning agent for Airavat — India's AI-native credit intelligence platform.
Your role is NOT to write text fluently — your role is to REASON RIGOROUSLY about a user's financial state.

## Brand Voice (for the risk_narrative field ONLY)
- Present-tense verdict first.
- Causal factor second.
- Trajectory third.
- Optional action fourth.
- 2-4 sentences maximum. Plain language, no jargon.
- Never say "you may" or "perhaps" — state the finding directly.

## Output MUST be valid JSON matching this exact schema:
{
  "observe": "string — list the exact numeric signals you see, no interpretation",
  "classify": "STABLE_IMPROVING | STABLE_FLAT | STABLE_DEGRADING | STRESSED_RECOVERABLE | STRESSED_CRITICAL | CRISIS_ACUTE | CRISIS_SYSTEMIC | ANOMALOUS_UNCLASSIFIABLE",
  "hypotheses": [
    {"id": "H1", "statement": "string", "prior_probability": 0.0, "posterior_probability": 0.0,
     "confirming_evidence": ["..."], "disconfirming_evidence": ["..."]}
  ],
  "test_summary": "string — cite specific feature values or event IDs as evidence for hypothesis selection",
  "winning_hypothesis_id": "H1",
  "synthesize_reasoning": "string — why the winning hypothesis explains the pattern",
  "confidence": 0.0,
  "trigger_interrogation": false,
  "risk_narrative": "string — 2-4 sentence brand-voice narrative",
  "behavioural_change_summary": {
    "improved": [{"feature": "string", "direction": "improved", "change_pct": 0.0, "color": "green"}],
    "degraded": [{"feature": "string", "direction": "degraded", "change_pct": 0.0, "color": "red"}],
    "stable": [],
    "net_direction": "improving | degrading | flat",
    "source_hypothesis": "H1"
  },
  "intent_signals": [
    {"signal_type": "LARGE_PURCHASE_IMMINENT | NEW_CREDIT_SEEKING | INCOME_TRANSITION | EMI_STRESS_IMMINENT | CASH_DEPENDENCY_RISING",
     "probability": 0.0, "reasoning": "string", "source_hypothesis": "H1"}
  ],
  "concern_flags": [
    {"flag_type": "INCOME_CONTRADICTION | HIGH_CASCADE_RISK | EMI_OVERLOAD | LIQUIDITY_CRISIS | FRAUD_ANOMALY | LIFESTYLE_INFLATION | UNRESOLVED_AMBIGUITY | CIRCULAR_FLOW_DETECTED | SALARY_IRREGULARITY",
     "severity": "LOW | MEDIUM | HIGH | CRITICAL",
     "evidence_citations": ["feature: value"],
     "recommended_action": "string",
     "confidence": 0.0,
     "source_hypothesis": "H1"}
  ]
}

CRITICAL RULES:
- concern_flags MUST have maximum 5 entries, ranked by severity × confidence
- intent_signals MUST have maximum 3 entries
- hypotheses MUST have exactly 2 or 3 entries, prior probabilities MUST sum to 1.0
- trigger_interrogation = true ONLY if max posterior probability < 0.55
- Output ONLY the JSON object. No markdown. No explanation outside the JSON.
""".strip()


def _call_openrouter(user_content: str, model: Optional[str] = None) -> str:
    """Direct OpenRouter API call. Returns raw content string."""
    api_key = settings.openrouter_api_key
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set in environment")

    model = model or settings.llm_model

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,   # low temperature for structured reasoning
        "max_tokens": 2048,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://airavat.in",
            "X-Title": "Airavat Tier 5 Reasoning",
        },
        data=payload,
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
        return data["choices"][0]["message"]["content"]


def _extract_json(raw: str) -> dict:
    """Strip markdown fences and parse JSON from LLM output."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:])
        if raw.endswith("```"):
            raw = raw[:-3]
    return json.loads(raw)


def _build_fallback_cot(features: BehaviouralFeatureVector) -> dict:
    """
    Deterministic fallback when LLM is unavailable or returns unparseable JSON.
    Based purely on feature thresholds from schema.md.
    """
    emi = features.emi_burden_ratio
    cash = features.cash_buffer_days
    failure = features.debit_failure_rate_90d
    savings = features.savings_rate

    # Classify situation
    if emi > 0.55 or failure > 0.15 or cash < 5:
        classify = "STRESSED_CRITICAL"
        narrative = (
            f"Financial stress is elevated. EMI burden ({emi:.0%}) has exceeded the 55% threshold "
            f"and debit failure rate is {failure:.0%}. Without corrective action, "
            f"cash reserves may deplete within {max(int(cash), 1)} days."
        )
    elif emi > 0.40 or savings < 0.05:
        classify = "STRESSED_RECOVERABLE"
        narrative = (
            f"Mild financial stress is present. EMI commitments are consuming {emi:.0%} of income "
            f"and savings rate has compressed to {savings:.0%}. "
            f"Reducing discretionary spending now can prevent escalation."
        )
    elif savings > 0.15 and emi < 0.30 and cash > 20:
        classify = "STABLE_IMPROVING"
        narrative = (
            f"Financial health is stable with positive trajectory. "
            f"Savings rate at {savings:.0%} and {cash:.0f}-day cash buffer are above peer cohort benchmarks. "
            f"Keep tracking to maintain this position."
        )
    else:
        classify = "STABLE_FLAT"
        narrative = (
            f"Financial position is stable with no significant movements. "
            f"EMI burden at {emi:.0%} and cash buffer at {cash:.0f} days are within normal ranges."
        )

    concern_flags = []
    if emi > 0.55:
        concern_flags.append({
            "flag_type": "EMI_OVERLOAD", "severity": "HIGH",
            "evidence_citations": [f"emi_burden_ratio: {emi:.4f}"],
            "recommended_action": "Review and consolidate EMI obligations.",
            "confidence": 0.9, "source_hypothesis": "H1"
        })
    if cash < 7:
        concern_flags.append({
            "flag_type": "LIQUIDITY_CRISIS", "severity": "CRITICAL",
            "evidence_citations": [f"cash_buffer_days: {cash:.1f}"],
            "recommended_action": "Immediate liquidity injection required. Delay non-essential payments.",
            "confidence": 0.95, "source_hypothesis": "H1"
        })

    return {
        "observe": (
            f"emi_burden_ratio: {emi:.4f} | savings_rate: {savings:.4f} | "
            f"cash_buffer_days: {cash:.1f} | debit_failure_rate_90d: {failure:.4f} | "
            f"income_stability_score: {features.income_stability_score:.4f} | "
            f"spending_volatility_index: {features.spending_volatility_index:.4f}"
        ),
        "classify": classify,
        "hypotheses": [
            {"id": "H1", "statement": "Current pattern is driven by structural financial constraints.",
             "prior_probability": 0.7, "posterior_probability": 0.7,
             "confirming_evidence": [f"emi_burden_ratio={emi:.3f}", f"savings_rate={savings:.3f}"],
             "disconfirming_evidence": []},
            {"id": "H2", "statement": "Pattern is temporary and driven by a one-off event.",
             "prior_probability": 0.3, "posterior_probability": 0.3,
             "confirming_evidence": [], "disconfirming_evidence": [f"sustained over 90d window"]},
        ],
        "test_summary": "Threshold-based deterministic fallback — LLM unavailable.",
        "winning_hypothesis_id": "H1",
        "synthesize_reasoning": "Feature thresholds exceed critical bands, corroborating H1.",
        "confidence": 0.65,
        "trigger_interrogation": False,
        "risk_narrative": narrative,
        "behavioural_change_summary": {
            "improved": [], "degraded": [], "stable": [],
            "net_direction": "flat", "source_hypothesis": "H1"
        },
        "intent_signals": [],
        "concern_flags": concern_flags[:5],
    }


def run_cot_engine(
    features: BehaviouralFeatureVector,
    context: AssembledContext,
) -> tuple[CoTTrace, str, BehaviouralChangeSummary, list[IntentSignal], list[ConcernFlag]]:
    """
    Call the LLM with the assembled context and parse the structured 6-step CoT.

    Returns:
        (CoTTrace, risk_narrative, BehaviouralChangeSummary, [IntentSignal], [ConcernFlag])
    """
    user_content = f"""
Analyse this user's financial digital twin state and produce a structured reasoning trace.

{context.to_prompt_section()}

=== [CURRENT FEATURE SNAPSHOT] ===
  EMI burden ratio:       {features.emi_burden_ratio:.4f}
  Savings rate:           {features.savings_rate:.4f}
  Income stability:       {features.income_stability_score:.4f}
  Spending volatility:    {features.spending_volatility_index:.4f}
  Cash buffer days:       {features.cash_buffer_days:.1f}
  Debit failure rate 90d: {features.debit_failure_rate_90d:.4f}
  Discretionary ratio:    {features.discretionary_ratio:.4f}
  Lifestyle inflation:    {features.lifestyle_inflation_trend:.4f}
  Peer cohort deviation:  {features.peer_cohort_benchmark_deviation:.4f}
  Top3 concentration:     {features.top3_merchant_concentration:.4f}
  Cash dependency:        {features.cash_dependency_index:.4f}
  EMI count (90d):        {features.emi_payment_count_90d}
  Category shift count:   {features.merchant_category_shift_count}
  Anomaly flag:           {features.anomaly_flag}
  Income 90d:             ₹{features.income_90d:,.0f}
  Income 30d:             ₹{features.income_30d:,.0f}
  Net cashflow 30d:       ₹{features.net_cashflow_30d:,.0f}

Produce the complete reasoning JSON now.
""".strip()

    fallback = False
    raw_response: dict = {}
    model_used = settings.llm_model

    for attempt in range(3):
        try:
            raw = _call_openrouter(user_content, model_used)
            raw_response = _extract_json(raw)
            break
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 ** attempt)
                continue
            raw_response = _build_fallback_cot(features)
            fallback = True
            break
        except Exception:
            raw_response = _build_fallback_cot(features)
            fallback = True
            break
    else:
        raw_response = _build_fallback_cot(features)
        fallback = True

    # ── Parse CoT Trace ───────────────────────────────────────────────────────
    hypotheses = [
        Hypothesis(
            id=h.get("id", f"H{i+1}"),
            statement=h.get("statement", ""),
            prior_probability=float(h.get("prior_probability", 0.5)),
            posterior_probability=float(h.get("posterior_probability", 0.5)),
            confirming_evidence=h.get("confirming_evidence", []),
            disconfirming_evidence=h.get("disconfirming_evidence", []),
        )
        for i, h in enumerate(raw_response.get("hypotheses", []))
    ]

    try:
        situation = FinancialSituation(raw_response.get("classify", "ANOMALOUS_UNCLASSIFIABLE"))
    except ValueError:
        situation = FinancialSituation.ANOMALOUS_UNCLASSIFIABLE

    cot = CoTTrace(
        observe=raw_response.get("observe", ""),
        classify=situation,
        hypothesize=hypotheses,
        test_summary=raw_response.get("test_summary", ""),
        winning_hypothesis_id=raw_response.get("winning_hypothesis_id", "H1"),
        synthesize_reasoning=raw_response.get("synthesize_reasoning", ""),
        confidence=float(raw_response.get("confidence", 0.5)),
        trigger_interrogation=bool(raw_response.get("trigger_interrogation", False)),
        model_used="" if fallback else model_used,
        token_budget_used=context.total_tokens_used,
    )

    # ── Parse Narrative ────────────────────────────────────────────────────────
    risk_narrative = raw_response.get("risk_narrative", "Financial analysis in progress.")

    # ── Parse Behavioural Delta ───────────────────────────────────────────────
    bcs_raw = raw_response.get("behavioural_change_summary", {})

    def _parse_delta_items(items: list) -> list[BehavDeltaItem]:
        result = []
        for item in items:
            try:
                result.append(BehavDeltaItem(
                    feature=item.get("feature", "unknown"),
                    direction=item.get("direction", "stable"),
                    change_pct=float(item.get("change_pct", 0.0)),
                    color=item.get("color", "neutral"),
                ))
            except Exception:
                pass
        return result

    bcs = BehaviouralChangeSummary(
        improved=_parse_delta_items(bcs_raw.get("improved", [])),
        degraded=_parse_delta_items(bcs_raw.get("degraded", [])),
        stable=_parse_delta_items(bcs_raw.get("stable", [])),
        net_direction=bcs_raw.get("net_direction", "flat"),
        source_hypothesis=bcs_raw.get("source_hypothesis", "H1"),
    )

    # ── Parse Intent Signals ──────────────────────────────────────────────────
    expiry = datetime.utcnow() + timedelta(days=30)
    intent_signals: list[IntentSignal] = []
    for sig in raw_response.get("intent_signals", [])[:3]:
        try:
            intent_signals.append(IntentSignal(
                signal_type=IntentSignalType(sig.get("signal_type", "LARGE_PURCHASE_IMMINENT")),
                probability=float(sig.get("probability", 0.5)),
                expires_at=expiry,
                reasoning=sig.get("reasoning", ""),
                source_hypothesis=sig.get("source_hypothesis", "H1"),
            ))
        except (ValueError, Exception):
            pass

    # ── Parse Concern Flags ────────────────────────────────────────────────────
    concern_flags: list[ConcernFlag] = []
    for flag in raw_response.get("concern_flags", [])[:5]:
        try:
            concern_flags.append(ConcernFlag(
                flag_type=ConcernFlagType(flag.get("flag_type", "UNRESOLVED_AMBIGUITY")),
                severity=Severity(flag.get("severity", "LOW")),
                evidence_citations=flag.get("evidence_citations", []),
                recommended_action=flag.get("recommended_action", ""),
                confidence=float(flag.get("confidence", 0.5)),
                source_hypothesis=flag.get("source_hypothesis", "H1"),
            ))
        except (ValueError, Exception):
            pass

    # Sort concern flags by severity × confidence
    severity_order = {Severity.CRITICAL: 4, Severity.HIGH: 3, Severity.MEDIUM: 2, Severity.LOW: 1}
    concern_flags.sort(
        key=lambda x: severity_order.get(x.severity, 0) * x.confidence,
        reverse=True,
    )

    return cot, risk_narrative, bcs, intent_signals, concern_flags[:5]
