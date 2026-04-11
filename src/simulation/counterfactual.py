"""
Tier 6 — Counterfactual Reasoning Engine

A counterfactual simulation answers:
  "If intervention A had been applied at time t₀ - δ, what would the user's state be now?"

Standard counterfactual scenarios (CF_*):
  CF_EARLIER_RESTRUC  — EMI restructuring 30d ago
  CF_MICRO_LOAN_15    — ₹20,000 micro-loan 15d ago
  CF_DISC_CUT_60      — 20% discretionary cut 60d ago
  CF_NO_INTERVENTION  — without any interventions that fired

The engine re-runs the Monte Carlo engine from (t₀ - δ) with the action's
daily CF delta applied, then computes the counterfactual state delta vs actual.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np


# ── Counterfactual scenario definitions ───────────────────────────────────────

@dataclass
class CounterfactualSpec:
    id: str
    question: str
    lookback_days: int
    action_id: str
    daily_cf_delta: float    # daily INR boost from the hypothetical action
    one_time_inflow: float = 0.0

CF_LIBRARY: dict[str, CounterfactualSpec] = {
    "CF_EARLIER_RESTRUC": CounterfactualSpec(
        id="CF_EARLIER_RESTRUC",
        question="What if EMI restructuring had been offered 30 days ago?",
        lookback_days=30,
        action_id="A_EMI_RESTRUC",
        daily_cf_delta=300.0,
    ),
    "CF_MICRO_LOAN_15": CounterfactualSpec(
        id="CF_MICRO_LOAN_15",
        question="What if a ₹20,000 micro-loan had been disbursed 15 days ago?",
        lookback_days=15,
        action_id="A_MICRO_LOAN",
        daily_cf_delta=0.0,
        one_time_inflow=20_000.0,
    ),
    "CF_DISC_CUT_60": CounterfactualSpec(
        id="CF_DISC_CUT_60",
        question="What if discretionary cut had started 60 days ago?",
        lookback_days=60,
        action_id="A_CUT_DISC_20",
        daily_cf_delta=800.0,
    ),
    "CF_NO_INTERVENTION": CounterfactualSpec(
        id="CF_NO_INTERVENTION",
        question="What would have happened without any interventions?",
        lookback_days=90,
        action_id="none",
        daily_cf_delta=-200.0,   # simulate absence of interventions = slight cashflow drain
    ),
}


# ── Counterfactual runner ─────────────────────────────────────────────────────

def run_counterfactual(
    cf_id: str,
    actual_risk_score: float,
    actual_cash_buffer_days: float,
    actual_regime: str,
    cash0: float,
    income_monthly: float,
    expense_monthly: float,
    emi_monthly: float,
    lookback_days: int | None = None,
    custom_cf: CounterfactualSpec | None = None,
    seed: int = 42,
) -> dict:
    """
    Estimate counterfactual state if action had been applied lookback_days ago.

    Uses a simplified deterministic path model (not full Monte Carlo) for speed.
    The full engine can optionally be wired in for higher accuracy.

    Returns dict matching §15.2 counterfactual output shape.
    """
    spec = custom_cf or CF_LIBRARY.get(cf_id)
    if spec is None:
        raise ValueError(f"Unknown counterfactual: {cf_id}")

    lb = lookback_days or spec.lookback_days

    # Simulate counterfactual daily cash over lookback_days
    rng = np.random.default_rng(seed)
    daily_income  = income_monthly / 30.0
    daily_expense = expense_monthly / 30.0
    daily_emi     = emi_monthly / 30.0
    daily_surplus = daily_income - daily_expense - daily_emi

    cf_daily_cf = spec.daily_cf_delta
    cf_one_time = spec.one_time_inflow

    cash_cf = cash0
    # Apply one-time inflow at start of lookback
    cash_cf += cf_one_time

    for d in range(lb):
        noise = rng.normal(0, daily_income * 0.08)
        cash_cf += daily_surplus + cf_daily_cf + noise

    # Counterfactual risk score estimate (linear approximation)
    # Better cashflow → lower risk_score
    cf_buffer_days = cash_cf / max(daily_expense + daily_emi, 1.0)
    cf_buffer_days = float(np.clip(cf_buffer_days, 0, 90))

    # Risk score: higher cash buffer → lower risk
    risk_delta_from_buffer = (cf_buffer_days - actual_cash_buffer_days) * 0.008
    cf_risk_score = float(np.clip(actual_risk_score - risk_delta_from_buffer, 0.0, 1.0))

    # Regime estimation from counterfactual cash buffer
    emi_burden_ratio = emi_monthly / max(income_monthly, 1.0)
    if cf_buffer_days > 15 and emi_burden_ratio < 0.35:
        cf_regime = "STABLE"
    elif cf_buffer_days > 5 or emi_burden_ratio < 0.55:
        cf_regime = "STRESSED"
    else:
        cf_regime = "CRISIS"

    # Penalty interest avoided (Stage 1 cascade)
    penalty_avoided = 0.0
    if cf_risk_score < actual_risk_score:
        # Rough: 2% p.a. penalty on overdue principal for days in cascade
        overdue = emi_monthly
        penalty_avoided = round(overdue * 0.02 * lb / 365.0, 0)

    # Crisis probability avoided (linear interpolation)
    crisis_prob_avoided = round(max(actual_risk_score - cf_risk_score, 0.0) * 0.8, 2)

    return {
        "scenario": cf_id,
        "lookback_days": lb,
        "actual_state_today": {
            "risk_score":        round(actual_risk_score, 4),
            "cash_buffer_days":  round(actual_cash_buffer_days, 1),
            "regime":            actual_regime,
        },
        "counterfactual_state_today": {
            "risk_score":        round(cf_risk_score, 4),
            "cash_buffer_days":  round(cf_buffer_days, 1),
            "regime":            cf_regime,
        },
        "value_of_earlier_intervention": {
            "penalty_interest_avoided": int(penalty_avoided),
            "cash_buffer_gained_days":  round(max(cf_buffer_days - actual_cash_buffer_days, 0.0), 1),
            "risk_score_improvement":   round(max(actual_risk_score - cf_risk_score, 0.0), 4),
            "crisis_probability_avoided": crisis_prob_avoided,
        },
    }


def list_counterfactuals() -> dict[str, str]:
    """Return available counterfactual IDs and their questions."""
    return {k: v.question for k, v in CF_LIBRARY.items()}
