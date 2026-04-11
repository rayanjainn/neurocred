"""
Tier 8 — Report Generator

Produces end-of-day and weekly financial summaries for delivery
via WhatsApp / SMS (tier4_tier8.md §14).

Report flow:
  1. Aggregate current twin state + recent changes + triggered alerts
  2. Generate plain-language summary: risk status, key insights, actions
  3. Serialise to structured dict for multi-channel delivery

DPDPA 2023: reports only sent to consented users via consented channels.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from src.twin.twin_model import DigitalTwin

ReportType = Literal["daily_summary", "weekly_summary"]


def _derive_insights(twin: DigitalTwin) -> list[str]:
    insights: list[str] = []
    cibil = twin.cibil_like_score()
    insights.append(f"CIBIL-like score: {cibil}")

    if twin.liquidity_health == "LOW":
        insights.append(f"⚠ Liquidity is LOW — cash buffer {twin.cash_buffer_days:.1f} days")
    elif twin.liquidity_health == "MEDIUM":
        insights.append(f"Cash buffer at {twin.cash_buffer_days:.1f} days (MEDIUM)")
    else:
        insights.append(f"Cash buffer healthy: {twin.cash_buffer_days:.1f} days")

    if twin.emi_burden_ratio > 0.35:
        insights.append(f"⚠ EMI burden high: {twin.emi_burden_ratio:.0%} of income")
    else:
        insights.append(f"EMI burden in control: {twin.emi_burden_ratio:.0%}")

    if twin.spending_volatility > 0.65:
        insights.append(f"⚠ Spending volatility elevated: {twin.spending_volatility:.0%}")

    if twin.income_stability > 0.75:
        insights.append(f"Income stable: {twin.income_stability:.0%} consistency")
    elif twin.income_stability < 0.4:
        insights.append(f"⚠ Income irregular: {twin.income_stability:.0%} consistency")

    return insights


def _derive_actions(twin: DigitalTwin) -> list[str]:
    actions: list[str] = []
    if twin.cash_buffer_days < 10:
        actions.append("Reduce non-essential spend to rebuild cash buffer")
    if twin.emi_burden_ratio > 0.35:
        actions.append("Contact lender to explore EMI restructuring")
    if twin.spending_volatility > 0.65:
        actions.append("Review top spending categories and set a weekly budget")
    if twin.income_stability < 0.4:
        actions.append("Diversify income streams or ensure salary credits are regular")
    if not actions:
        actions.append("Maintain your current healthy financial habits")
    return actions


def generate_report(
    twin: DigitalTwin,
    report_type: ReportType = "daily_summary",
    report_date: date | None = None,
    app_url: str = "https://app.airavat.in",
) -> dict[str, Any]:
    """
    Build a structured report dict.
    Same structure as tier4_tier8.md §17.3.
    """
    if report_date is None:
        report_date = date.today()

    insights = _derive_insights(twin)
    actions = _derive_actions(twin)

    # Risk status label
    cibil = twin.cibil_like_score()
    if cibil >= 750:
        risk_label = "Excellent"
    elif cibil >= 650:
        risk_label = "Good"
    elif cibil >= 550:
        risk_label = "Average"
    else:
        risk_label = "Needs Attention"

    return {
        "report_type": report_type,
        "user_id": twin.user_id,
        "date": report_date.isoformat(),
        "risk_status": risk_label,
        "cibil_like_score": cibil,
        "liquidity_health": twin.liquidity_health,
        "twin_version": twin.version,
        "key_insights": insights,
        "suggested_actions": actions,
        "avatar_expression": twin.avatar_state.expression,
        "full_report_link": f"{app_url}/report/{report_date.strftime('%Y%m%d')}?uid={twin.user_id}",
        "generated_at": datetime.utcnow().isoformat(),
        "opt_out_note": "Reply STOP to unsubscribe from automated reports.",
    }


def format_whatsapp_message(report: dict[str, Any]) -> str:
    """Render a report dict into a WhatsApp-friendly plain-text message."""
    lines = [
        f"*Airavat Daily Report — {report['date']}*",
        f"Score: {report['cibil_like_score']} ({report['risk_status']})",
        f"Liquidity: {report['liquidity_health']}",
        "",
        "*Key Insights:*",
    ]
    for ins in report["key_insights"]:
        lines.append(f"• {ins}")
    lines.append("")
    lines.append("*Suggested Actions:*")
    for act in report["suggested_actions"]:
        lines.append(f"→ {act}")
    lines.append(f"\nFull report: {report['full_report_link']}")
    lines.append(f"\n_{report['opt_out_note']}_")
    return "\n".join(lines)


def format_sms_message(report: dict[str, Any]) -> str:
    """Render a compact SMS (≤160 chars ideally)."""
    return (
        f"Airavat: Score {report['cibil_like_score']}, "
        f"Liquidity {report['liquidity_health']}. "
        f"{report['suggested_actions'][0] if report['suggested_actions'] else 'Stay on track!'}. "
        f"Details: {report['full_report_link']}"
    )
