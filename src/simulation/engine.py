"""
Tier 6 — Predictive Risk Simulation Engine (Core Monte Carlo Runner)

Full pipeline per simulation:
  1. Classify initial regime from twin features
  2. Build GARCH σ path per (path, day)
  3. Generate correlated shocks via t-Copula + Cholesky
     256 Sobol path-pairs (antithetic) + 244 standard random path-pairs = 1,000 paths
  4. Evolve daily cash state with regime-gated multipliers
  5. Run EMI cascade tracker
  6. Extract tail risk, fan chart, EWS, temporal projections
  7. Run recovery plan A* search
  8. Run counterfactual engine (optional)
  9. Emit simulation_completed event to Redis

Simulation request:
  SimulationRequest (Pydantic) → validated, seed derived from user_id + timestamp

Simulation response:
  Full dict matching §15.2 response shape from tier6.md
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

import numpy as np

from src.simulation.regime import (
    Regime,
    classify_regime,
    get_transition_matrix,
    sample_regime_path,
    regime_sigma_multipliers,
)
from src.simulation.garch import build_garch_vol_matrix, initial_sigma
from src.simulation.correlation import (
    generate_correlated_shocks,
    generate_sobol_shocks,
    generate_antithetic_pair,
)
from src.simulation.cascade import CascadeTracker
from src.simulation.scenario_library import ScenarioSpec, resolve_scenario
from src.simulation.ews import compute_full_ews, compute_leading_indicators
from src.simulation.tail_risk import (
    compute_var_cvar,
    extract_fan_chart,
    compute_temporal_projections,
    net_worth_delta,
    liquidity_crash_stats,
    emi_stress_score,
    regime_distribution_at_day,
    default_probability,
)
from src.simulation.recovery import find_recovery_plan
from src.simulation.counterfactual import run_counterfactual


# ── Simulation Request / Response types ──────────────────────────────────────

@dataclass
class TwinSnapshot:
    """Minimal twin state needed for simulation. Maps from DigitalTwin fields."""
    income_stability: float     = 0.65
    spending_volatility: float  = 0.35
    liquidity_health: str       = "MEDIUM"
    risk_score: float           = 0.35
    cash_buffer_days: float     = 14.0
    emi_monthly: float          = 15000.0
    emi_overdue_count: int      = 0
    debit_failure_rate: float   = 0.0
    cash_balance_current: float = 40000.0
    cascade_susceptibility: float = 0.45
    persona: str                = "unknown"
    financial_dna: list[float]  = field(default_factory=list)
    # Derived income / expense estimates
    income_monthly: float       = 50000.0
    essential_expense_monthly: float = 20000.0
    discretionary_expense_monthly: float = 10000.0
    overdraft_limit: float      = 5000.0


@dataclass
class VarianceReduction:
    sobol: bool     = True
    antithetic: bool = True


@dataclass
class SimulationRequest:
    user_id: str
    twin_snapshot: TwinSnapshot       = field(default_factory=TwinSnapshot)
    horizon_days: int | None          = None
    num_simulations: int              = 1000
    scenario: ScenarioSpec            = field(default_factory=ScenarioSpec)
    variance_reduction: VarianceReduction = field(default_factory=VarianceReduction)
    run_counterfactual: bool          = True
    counterfactual_id: str            = "CF_EARLIER_RESTRUC"
    counterfactual_lookback_days: int = 30
    seed: int | None                  = None


# ── Seed derivation ──────────────────────────────────────────────────────────

def _derive_seed(user_id: str, sim_id: str) -> int:
    raw = f"{user_id}:{sim_id}"
    return int(hashlib.sha256(raw.encode()).hexdigest()[:8], 16)


# ── Adaptive horizon ─────────────────────────────────────────────────────────

def _adaptive_horizon(
    cash_buffer_days: float,
    income_stability: float,
    ews_14d: float = 0.0,
) -> int:
    if income_stability <= 0:
        income_stability = 0.01
    raw = round(2 * cash_buffer_days / income_stability * 1.5)
    H = max(90, min(180, raw))
    if ews_14d > 0.55:
        H = 180
    return H


# ── Core engine ──────────────────────────────────────────────────────────────

def run_simulation(req: SimulationRequest) -> dict[str, Any]:
    """
    Full Monte Carlo simulation pipeline.
    Returns complete simulation response dict (§15.2 shape).
    """
    twin = req.twin_snapshot
    persona = twin.persona

    # ── IDs & seed ────────────────────────────────────────────────────────────
    sim_id = f"sim_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
    seed = req.seed if req.seed is not None else _derive_seed(req.user_id, sim_id)
    rng = np.random.default_rng(seed)

    # ── Horizon ──────────────────────────────────────────────────────────────
    H = req.horizon_days or _adaptive_horizon(twin.cash_buffer_days, twin.income_stability)
    N = max(req.num_simulations, 100)

    # ── Initial regime ───────────────────────────────────────────────────────
    initial_regime = classify_regime(
        twin.cash_buffer_days,
        twin.emi_monthly / max(twin.income_monthly, 1.0),
        max(0.0, min(1.0, twin.debit_failure_rate)),
        twin.emi_overdue_count,
    )

    # ── Scenario resolution ──────────────────────────────────────────────────
    scenario = resolve_scenario(req.scenario, H)

    # ── GARCH volatility matrix (N, H) ───────────────────────────────────────
    sigma0 = initial_sigma(persona)
    garch_matrix = build_garch_vol_matrix(N, H, persona, sigma0=sigma0, base_seed=seed)

    # ── Correlated shock generation ──────────────────────────────────────────
    n_sobol = 512 if req.variance_reduction.sobol else 0
    n_rand  = N - n_sobol

    shocks_all: list[np.ndarray] = []

    if n_sobol > 0:
        n_sobol_half = n_sobol // 2
        sobol_pos = generate_sobol_shocks(n_sobol_half, H, persona, base_seed=seed)
        if req.variance_reduction.antithetic:
            sobol_neg = generate_antithetic_pair(sobol_pos)
            shocks_all.append(sobol_pos)
            shocks_all.append(sobol_neg)
        else:
            shocks_all.append(sobol_pos)
            n_rand += n_sobol_half  # fill remaining with random

    if n_rand > 0:
        n_rand_half = n_rand // 2 if req.variance_reduction.antithetic else n_rand
        rand_pos = generate_correlated_shocks(n_rand_half, H, persona, rng=rng)
        shocks_all.append(rand_pos)
        if req.variance_reduction.antithetic and n_rand_half > 0:
            shocks_all.append(generate_antithetic_pair(rand_pos))

    shocks = np.vstack(shocks_all)[:N]   # shape (N, H, 4)
    N_actual = shocks.shape[0]

    # ── Transition matrices for regime paths ─────────────────────────────────
    trans_matrix = get_transition_matrix(persona)

    # ── Daily income / expense base parameters ───────────────────────────────
    daily_income_base = twin.income_monthly / 30.0
    daily_ess_base    = twin.essential_expense_monthly / 30.0
    daily_disc_base   = twin.discretionary_expense_monthly / 30.0
    daily_emi_base    = twin.emi_monthly / 30.0
    overdraft_limit   = twin.overdraft_limit

    # EMI due days (every 30 days, starting day 29)
    emi_due_days = set(range(29, H, 30))

    # ── Cascade tracker ──────────────────────────────────────────────────────
    cascade = CascadeTracker(n_paths=N_actual, persona=persona)

    # ── Cash path matrix ─────────────────────────────────────────────────────
    cash_paths     = np.empty((N_actual, H), dtype=np.float64)
    regime_matrix  = np.empty((N_actual, H), dtype=np.int8)

    for k in range(N_actual):
        # Regime path for this simulation path
        regime_path = sample_regime_path(initial_regime, trans_matrix, H, rng)
        regime_matrix[k] = regime_path

        sigma_mults = regime_sigma_multipliers(regime_path)   # (H,)
        garch_sigmas = garch_matrix[k % N, :]                 # (H,)
        effective_sigma = garch_sigmas * sigma_mults           # (H,)

        cash = twin.cash_balance_current

        for t in range(H):
            shock = shocks[k, t]   # shape (4,) — [income, ess, disc, emi_delay]
            eff_sig = effective_sigma[t]

            # Income
            income_mult = scenario.income_multipliers[t]
            income = max(daily_income_base * income_mult + shock[0] * eff_sig * daily_income_base, 0.0)

            # Essential expense
            ess_mult = scenario.ess_exp_multipliers[t]
            ess = max(daily_ess_base * ess_mult + abs(shock[1]) * eff_sig * daily_ess_base, 0.0)

            # Discretionary (reduced in stressed/crisis regimes)
            regime_disc_factor = {0: 1.0, 1: 0.85, 2: 0.60}[int(regime_path[t])]
            disc_mult = scenario.disc_multipliers[t] * regime_disc_factor
            disc = max(daily_disc_base * disc_mult + abs(shock[2]) * eff_sig * daily_disc_base * 0.5, 0.0)

            # EMI (only on due days)
            emi_today = 0.0
            emi_due = t in emi_due_days
            if emi_due:
                emi_miss_delta = scenario.emi_miss_prob_deltas[t] + abs(shock[3]) * 0.1
                if rng.random() > min(emi_miss_delta, 0.95):
                    emi_today = daily_emi_base * 30.0  # full monthly EMI

            # One-time scenario expenses
            one_time = scenario.one_time_expenses.get(t, 0.0)

            # Cascade penalty
            n_remaining = max(len(emi_due_days) - (t // 30), 1)
            cascade_penalty = cascade.process_day(
                k, cash, daily_emi_base * 30.0, emi_due, n_remaining, rng
            )

            cash = cash + income - ess - disc - emi_today - one_time - cascade_penalty

            # Hard floor at -overdraft_limit
            if cash < -overdraft_limit:
                cash = -overdraft_limit

            cash_paths[k, t] = cash

    # ── Tail risk ─────────────────────────────────────────────────────────────
    # Operational default should trigger before the hard overdraft floor is exhausted.
    # Using only -overdraft_limit makes default probabilities unrealistically flat at zero.
    default_thresh = min(0.0, -0.25 * overdraft_limit)
    var_95, cvar_95 = compute_var_cvar(cash_paths, twin.cash_balance_current)
    dp = default_probability(cash_paths, default_thresh)

    # ── EWS ──────────────────────────────────────────────────────────────────
    ews = compute_full_ews(cash_paths, twin.emi_monthly)

    # ── Fan chart ─────────────────────────────────────────────────────────────
    fan = extract_fan_chart(cash_paths)

    # ── Temporal projections ──────────────────────────────────────────────────
    stage_finals = cascade.stage_matrix(H)
    n_emi_dates = len(emi_due_days)
    emi_score = emi_stress_score(stage_finals, n_emi_dates)
    emi_stress_by_day = {30: emi_score * 0.4, 60: emi_score * 0.7, 90: emi_score}
    temporal = compute_temporal_projections(
        cash_paths, twin.cash_balance_current, twin.emi_monthly,
        default_thresh, emi_stress_by_day,
    )

    # ── Net worth delta ───────────────────────────────────────────────────────
    nw_delta = net_worth_delta(cash_paths, twin.cash_balance_current)

    # ── Liquidity crash stats ─────────────────────────────────────────────────
    liq_crash = liquidity_crash_stats(cash_paths, twin.emi_monthly)

    # ── Regime distribution at 90d ────────────────────────────────────────────
    regime_dist_90d = regime_distribution_at_day(regime_matrix.astype(np.int8), min(89, H - 1))

    # ── Cascade analysis ──────────────────────────────────────────────────────
    cascade_analysis = cascade.cascade_analysis()

    # ── Recovery plan ─────────────────────────────────────────────────────────
    emi_burden = twin.emi_monthly / max(twin.income_monthly, 1.0)
    initial_regime_int = int(initial_regime)
    recovery_plan = find_recovery_plan(
        regime=initial_regime_int,
        cash_buffer_days=twin.cash_buffer_days,
        emi_overdue_count=twin.emi_overdue_count,
        emi_monthly=twin.emi_monthly,
    )

    # ── Counterfactual ────────────────────────────────────────────────────────
    counterfactual_result: dict | None = None
    if req.run_counterfactual:
        actual_regime_str = ["STABLE", "STRESSED", "CRISIS"][initial_regime_int]
        try:
            counterfactual_result = run_counterfactual(
                cf_id=req.counterfactual_id,
                actual_risk_score=twin.risk_score,
                actual_cash_buffer_days=twin.cash_buffer_days,
                actual_regime=actual_regime_str,
                cash0=twin.cash_balance_current,
                income_monthly=twin.income_monthly,
                expense_monthly=twin.essential_expense_monthly + twin.discretionary_expense_monthly,
                emi_monthly=twin.emi_monthly,
                lookback_days=req.counterfactual_lookback_days,
                seed=seed + 1,
            )
        except Exception:
            counterfactual_result = None

    # ── Variance reduction accounting ────────────────────────────────────────
    vr_applied: list[str] = []
    if req.variance_reduction.sobol and n_sobol > 0:
        vr_applied.append(f"sobol_{n_sobol}")
    if req.variance_reduction.antithetic:
        vr_applied.append("antithetic")
    effective_precision = N_actual * (4 if len(vr_applied) == 2 else 2 if vr_applied else 1)

    return {
        "user_id":               req.user_id,
        "simulation_id":         sim_id,
        "seed":                  seed,
        "horizon_days":          H,
        "num_paths":             N_actual,
        "variance_reduction_applied": vr_applied,
        "effective_precision_equivalent": effective_precision,

        "default_probability":   dp,
        "temporal_projections":  temporal,
        "var_95":                -var_95,   # sign convention: negative = loss
        "cvar_95":               -cvar_95,

        "ews":                   ews,

        "liquidity_crash_days":  liq_crash,

        "emi_stress_score":      round(emi_score, 4),

        "net_worth_delta_90d":   nw_delta,

        "regime_distribution_at_90d": regime_dist_90d,

        "fan_chart": {
            "horizon_days": H,
            **fan,
        },

        "cascade_analysis":      cascade_analysis,

        "recovery_plan":         recovery_plan,

        "counterfactual":        counterfactual_result,

        "twin_update_emitted":   False,   # set to True by output_emitter after publish
        "timestamp":             datetime.now(timezone.utc).isoformat(),
    }
