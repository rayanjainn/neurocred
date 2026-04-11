"""
Tier 8 — Trigger Engine

Evaluates all intervention triggers against a Digital Twin state
and returns a list of fired TriggerResult objects.

Trigger thresholds follow tier4_tier8.md §3.2:
  - Liquidity Drop:      liquidity_health == LOW  OR  cash_buffer_days < 10
  - Overspend:           spending_volatility > 0.65 AND 7d outbound > 1.3× median
  - EMI-at-Risk:         emi_burden_ratio > 0.35 OR projected_miss_prob > 0.35
  - Lifestyle Inflation: spending_volatility QoQ increase > 25%
  - Savings Opportunity: high credit dependency + idle buffer
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from src.twin.twin_model import DigitalTwin

TriggerType = Literal[
    "liquidity_drop",
    "overspend_warning",
    "emi_at_risk",
    "lifestyle_inflation",
    "savings_opportunity",
    "fraud_anomaly",
    "new_to_credit_guidance",
]

Priority = Literal["HIGH", "MEDIUM", "LOW"]

_TRIGGER_PRIORITY: dict[TriggerType, Priority] = {
    "liquidity_drop": "HIGH",
    "emi_at_risk": "HIGH",
    "fraud_anomaly": "HIGH",
    "overspend_warning": "MEDIUM",
    "lifestyle_inflation": "MEDIUM",
    "savings_opportunity": "LOW",
    "new_to_credit_guidance": "LOW",
}

_TRIGGER_CHANNELS: dict[TriggerType, list[str]] = {
    "liquidity_drop": ["sms", "push"],
    "emi_at_risk": ["sms", "push"],
    "fraud_anomaly": ["push", "sms"],
    "overspend_warning": ["push"],
    "lifestyle_inflation": ["push"],
    "savings_opportunity": ["whatsapp"],
    "new_to_credit_guidance": ["whatsapp"],
}


@dataclass
class TriggerResult:
    trigger_type: TriggerType
    fired: bool
    priority: Priority
    channels: list[str]
    urgency: float          # [0, 1]
    reason: str
    suggested_actions: list[str] = field(default_factory=list)


def evaluate_triggers(
    twin: DigitalTwin,
    prev_spending_volatility: float | None = None,
) -> list[TriggerResult]:
    """
    Evaluate all triggers for a twin state.
    `prev_spending_volatility` is from a recent historical snapshot
    (used for lifestyle inflation QoQ detection).

    Returns only fired triggers, sorted HIGH → MEDIUM → LOW priority.
    """
    results: list[TriggerResult] = []

    # ── 1. Liquidity Drop ──────────────────────────────────────────────────
    if twin.liquidity_health == "LOW" or twin.cash_buffer_days < 10.0:
        urgency = 0.9 if twin.liquidity_health == "LOW" else 0.7
        results.append(TriggerResult(
            trigger_type="liquidity_drop",
            fired=True,
            priority="HIGH",
            channels=_TRIGGER_CHANNELS["liquidity_drop"],
            urgency=urgency,
            reason=f"Cash buffer at {twin.cash_buffer_days:.1f} days (threshold: 10)",
            suggested_actions=[
                "Review non-essential subscriptions",
                "Defer discretionary spends for 7 days",
                "Consider a short-term liquidity buffer via pre-qualified credit",
            ],
        ))

    # ── 2. Overspend Warning ───────────────────────────────────────────────
    if twin.spending_volatility > 0.65:
        urgency = min(0.9, twin.spending_volatility)
        results.append(TriggerResult(
            trigger_type="overspend_warning",
            fired=True,
            priority="MEDIUM",
            channels=_TRIGGER_CHANNELS["overspend_warning"],
            urgency=urgency,
            reason=f"Spending volatility at {twin.spending_volatility:.2f} (threshold: 0.65)",
            suggested_actions=[
                "Set a weekly spending cap",
                "Review top 3 merchant categories",
            ],
        ))

    # ── 3. EMI-at-Risk ─────────────────────────────────────────────────────
    if twin.emi_burden_ratio > 0.35:
        urgency = min(0.95, twin.emi_burden_ratio)
        results.append(TriggerResult(
            trigger_type="emi_at_risk",
            fired=True,
            priority="HIGH",
            channels=_TRIGGER_CHANNELS["emi_at_risk"],
            urgency=urgency,
            reason=f"EMI burden at {twin.emi_burden_ratio:.0%} of income (threshold: 35%)",
            suggested_actions=[
                "Request EMI restructuring with lender",
                "Reduce discretionary spend to build buffer",
                "Explore balance transfer for lower EMI",
            ],
        ))

    # ── 4. Lifestyle Inflation ─────────────────────────────────────────────
    if prev_spending_volatility is not None:
        qoq_increase = (twin.spending_volatility - prev_spending_volatility) / max(prev_spending_volatility, 0.01)
        if qoq_increase > 0.25:
            results.append(TriggerResult(
                trigger_type="lifestyle_inflation",
                fired=True,
                priority="MEDIUM",
                channels=_TRIGGER_CHANNELS["lifestyle_inflation"],
                urgency=0.5,
                reason=f"Spending volatility rose {qoq_increase:.0%} QoQ (threshold: 25%)",
                suggested_actions=[
                    "Review discretionary spend categories",
                    "Set savings target for next quarter",
                ],
            ))

    # ── 5. Savings Opportunity ─────────────────────────────────────────────
    if (
        twin.cash_buffer_days > 20.0
        and twin.emi_burden_ratio < 0.25
        and twin.risk_score < 0.35
    ):
        results.append(TriggerResult(
            trigger_type="savings_opportunity",
            fired=True,
            priority="LOW",
            channels=_TRIGGER_CHANNELS["savings_opportunity"],
            urgency=0.2,
            reason="Strong liquidity buffer with low burden — savings opportunity detected",
            suggested_actions=[
                "Consider SIP/RD with idle buffer",
                "Pre-pay high-interest EMI to save on interest",
            ],
        ))

    # ── 6. Fraud / Anomaly ─────────────────────────────────────────────────
    if twin.persona == "shell_circular":
        results.append(TriggerResult(
            trigger_type="fraud_anomaly",
            fired=True,
            priority="HIGH",
            channels=_TRIGGER_CHANNELS["fraud_anomaly"],
            urgency=0.95,
            reason="Circular trading / shell pattern detected in transaction graph",
            suggested_actions=[
                "Account flagged for manual review",
                "Credit offers suspended pending review",
            ],
        ))

    # ── 7. New-to-Credit Guidance ──────────────────────────────────────────
    if twin.persona == "new_to_credit":
        results.append(TriggerResult(
            trigger_type="new_to_credit_guidance",
            fired=True,
            priority="LOW",
            channels=_TRIGGER_CHANNELS["new_to_credit_guidance"],
            urgency=0.1,
            reason="Thin credit file detected — guidance mode active",
            suggested_actions=[
                "Build credit history with a secured credit card",
                "Ensure salary is credited to this account regularly",
                "Maintain 3 months of consistent digital transactions",
            ],
        ))

    # Sort: HIGH first, then MEDIUM, then LOW
    _order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    results.sort(key=lambda t: (_order[t.priority], -t.urgency))
    return results


def compute_relevance_score(
    trigger: TriggerResult,
    personalization: float = 0.5,
    acceptance_history: float = 0.5,
    safety_factor: float = 1.0,
) -> float:
    """
    tier4_tier8.md §3.2:
      relevance = 0.4×urgency + 0.3×personalization + 0.2×acceptance_history + 0.1×safety_factor
    Only fires notification if relevance ≥ 0.75.
    """
    return (
        0.4 * trigger.urgency
        + 0.3 * personalization
        + 0.2 * acceptance_history
        + 0.1 * safety_factor
    )
