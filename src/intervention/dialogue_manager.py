"""
Tier 8 — Dialogue Manager (Avatar Chat Intelligence)

Powers natural conversation with the Digital Twin avatar.

Chat flow (tier4_tier8.md §15):
  User query
    → fetch latest twin state + recent history
    → build rich context (metrics, alerts, trends)
    → LLM generates RBI-compliant, empathetic response
    → return to frontend with optional simulation flag

In the prototype, LLM calls are simulated with rule-based template
responses. Production: replace _generate_response() with a call to
Claude / GPT-4o with the context-enriched prompt.

DPDPA 2023 compliance:
  - User is always informed they are speaking to an AI agent
  - All conversations logged via AuditLogger
  - No financial product offers without prior consent
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from src.twin.twin_model import DigitalTwin


_SYSTEM_PROMPT_TEMPLATE = """
You are Airavat, a financial AI assistant powered by the user's Digital Twin.
You are empathetic, honest, and always explain financial concepts in simple terms.
You are NOT a certified financial advisor. Never guarantee returns or promise credit.
Always inform the user you are an AI and their data is handled with full consent.

Current twin state:
  - Risk score: {risk_score:.0%} (lower is better)
  - Liquidity: {liquidity_health}
  - Income stability: {income_stability:.0%}
  - Spending volatility: {spending_volatility:.0%}
  - EMI burden: {emi_burden:.0%} of income
  - Cash buffer: {cash_buffer_days:.1f} days
  - CIBIL-like score: {cibil_score}
  - Persona: {persona}
  - Recent alerts: {recent_alerts}
""".strip()

# ── intent detection ──────────────────────────────────────────────────────────

_INTENT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(liquidity|cash|buffer|survival)", re.I), "liquidity"),
    (re.compile(r"(emi|loan|debt|repay)", re.I), "emi"),
    (re.compile(r"(save|savings|invest|sip|rd)", re.I), "savings"),
    (re.compile(r"(score|cibil|rating|credit)", re.I), "credit_score"),
    (re.compile(r"(spend|expense|budget)", re.I), "spending"),
    (re.compile(r"(future|forecast|next\s+\d+\s+days|predict)", re.I), "forecast"),
    (re.compile(r"(improve|increase|better|boost)", re.I), "improvement"),
    (re.compile(r"(explain|what|why|how)", re.I), "explain"),
]


def _detect_intent(message: str) -> str:
    for pattern, intent in _INTENT_PATTERNS:
        if pattern.search(message):
            return intent
    return "general"


# ── rule-based response templates ────────────────────────────────────────────

def _rule_based_response(message: str, twin: DigitalTwin) -> str:
    """
    Deterministic template response for prototype.
    Replace this function body with an LLM API call in production.
    """
    intent = _detect_intent(message)
    cibil = twin.cibil_like_score()

    if intent == "liquidity":
        if twin.liquidity_health == "LOW":
            return (
                f"Your cash buffer is at {twin.cash_buffer_days:.1f} days — that's LOW. "
                "I'd recommend pausing any non-essential subscriptions and avoiding large "
                "discretionary purchases for the next 10–14 days to rebuild your buffer. "
                "Would you like me to suggest specific areas to cut back?"
            )
        return (
            f"Your cash buffer is {twin.cash_buffer_days:.1f} days — "
            f"that's {twin.liquidity_health}. You have decent runway for now."
        )

    if intent == "emi":
        if twin.emi_burden_ratio > 0.35:
            return (
                f"Your EMI burden is {twin.emi_burden_ratio:.0%} of your income, "
                "which is above the recommended 35% threshold. This can strain your "
                "cash flow. Would you like to explore EMI restructuring options or "
                "understand which loan is most expensive to prepay first?"
            )
        return (
            f"Your EMI burden is {twin.emi_burden_ratio:.0%} — within healthy limits. "
            "Keep maintaining timely payments to build your credit profile."
        )

    if intent == "savings":
        return (
            f"Based on your current income and expense patterns, "
            f"you have a CIBIL-like score of {cibil}. "
            "To improve your savings rate, focus on reducing discretionary spend "
            "in your top merchant categories. Even a 10% reduction can significantly "
            "improve your financial buffer over 90 days."
        )

    if intent == "credit_score":
        band = "Excellent" if cibil >= 750 else "Good" if cibil >= 650 else "Average" if cibil >= 550 else "Needs improvement"
        return (
            f"Your current CIBIL-like score is {cibil} ({band}). "
            f"The biggest factors affecting your score are: "
            f"EMI burden ({twin.emi_burden_ratio:.0%}), "
            f"income stability ({twin.income_stability:.0%}), "
            f"and cash buffer ({twin.cash_buffer_days:.1f} days). "
            "Would you like a personalised improvement plan?"
        )

    if intent == "improvement":
        tips = []
        if twin.emi_burden_ratio > 0.35:
            tips.append("reduce EMI burden below 35% by prepaying the highest-interest loan")
        if twin.cash_buffer_days < 15:
            tips.append(f"build cash buffer from {twin.cash_buffer_days:.1f} to at least 15 days")
        if twin.spending_volatility > 0.5:
            tips.append("reduce spending volatility by setting a weekly budget")
        if not tips:
            tips.append("maintain your current healthy financial habits")
        return "To improve your financial profile: " + "; ".join(tips) + "."

    if intent == "forecast":
        trend = "stable" if abs(twin.spending_volatility - 0.3) < 0.15 else "volatile"
        return (
            f"Based on your last 90 days, your spending pattern is {trend}. "
            f"With current cash buffer of {twin.cash_buffer_days:.1f} days and "
            f"income stability at {twin.income_stability:.0%}, "
            "the next 30 days look manageable — but watch for EMI due dates."
        )

    # default
    return (
        f"I'm your Airavat Digital Twin assistant. Your current financial health: "
        f"CIBIL-like score {cibil}, liquidity {twin.liquidity_health}, "
        f"EMI burden {twin.emi_burden_ratio:.0%}. "
        "Ask me anything about your finances!"
    )


# ── dialogue manager ──────────────────────────────────────────────────────────

class DialogueManager:
    """
    Handles multi-turn chat with the Digital Twin avatar.
    Each conversation turn is context-enriched and auditable.
    """

    def __init__(self) -> None:
        pass  # stateless: context fetched fresh on each turn

    def chat(
        self,
        message: str,
        twin: DigitalTwin,
        recent_triggers: list[str] | None = None,
        *,
        include_simulation: bool = False,
    ) -> dict[str, Any]:
        """
        Process one user message and return the twin's response.

        Returns:
          {
            "role": "twin",
            "content": str,
            "intent": str,
            "includes_simulation": bool,
            "avatar_expression": str,
            "cibil_score": int,
            "ts": str,
          }
        """
        intent = _detect_intent(message)
        response_text = _rule_based_response(message, twin)

        return {
            "role": "twin",
            "content": response_text,
            "intent": intent,
            "includes_simulation": include_simulation,
            "avatar_expression": twin.avatar_state.expression,
            "mood_message": twin.avatar_state.mood_message,
            "cibil_score": twin.cibil_like_score(),
            "ts": datetime.utcnow().isoformat(),
        }

    def build_system_prompt(
        self,
        twin: DigitalTwin,
        recent_triggers: list[str] | None = None,
    ) -> str:
        """
        Build the LLM system prompt with current twin context.
        Use this when swapping in a real LLM call.
        """
        return _SYSTEM_PROMPT_TEMPLATE.format(
            risk_score=twin.risk_score,
            liquidity_health=twin.liquidity_health,
            income_stability=twin.income_stability,
            spending_volatility=twin.spending_volatility,
            emi_burden=twin.emi_burden_ratio,
            cash_buffer_days=twin.cash_buffer_days,
            cibil_score=twin.cibil_like_score(),
            persona=twin.persona,
            recent_alerts=", ".join(recent_triggers or []) or "none",
        )
