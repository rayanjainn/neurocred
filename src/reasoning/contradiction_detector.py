"""
Tier 5 — Contradiction Detector (Module 3)

Three-layer statistical income consistency analysis:
  Layer 1: Monthly Income Z-Test (95% CI, relaxed for gig workers)
  Layer 2: Income Source Consistency (P2P vs P2M employer)
  Layer 3: Lifestyle Consistency Index (discretionary/income ratio)

Runs BEFORE the LLM call. Output feeds into Priority 5 context assembly.
"""

from __future__ import annotations

import math
import statistics
from typing import Optional

from src.reasoning.schemas import (
    ContradictionDetectorResult,
    IncomeDirection,
    Severity,
)


def run_contradiction_detector(
    declared_income: float,
    monthly_income_observations: list[float],   # from Tier 3: income per month (last 3m)
    income_stability_score: float,              # from Tier 3
    p2p_income_fraction: float,                 # fraction of income from P2P transfers
    discretionary_30d: float,                   # from Tier 3
    cash_dependency_index: float,               # from Tier 3
) -> ContradictionDetectorResult:
    """
    Run all three contradiction detection layers and return a structured result.

    Args:
        declared_income: Monthly income declared by user at onboarding (INR)
        monthly_income_observations: List of observed monthly income totals (INCOME-typed events)
        income_stability_score: From Tier 3 (0=volatile, 1=stable)
        p2p_income_fraction: Fraction of total income events that are P2P transfers
        discretionary_30d: 30-day discretionary spending total
        cash_dependency_index: Fraction of outflows via ATM/cash

    Returns:
        ContradictionDetectorResult with all layer flags and severity.
    """
    result = ContradictionDetectorResult(declared_income=declared_income)
    layers_triggered = 0

    # ── Layer 1: Monthly Income Z-Test ────────────────────────────────────────
    if len(monthly_income_observations) >= 2:
        mu_obs = statistics.mean(monthly_income_observations)
        sigma_obs = statistics.stdev(monthly_income_observations)
        n_months = len(monthly_income_observations)
        result.observed_mean_income = mu_obs

        if sigma_obs > 0:
            z = (declared_income - mu_obs) / (sigma_obs / math.sqrt(n_months))
            result.z_score = round(z, 4)

            # Relax threshold for volatile gig workers
            threshold = 2.5 if income_stability_score < 0.5 else 2.0

            if abs(z) > threshold:
                result.layer1_flag = True
                layers_triggered += 1
                result.direction = (
                    IncomeDirection.OVER_REPORTED if z > 0 else IncomeDirection.UNDER_REPORTED
                )
        else:
            # zero variance — single data point or fully consistent; can still check magnitude
            if monthly_income_observations:
                mu_obs = monthly_income_observations[0]
                result.observed_mean_income = mu_obs

    # ── Layer 2: Income Source Consistency ───────────────────────────────────
    # If >40% of income events are P2P, declared "salary" is partly informal
    P2P_THRESHOLD = 0.40
    if p2p_income_fraction > P2P_THRESHOLD:
        result.layer2_flag = True
        layers_triggered += 1

    # ── Layer 3: Lifestyle Consistency Index ─────────────────────────────────
    # LCI = avg monthly discretionary / declared monthly income
    # Normal range: 0.10 – 0.35
    lci: float = 0.0
    if declared_income > 0:
        lci = discretionary_30d / declared_income
    result.layer3_lci = round(lci, 4)

    layer3_flag = False
    if lci > 0.45 and declared_income > 50_000:
        # Spending more than 45% discretionary on high declared income → over-reporting
        layer3_flag = True
        if result.direction == IncomeDirection.CONSISTENT:
            result.direction = IncomeDirection.OVER_REPORTED
    elif lci < 0.05 and declared_income < 30_000 and cash_dependency_index > 0.25:
        # Extremely low discretionary + high cash dependency → under-reporting
        layer3_flag = True
        if result.direction == IncomeDirection.CONSISTENT:
            result.direction = IncomeDirection.UNDER_REPORTED

    result.layer3_flag = layer3_flag
    if layer3_flag:
        layers_triggered += 1

    # ── Aggregate ─────────────────────────────────────────────────────────────
    result.layers_triggered = layers_triggered
    result.contradiction_detected = layers_triggered >= 1

    # Severity: 1 layer = LOW, 2 layers = MEDIUM, 3 layers = HIGH
    if layers_triggered == 0:
        result.severity = Severity.LOW
    elif layers_triggered == 1:
        result.severity = Severity.LOW
    elif layers_triggered == 2:
        result.severity = Severity.MEDIUM
    else:
        result.severity = Severity.HIGH

    # Confidence: ratio of layers triggered × base z-score signal strength
    z_signal = min(abs(result.z_score) / 3.0, 1.0)
    result.confidence = round(
        (layers_triggered / 3.0) * 0.7 + z_signal * 0.3, 4
    )

    # Summary
    parts = []
    if result.layer1_flag:
        parts.append(
            f"Z-test: declared ₹{declared_income:,.0f} vs observed mean "
            f"₹{result.observed_mean_income:,.0f} (z={result.z_score:.2f})"
        )
    if result.layer2_flag:
        parts.append(
            f"Source inconsistency: {p2p_income_fraction*100:.0f}% of income is P2P (threshold 40%)"
        )
    if result.layer3_flag:
        parts.append(
            f"LCI={lci:.2f} (expected 0.10–0.35, discretionary ₹{discretionary_30d:,.0f})"
        )
    result.details = "; ".join(parts) if parts else "No contradiction signals detected."

    return result


def extract_monthly_income_from_features(
    income_90d: float,
    income_30d: float,
    income_7d: float,
) -> list[float]:
    """
    Build a rough 3-month income observation list from Tier 3 window features.
    Used when full event-level data per month isn't available.
    """
    # Approximate month 3 = 90d - 30d, month 2 = 30d - 7d, month 1 = 7d
    # This is a proxy; ideally use actual monthly breakdowns
    m3_approx = max(income_90d - income_30d, 0.0)
    m2_approx = max(income_30d - income_7d, 0.0)
    m1_approx = income_7d

    # Filter out zero months (no data) to avoid skewing the mean
    observations = [m for m in [m1_approx, m2_approx, m3_approx] if m > 0]
    return observations if observations else [0.0]
