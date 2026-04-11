"""
Tier 6 — Early Warning Score (EWS)

EWS measures fraction of paths approaching crisis threshold *before* it materialises.

  EWS(d) = (1/N) × Σ 𝟙[ min_{t∈[1,d]} C_t^(k) < θ_warning ]

  θ_warning = 0.5 × monthly_emi_total

Computed at three horizons: 7-day, 14-day, 30-day.

EWS Severity Bands:
  GREEN:  0.00 – 0.15  — no action
  AMBER:  0.15 – 0.30  — soft nudge
  ORANGE: 0.30 – 0.55  — EMI-at-risk alert + micro-loan pre-qualify
  RED:    > 0.55        — immediate intervention + human escalation

When EWS(14) > 0.30, Tier 8 Intervention Agent is triggered.
"""

from __future__ import annotations

from typing import Literal

import numpy as np

EWSSeverity = Literal["GREEN", "AMBER", "ORANGE", "RED"]

_SEVERITY_THRESHOLDS = [
    (0.00, 0.15, "GREEN"),
    (0.15, 0.30, "AMBER"),
    (0.30, 0.55, "ORANGE"),
    (0.55, 1.01, "RED"),
]


def compute_ews(
    cash_paths: np.ndarray,         # shape (N, horizon)
    monthly_emi_total: float,
    horizon_days: int = 30,
) -> float:
    """
    Compute EWS(horizon_days) from cash path matrix.

    Args:
        cash_paths: shape (N, H) — daily cash balance per path
        monthly_emi_total: warning threshold = 0.5 × this value
        horizon_days: evaluate paths up to this day (max = H)

    Returns:
        float in [0, 1] — fraction of paths that breach warning threshold
    """
    theta = 0.5 * monthly_emi_total
    n, h = cash_paths.shape
    d = min(horizon_days, h)
    # Min cash over [0, d) per path
    min_cash = np.min(cash_paths[:, :d], axis=1)  # shape (N,)
    return float(np.mean(min_cash < theta))


def classify_severity(ews_14d: float) -> EWSSeverity:
    for lo, hi, label in _SEVERITY_THRESHOLDS:
        if lo <= ews_14d < hi:
            return label  # type: ignore[return-value]
    return "RED"


def trigger_recommendation(severity: EWSSeverity) -> str:
    return {
        "GREEN":  "NO_ACTION",
        "AMBER":  "SOFT_NUDGE",
        "ORANGE": "EMI_AT_RISK_ALERT + MICRO_LOAN_PRE_QUALIFY",
        "RED":    "IMMEDIATE_INTERVENTION + HUMAN_ESCALATION",
    }[severity]


def compute_full_ews(
    cash_paths: np.ndarray,
    monthly_emi_total: float,
) -> dict:
    """
    Compute EWS at 7d, 14d, 30d horizons plus severity and trigger recommendation.

    Returns dict matching §15.2 simulation response shape.
    """
    ews_7d  = compute_ews(cash_paths, monthly_emi_total, 7)
    ews_14d = compute_ews(cash_paths, monthly_emi_total, 14)
    ews_30d = compute_ews(cash_paths, monthly_emi_total, 30)
    severity = classify_severity(ews_14d)

    return {
        "ews_7d":                round(ews_7d,  4),
        "ews_14d":               round(ews_14d, 4),
        "ews_30d":               round(ews_30d, 4),
        "severity":              severity,
        "trigger_recommendation": trigger_recommendation(severity),
    }


def compute_leading_indicators(
    cash_paths: np.ndarray,
    spending_volatility_change: float = 0.0,
    recent_debit_failures: int = 0,
    avg_daily_burn: float = 0.0,
) -> list[str]:
    """
    Human-readable leading indicator strings for EWS streaming endpoint.
    """
    indicators: list[str] = []
    if spending_volatility_change > 0.10:
        pct = round(spending_volatility_change * 100)
        indicators.append(f"Spending volatility up {pct}% vs 30d baseline")
    if recent_debit_failures > 0:
        indicators.append(f"{recent_debit_failures} debit failure(s) in last 7 days")
    if avg_daily_burn > 0:
        indicators.append(f"Cash buffer declining at ₹{avg_daily_burn:,.0f}/day average")
    if not indicators:
        indicators.append("No significant leading indicators detected")
    return indicators
