"""
Tier 6 — Stress Scenario Library

Three scenario categories:
  1. Atomic       — single-event shocks (S_*)
  2. Compound     — simultaneous co-occurrence (C_*)
  3. Cascading    — sequential event chains (CA_*)

Scenario composition API:
  ScenarioSpec(type="atomic"|"compound"|"cascading", components=[...], ...)
  → resolved to a ResolvedScenario with per-day income/expense/emi multipliers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


# ── Atomic scenario definitions ──────────────────────────────────────────────

@dataclass
class AtomicScenario:
    id: str
    name: str
    income_multiplier: float          = 1.0   # applied during active days
    income_ramp_start_day: int        = -1    # -1 = no ramp
    income_ramp_target: float         = 1.0   # ramp target multiplier
    essential_expense_multiplier: float = 1.0
    discretionary_multiplier: float   = 1.0
    emi_miss_prob_delta: float         = 0.0  # additive delta to daily EMI miss prob
    one_time_expense: float            = 0.0  # INR, applied on start_day
    duration_days: int                 = 30
    permanent: bool                    = False


ATOMIC_SCENARIOS: dict[str, AtomicScenario] = {
    "S_INC_DROP_20": AtomicScenario(
        id="S_INC_DROP_20",
        name="Mild income shock",
        income_multiplier=0.80,
        duration_days=30,
    ),
    "S_INC_DROP_50": AtomicScenario(
        id="S_INC_DROP_50",
        name="Severe income shock",
        income_multiplier=0.50,
        duration_days=60,
    ),
    "S_JOB_LOSS": AtomicScenario(
        id="S_JOB_LOSS",
        name="Job loss",
        income_multiplier=0.0,
        income_ramp_start_day=45,
        income_ramp_target=0.50,
        essential_expense_multiplier=1.08,
        emi_miss_prob_delta=0.15,
        duration_days=90,
    ),
    "S_EXP_SURGE_30": AtomicScenario(
        id="S_EXP_SURGE_30",
        name="Expense surge",
        essential_expense_multiplier=1.30,
        duration_days=30,
    ),
    "S_MEDICAL": AtomicScenario(
        id="S_MEDICAL",
        name="Medical emergency",
        one_time_expense=62500.0,   # mid-point of ₹25,000–₹1,00,000
        emi_miss_prob_delta=0.10,
        duration_days=1,
    ),
    "S_RATE_HIKE": AtomicScenario(
        id="S_RATE_HIKE",
        name="Interest rate hike (RBI)",
        essential_expense_multiplier=1.05,
        emi_miss_prob_delta=0.005,  # EMI floats up 0.5%
        permanent=True,
        duration_days=9999,
    ),
    "S_FRAUD": AtomicScenario(
        id="S_FRAUD",
        name="Account freeze / fraud",
        income_multiplier=0.0,
        essential_expense_multiplier=1.20,   # emergency legal expense proxy
        emi_miss_prob_delta=0.30,
        duration_days=14,
    ),
}


# ── Compound scenario definitions ─────────────────────────────────────────────

@dataclass
class CompoundScenario:
    id: str
    name: str
    components: list[str]             # atomic scenario IDs
    description: str = ""


COMPOUND_SCENARIOS: dict[str, CompoundScenario] = {
    "C_JOB_MEDICAL": CompoundScenario(
        id="C_JOB_MEDICAL",
        name="Job loss + Medical emergency",
        components=["S_JOB_LOSS", "S_MEDICAL"],
        description="Job loss causes health crisis",
    ),
    "C_RATE_STRESS": CompoundScenario(
        id="C_RATE_STRESS",
        name="Rate hike + Expense surge",
        components=["S_RATE_HIKE", "S_EXP_SURGE_30"],
        description="Rate hike coincides with inflation surge",
    ),
    "C_FRAUD_LOSS": CompoundScenario(
        id="C_FRAUD_LOSS",
        name="Fraud + Mild income drop",
        components=["S_FRAUD", "S_INC_DROP_20"],
        description="Account freeze + reduced income + legal costs",
    ),
    "C_FULL_STRESS": CompoundScenario(
        id="C_FULL_STRESS",
        name="Full stress (regulatory worst-case)",
        components=["S_JOB_LOSS", "S_MEDICAL", "S_RATE_HIKE"],
        description="Absolute worst-path for regulatory stress test",
    ),
}


# ── Cascading scenario definitions (sequential) ───────────────────────────────

@dataclass
class CascadingScenario:
    id: str
    name: str
    sequence: list[str]              # atomic IDs in order
    time_offsets: list[int]          # day each atomic starts (relative to sim start)
    description: str = ""


CASCADING_SCENARIOS: dict[str, CascadingScenario] = {
    "CA_INCOME_EMI": CascadingScenario(
        id="CA_INCOME_EMI",
        name="Income drop → EMI cascade",
        sequence=["S_INC_DROP_20"],
        time_offsets=[0],
        description="Income drop causes first EMI miss; cascade model takes over at day 30",
    ),
    "CA_FRAUD_SPIRAL": CascadingScenario(
        id="CA_FRAUD_SPIRAL",
        name="Fraud → income spiral",
        sequence=["S_FRAUD", "S_INC_DROP_50"],
        time_offsets=[0, 14],
        description="Account freeze resolves but triggers credit limit cut → effective income drop",
    ),
    "CA_LIFESTYLE_DEBT": CascadingScenario(
        id="CA_LIFESTYLE_DEBT",
        name="Lifestyle inflation → expense surge",
        sequence=["S_EXP_SURGE_30"],
        time_offsets=[60],  # gradual over 90d; modelled as surge at day 60
        description="Detected by lifestyle_inflation_trend > 0.25",
    ),
}


# ── ScenarioSpec (request input) ─────────────────────────────────────────────

@dataclass
class ScenarioSpec:
    type: Literal["atomic", "compound", "cascading", "baseline"] = "baseline"
    components: list[str] = field(default_factory=list)   # atomic/compound/cascading IDs
    start_day: int = 0
    duration_override: int | None = None
    custom_params: dict[str, Any] = field(default_factory=dict)


# ── Resolved scenario: per-day multiplier lookup ─────────────────────────────

@dataclass
class ResolvedScenario:
    """
    Pre-resolved scenario for simulation use.
    Provides per-day multipliers for income, essential expense, discretionary,
    EMI miss prob delta, and one-time expenses.
    """
    income_multipliers: list[float]       # length = horizon
    ess_exp_multipliers: list[float]
    disc_multipliers: list[float]
    emi_miss_prob_deltas: list[float]
    one_time_expenses: dict[int, float]   # day → INR amount
    name: str = "baseline"


def _baseline(horizon: int) -> ResolvedScenario:
    return ResolvedScenario(
        income_multipliers=[1.0] * horizon,
        ess_exp_multipliers=[1.0] * horizon,
        disc_multipliers=[1.0] * horizon,
        emi_miss_prob_deltas=[0.0] * horizon,
        one_time_expenses={},
        name="baseline",
    )


def _apply_atomic(
    resolved: ResolvedScenario,
    atomic: AtomicScenario,
    start_day: int,
    horizon: int,
    duration_override: int | None = None,
    custom_params: dict[str, Any] | None = None,
) -> None:
    """Apply an atomic scenario's effect onto a ResolvedScenario (in-place)."""
    duration = duration_override or atomic.duration_days
    end_day = start_day + duration if not atomic.permanent else horizon

    # Handle custom medical expense override
    one_time = atomic.one_time_expense
    if custom_params and "medical_expense_amount" in custom_params:
        one_time = float(custom_params["medical_expense_amount"])

    for d in range(start_day, min(end_day, horizon)):
        # Income: handle ramp-back for job loss
        if atomic.income_ramp_start_day >= 0 and d >= start_day + atomic.income_ramp_start_day:
            ramp_progress = (d - (start_day + atomic.income_ramp_start_day)) / max(duration - atomic.income_ramp_start_day, 1)
            inc_mult = atomic.income_multiplier + (atomic.income_ramp_target - atomic.income_multiplier) * min(ramp_progress, 1.0)
        else:
            inc_mult = atomic.income_multiplier

        resolved.income_multipliers[d] = min(resolved.income_multipliers[d], inc_mult)
        resolved.ess_exp_multipliers[d] = max(resolved.ess_exp_multipliers[d], atomic.essential_expense_multiplier)
        resolved.disc_multipliers[d] = min(resolved.disc_multipliers[d], atomic.discretionary_multiplier)
        resolved.emi_miss_prob_deltas[d] += atomic.emi_miss_prob_delta

    # One-time expense on start_day
    if one_time > 0 and start_day < horizon:
        resolved.one_time_expenses[start_day] = (
            resolved.one_time_expenses.get(start_day, 0.0) + one_time
        )


def resolve_scenario(spec: ScenarioSpec, horizon: int) -> ResolvedScenario:
    """
    Convert a ScenarioSpec into a ResolvedScenario with per-day multiplier arrays.
    """
    resolved = _baseline(horizon)

    if spec.type == "baseline" or not spec.components:
        return resolved

    if spec.type == "atomic":
        for cid in spec.components:
            if cid in ATOMIC_SCENARIOS:
                atomic = ATOMIC_SCENARIOS[cid]
                _apply_atomic(resolved, atomic, spec.start_day, horizon,
                              spec.duration_override, spec.custom_params)
                resolved.name = atomic.name

    elif spec.type == "compound":
        names = []
        # Find compound def or treat components as direct atomic list
        compound = None
        if len(spec.components) == 1 and spec.components[0] in COMPOUND_SCENARIOS:
            compound = COMPOUND_SCENARIOS[spec.components[0]]
            atom_ids = compound.components
            names.append(compound.name)
        else:
            atom_ids = spec.components

        for aid in atom_ids:
            if aid in ATOMIC_SCENARIOS:
                atomic = ATOMIC_SCENARIOS[aid]
                _apply_atomic(resolved, atomic, spec.start_day, horizon,
                              spec.duration_override, spec.custom_params)
                names.append(atomic.name)
        resolved.name = " + ".join(names) if names else "compound"

    elif spec.type == "cascading":
        for cid in spec.components:
            if cid in CASCADING_SCENARIOS:
                casc = CASCADING_SCENARIOS[cid]
                for seq_id, offset in zip(casc.sequence, casc.time_offsets):
                    if seq_id in ATOMIC_SCENARIOS:
                        atomic = ATOMIC_SCENARIOS[seq_id]
                        _apply_atomic(resolved, atomic, spec.start_day + offset, horizon,
                                      spec.duration_override, spec.custom_params)
                resolved.name = casc.name

    return resolved


def list_scenarios() -> dict:
    """Return a summary of all available scenarios."""
    return {
        "atomic": {k: v.name for k, v in ATOMIC_SCENARIOS.items()},
        "compound": {k: v.name for k, v in COMPOUND_SCENARIOS.items()},
        "cascading": {k: v.name for k, v in CASCADING_SCENARIOS.items()},
    }
