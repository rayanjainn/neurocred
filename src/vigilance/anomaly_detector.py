"""
Tier 9 — Module 5: Behavioural Anomaly Detection

Three sub-modules:
  5.1 Hidden Financial Stress   — Logistic regression on rolling cash-buffer/debit-failure trends
  5.2 Progressive Income Underreporting — Sigmoid scoring against cohort-normalised observed income
  5.3 Identity & Behaviour Shifts — JS-Divergence on category-mix histograms

All purely statistical — no model training required at runtime. Designed for
<10ms per-user compute using Polars-style calculations (implemented with stdlib
math for zero-dependency portability).

Outputs feed directly into Tier 7 Trust Score as calibrated signals.
"""

from __future__ import annotations

import math
from typing import Optional

from src.features.schemas import BehaviouralFeatureVector
from src.vigilance.schemas import (
    IdentityShiftResult,
    IncomeUnderreportResult,
    RiskLevel,
    StressSignalResult,
)


# ─────────────────────────────────────────────────────────────────────────────
# Module 5.1 — Hidden Financial Stress
# ─────────────────────────────────────────────────────────────────────────────

# Logistic regression weights (trained on synthetic stress labels;
# calibrated to produce P(stress) ≈ prior rate in healthy population)
_STRESS_WEIGHTS = {
    "debit_failure_rate_90d":     +3.5,
    "cash_buffer_days_inv":       +2.8,    # inverted: low buffer = high stress
    "end_of_month_liquidity_dip": +1.5,
    "emi_burden_ratio":           +2.2,
    "spending_volatility_index":  +1.0,
    "income_stability_neg":       +2.5,    # inverted: low stability = high stress
    "_bias":                      -4.5,    # anchors prior at ~5% stress rate
}


def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def run_stress_detector(fv: BehaviouralFeatureVector) -> StressSignalResult:
    """
    Module 5.1: Logistic regression stress signal.

    Features are min-max normalised to [0,1] before applying weights
    so coefficient magnitudes are comparable.
    """
    # Normalise each feature against plausible max values
    normalised = {
        "debit_failure_rate_90d":     min(fv.debit_failure_rate_90d / 0.5, 1.0),
        "cash_buffer_days_inv":       max(0.0, 1.0 - fv.cash_buffer_days / 90.0),
        "end_of_month_liquidity_dip": min(abs(fv.end_of_month_liquidity_dip) / 50_000, 1.0),
        "emi_burden_ratio":           min(fv.emi_burden_ratio / 0.8, 1.0),
        "spending_volatility_index":  min(fv.spending_volatility_index / 2.0, 1.0),
        "income_stability_neg":       max(0.0, 1.0 - fv.income_stability_score),
    }

    log_odds = _STRESS_WEIGHTS["_bias"]
    for feat, weight in _STRESS_WEIGHTS.items():
        if feat == "_bias":
            continue
        log_odds += weight * normalised[feat]

    stress_score = _sigmoid(log_odds)

    # Velocity stress spike: debit failures spiking + liquidity dip together
    velocity_spike = (
        fv.debit_failure_rate_90d > 0.10
        and abs(fv.end_of_month_liquidity_dip) > 10_000
    )

    # Cash buffer trend label
    if fv.cash_buffer_days < 5:
        buffer_trend = "critical"
    elif fv.cash_buffer_days < 10:
        buffer_trend = "declining"
    elif fv.cash_buffer_days < 20:
        buffer_trend = "stable"
    else:
        buffer_trend = "improving"

    # Debit failure trend label
    if fv.debit_failure_rate_90d > 0.15:
        failure_trend = "critical"
    elif fv.debit_failure_rate_90d > 0.07:
        failure_trend = "declining"
    else:
        failure_trend = "stable"

    if stress_score >= 0.70:
        risk = RiskLevel.CRITICAL
    elif stress_score >= 0.45:
        risk = RiskLevel.HIGH
    elif stress_score >= 0.20:
        risk = RiskLevel.MEDIUM
    else:
        risk = RiskLevel.LOW

    return StressSignalResult(
        user_id=fv.user_id,
        stress_confidence_score=round(stress_score, 4),
        velocity_stress_spike=velocity_spike,
        cash_buffer_trend=buffer_trend,
        debit_failure_trend=failure_trend,
        rolling_features={
            "debit_failure_rate_90d": round(fv.debit_failure_rate_90d, 4),
            "cash_buffer_days": round(fv.cash_buffer_days, 2),
            "emi_burden_ratio": round(fv.emi_burden_ratio, 4),
            "end_of_month_liquidity_dip": round(fv.end_of_month_liquidity_dip, 2),
            "income_stability_score": round(fv.income_stability_score, 4),
        },
        risk_level=risk,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Module 5.2 — Progressive Income Underreporting
# ─────────────────────────────────────────────────────────────────────────────

def run_income_underreport_detector(
    fv: BehaviouralFeatureVector,
    declared_income: float,
    cohort_mean_income: float,
    cohort_std_income: float,
) -> IncomeUnderreportResult:
    """
    Module 5.2: Sigmoid-based income underreporting detector.

    income_underreport_score = sigmoid((observed - declared) / std_peer_income)

    Score > 0.65 → probable underreporting; adapted for project/seasonal MSMEs
    via cohort normalisation.

    Args:
        fv:                 BehaviouralFeatureVector for the user
        declared_income:    Monthly income declared at onboarding
        cohort_mean_income: Mean monthly income for this user's peer cohort
        cohort_std_income:  Std-dev of monthly income within peer cohort
    """
    # Observed income proxy: non-P2P credits in 90d / 3 months
    # Approximation: use income_90d as the base, reduce by cash_dependency (proxy for P2P)
    p2p_fraction    = min(fv.cash_dependency_index * 1.5, 0.9)
    observed_proxy  = (fv.income_90d / 3.0) * (1.0 - p2p_fraction)
    observed_proxy  = max(observed_proxy, 0.0)

    if declared_income <= 0:
        declared_income = cohort_mean_income or 1.0

    # Z-score relative to peer cohort std
    std = cohort_std_income if cohort_std_income > 100 else max(declared_income * 0.3, 1000)
    zscore = (observed_proxy - declared_income) / (std + 1e-9)

    # Sigmoid: positive z-score = observed > declared = underreporting
    score = _sigmoid(zscore)
    is_underreporting = score >= 0.65

    if score >= 0.80:
        risk = RiskLevel.CRITICAL
    elif score >= 0.65:
        risk = RiskLevel.HIGH
    elif score >= 0.50:
        risk = RiskLevel.MEDIUM
    else:
        risk = RiskLevel.LOW

    return IncomeUnderreportResult(
        user_id=fv.user_id,
        income_underreport_score=round(score, 4),
        is_underreporting=is_underreporting,
        observed_income_proxy=round(observed_proxy, 2),
        declared_income_proxy=round(declared_income, 2),
        cohort_std_income=round(std, 2),
        zscore=round(zscore, 4),
        risk_level=risk,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Module 5.3 — Identity & Behaviour Shift
# ─────────────────────────────────────────────────────────────────────────────

def _js_divergence(p: list[float], q: list[float]) -> float:
    """
    Jensen-Shannon divergence between two probability distributions.
    p = 30d category mix, q = 90d category mix.
    JSD ∈ [0, log(2)] — normalised to [0, 1] by dividing by log(2).
    """
    if not p or not q or len(p) != len(q):
        return 0.0

    # Normalise to sum = 1
    sum_p = sum(p) or 1.0
    sum_q = sum(q) or 1.0
    p = [x / sum_p for x in p]
    q = [x / sum_q for x in q]

    m = [(pi + qi) / 2.0 for pi, qi in zip(p, q)]

    def kl(a: list[float], b: list[float]) -> float:
        acc = 0.0
        for ai, bi in zip(a, b):
            if ai > 1e-10 and bi > 1e-10:
                acc += ai * math.log(ai / bi)
        return acc

    jsd = 0.5 * kl(p, m) + 0.5 * kl(q, m)
    return round(min(jsd / math.log(2), 1.0), 4)


def run_identity_shift_detector(
    fv: BehaviouralFeatureVector,
    category_mix_30d: Optional[list[float]] = None,
    category_mix_90d: Optional[list[float]] = None,
) -> IdentityShiftResult:
    """
    Module 5.3: JS-Divergence + feature-based identity shift scoring.

    Args:
        fv:               BehaviouralFeatureVector for the user
        category_mix_30d: Fractional spend per category (last 30d)
        category_mix_90d: Fractional spend per category (90d baseline)
                          Both lists must have the same length.
                          If None, use proxy features from fv.

    Returns:
        IdentityShiftResult
    """
    # JSD from provided distributions or proxy via features
    if category_mix_30d and category_mix_90d:
        js_div = _js_divergence(category_mix_30d, category_mix_90d)
    else:
        # Proxy: merchant_category_shift_count normalised to [0,1]
        js_div = round(min(fv.merchant_category_shift_count / 10.0, 1.0), 4)

    # Discretionary ratio change (30d vs 90d)
    disc_change = abs(fv.discretionary_30d - fv.discretionary_90d) / max(fv.discretionary_90d, 1.0)
    disc_change_norm = min(disc_change, 1.0)

    # Lifestyle inflation as additional signal
    inflation_signal = min(abs(fv.lifestyle_inflation_trend), 1.0)

    # Composite identity shift score: weighted sum
    identity_score = (
        js_div         * 0.45
        + disc_change_norm * 0.30
        + inflation_signal * 0.25
    )
    identity_score = round(min(identity_score, 1.0), 4)

    is_shifted = identity_score >= 0.45

    # Build category drift evidence
    shifted_categories: list[str] = []
    if js_div > 0.3:
        shifted_categories.append(f"category_mix (JS={js_div:.3f})")
    if disc_change_norm > 0.3:
        shifted_categories.append(f"discretionary_ratio_change={disc_change_norm:.2f}")
    if inflation_signal > 0.2:
        shifted_categories.append(f"lifestyle_inflation={fv.lifestyle_inflation_trend:+.1%}")

    if identity_score >= 0.70:
        risk = RiskLevel.CRITICAL
    elif identity_score >= 0.45:
        risk = RiskLevel.HIGH
    elif identity_score >= 0.25:
        risk = RiskLevel.MEDIUM
    else:
        risk = RiskLevel.LOW

    return IdentityShiftResult(
        user_id=fv.user_id,
        identity_shift_score=identity_score,
        is_identity_shifted=is_shifted,
        js_divergence=js_div,
        category_drift_score=round(js_div * 0.5 + disc_change_norm * 0.5, 4),
        discretionary_ratio_change=round(disc_change_norm, 4),
        risk_level=risk,
        top_shifted_categories=shifted_categories,
    )
