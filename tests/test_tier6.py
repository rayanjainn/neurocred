"""
Tier 6 — Predictive Risk Simulation Engine: Test Suite

Tests:
  TestRegime           — classify_regime, transition matrix, path sampling
  TestGARCH            — GARCH(1,1) evolution, long-run variance, path generation
  TestCorrelation      — Cholesky decomposition, shock generation, antithetic pairs
  TestCascade          — Stage 1–4 escalation, systemic flag, cascade analysis
  TestScenarioLibrary  — atomic/compound/cascading scenario resolution
  TestEWS              — EWS computation, severity bands
  TestTailRisk         — VaR/CVaR, fan chart, temporal projections
  TestRecovery         — A* recovery plan, MDP transitions
  TestBayesianUpdater  — Conjugate posterior update, regime update
  TestCounterfactual   — Counterfactual simulation, value estimation
  TestEngine           — Full Monte Carlo pipeline, output shape validation
  TestAPI              — Simulation API endpoints (mocked)
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest


# ── helpers ──────────────────────────────────────────────────────────────────

def _cash_paths(n: int = 100, h: int = 90, base: float = 40000) -> np.ndarray:
    rng = np.random.default_rng(0)
    # Simulate declining cash paths for testing
    noise = rng.normal(0, 500, (n, h))
    paths = base + np.cumsum(noise - 100, axis=1)
    return paths


# ═══════════════════════════════════════════════════════════════════════════
# TestRegime
# ═══════════════════════════════════════════════════════════════════════════

class TestRegime:
    def test_classify_stable(self):
        from src.simulation.regime import classify_regime, Regime
        r = classify_regime(cash_buffer_days=20, emi_burden_ratio=0.25, debit_failure_rate=0.02)
        assert r == Regime.STABLE

    def test_classify_stressed_low_buffer(self):
        from src.simulation.regime import classify_regime, Regime
        r = classify_regime(cash_buffer_days=10, emi_burden_ratio=0.30, debit_failure_rate=0.02)
        assert r == Regime.STRESSED

    def test_classify_stressed_high_failure_rate(self):
        from src.simulation.regime import classify_regime, Regime
        r = classify_regime(cash_buffer_days=20, emi_burden_ratio=0.25, debit_failure_rate=0.15)
        assert r == Regime.STRESSED

    def test_classify_stressed_emi_burden(self):
        from src.simulation.regime import classify_regime, Regime
        r = classify_regime(cash_buffer_days=20, emi_burden_ratio=0.40, debit_failure_rate=0.02)
        assert r == Regime.STRESSED

    def test_classify_crisis_low_buffer(self):
        from src.simulation.regime import classify_regime, Regime
        r = classify_regime(cash_buffer_days=3, emi_burden_ratio=0.30, debit_failure_rate=0.02)
        assert r == Regime.CRISIS

    def test_classify_crisis_high_emi(self):
        from src.simulation.regime import classify_regime, Regime
        r = classify_regime(cash_buffer_days=20, emi_burden_ratio=0.60, debit_failure_rate=0.02)
        assert r == Regime.CRISIS

    def test_classify_crisis_overdue(self):
        from src.simulation.regime import classify_regime, Regime
        r = classify_regime(cash_buffer_days=20, emi_burden_ratio=0.30, debit_failure_rate=0.02, emi_overdue_count=2)
        assert r == Regime.CRISIS

    def test_transition_matrix_rows_sum_to_one(self):
        from src.simulation.regime import get_transition_matrix
        for persona in ["genuine_healthy", "genuine_struggling", "shell_circular", "paper_trader", "new_to_credit", "unknown"]:
            tm = get_transition_matrix(persona)
            assert tm.shape == (3, 3)
            np.testing.assert_allclose(tm.sum(axis=1), 1.0, atol=1e-10)

    def test_sample_regime_path_length(self):
        from src.simulation.regime import Regime, get_transition_matrix, sample_regime_path
        rng = np.random.default_rng(42)
        tm = get_transition_matrix("unknown")
        path = sample_regime_path(Regime.STABLE, tm, 90, rng)
        assert len(path) == 90
        assert all(0 <= v <= 2 for v in path)

    def test_regime_sigma_multipliers(self):
        from src.simulation.regime import regime_sigma_multipliers, REGIME_SIGMA_MULTIPLIER, Regime
        path = np.array([0, 1, 2, 0], dtype=np.int8)
        mults = regime_sigma_multipliers(path)
        assert mults[0] == REGIME_SIGMA_MULTIPLIER[Regime.STABLE]
        assert mults[1] == REGIME_SIGMA_MULTIPLIER[Regime.STRESSED]
        assert mults[2] == REGIME_SIGMA_MULTIPLIER[Regime.CRISIS]


# ═══════════════════════════════════════════════════════════════════════════
# TestGARCH
# ═══════════════════════════════════════════════════════════════════════════

class TestGARCH:
    def test_evolve_garch_positive(self):
        from src.simulation.garch import evolve_garch
        sigma = evolve_garch(sigma_prev=0.05, epsilon_prev=0.01, omega=0.0002, alpha=0.05, beta=0.90)
        assert sigma > 0

    def test_garch_vol_path_length(self):
        from src.simulation.garch import build_garch_vol_path
        path = build_garch_vol_path(horizon=90, persona="genuine_healthy", seed=0)
        assert len(path) == 90
        assert np.all(path > 0)

    def test_garch_vol_path_all_personas(self):
        from src.simulation.garch import build_garch_vol_path
        for persona in ["genuine_healthy", "genuine_struggling", "shell_circular", "paper_trader", "new_to_credit"]:
            path = build_garch_vol_path(horizon=30, persona=persona, seed=1)
            assert len(path) == 30
            assert np.all(path > 0)

    def test_garch_matrix_shape(self):
        from src.simulation.garch import build_garch_vol_matrix
        mat = build_garch_vol_matrix(n_paths=10, horizon=30, persona="genuine_healthy")
        assert mat.shape == (10, 30)
        assert np.all(mat > 0)

    def test_long_run_variance(self):
        from src.simulation.garch import initial_sigma, GARCH_PARAMS
        for persona, (omega, alpha, beta) in GARCH_PARAMS.items():
            sig = initial_sigma(persona)
            assert sig > 0
            # Verify it approximates sqrt(omega / (1 - alpha - beta))
            expected = np.sqrt(omega / (1 - alpha - beta))
            assert abs(sig - expected) < 0.001

    def test_struggling_more_volatile_than_healthy(self):
        from src.simulation.garch import initial_sigma
        assert initial_sigma("genuine_struggling") > initial_sigma("genuine_healthy")

    def test_shell_circular_more_volatile_than_healthy(self):
        from src.simulation.garch import initial_sigma
        # shell_circular has higher omega (0.0030) than genuine_healthy (0.0002)
        assert initial_sigma("shell_circular") > initial_sigma("genuine_healthy")


# ═══════════════════════════════════════════════════════════════════════════
# TestCorrelation
# ═══════════════════════════════════════════════════════════════════════════

class TestCorrelation:
    def test_cholesky_lower_triangular(self):
        from src.simulation.correlation import get_cholesky
        L = get_cholesky("genuine_healthy")
        assert L.shape == (4, 4)
        # Lower triangular: upper triangle should be zero
        assert np.allclose(np.triu(L, k=1), 0)

    def test_reconstructed_corr_valid(self):
        from src.simulation.correlation import get_cholesky, PERSONA_CORR
        for persona in PERSONA_CORR:
            L = get_cholesky(persona)
            approx_corr = L @ L.T
            # Diagonal should be ~1
            np.testing.assert_allclose(np.diag(approx_corr), 1.0, atol=0.01)

    def test_shock_shape(self):
        from src.simulation.correlation import generate_correlated_shocks
        rng = np.random.default_rng(0)
        shocks = generate_correlated_shocks(100, 90, "genuine_healthy", rng=rng)
        assert shocks.shape == (100, 90, 4)

    def test_antithetic_pair_negates(self):
        from src.simulation.correlation import generate_correlated_shocks, generate_antithetic_pair
        rng = np.random.default_rng(0)
        pos = generate_correlated_shocks(50, 10, "unknown", rng=rng)
        neg = generate_antithetic_pair(pos)
        np.testing.assert_allclose(pos + neg, 0, atol=1e-12)

    def test_sobol_shocks_shape(self):
        from src.simulation.correlation import generate_sobol_shocks
        shocks = generate_sobol_shocks(64, 30, "genuine_healthy", base_seed=0)
        assert shocks.shape == (64, 30, 4)

    def test_shocks_correlated_negatively_income_essential(self):
        """Income and essential expense shocks should be negatively correlated."""
        from src.simulation.correlation import generate_correlated_shocks
        rng = np.random.default_rng(42)
        shocks = generate_correlated_shocks(2000, 1, "genuine_healthy", rng=rng, use_t_copula=False)
        income_shocks = shocks[:, 0, 0]
        ess_shocks    = shocks[:, 0, 1]
        corr = float(np.corrcoef(income_shocks, ess_shocks)[0, 1])
        assert corr < 0, f"Expected negative correlation, got {corr:.3f}"


# ═══════════════════════════════════════════════════════════════════════════
# TestCascade
# ═══════════════════════════════════════════════════════════════════════════

class TestCascade:
    def test_no_cascade_if_sufficient_cash(self):
        from src.simulation.cascade import CascadeTracker
        rng = np.random.default_rng(0)
        tracker = CascadeTracker(n_paths=1, persona="genuine_healthy")
        # Cash > EMI: no cascade triggered
        penalty = tracker.process_day(0, cash=50000, emi_base=15000, emi_due_today=True,
                                       n_remaining_emis=10, rng=rng)
        assert tracker.states[0].stage == 0
        assert penalty == 0.0

    def test_stage1_triggered_on_insufficient_cash(self):
        from src.simulation.cascade import CascadeTracker
        rng = np.random.default_rng(0)
        tracker = CascadeTracker(n_paths=1, persona="genuine_struggling")
        # Cash < EMI: Stage 1 triggered
        tracker.process_day(0, cash=5000, emi_base=15000, emi_due_today=True,
                            n_remaining_emis=10, rng=rng)
        assert tracker.states[0].stage == 1
        assert tracker.states[0].missed_emis == 1

    def test_cascade_penalty_after_stage1(self):
        from src.simulation.cascade import CascadeTracker, PENALTY_RATE_STAGE1
        rng = np.random.default_rng(0)
        tracker = CascadeTracker(n_paths=1, persona="genuine_struggling")
        tracker.process_day(0, cash=5000, emi_base=15000, emi_due_today=True,
                            n_remaining_emis=10, rng=rng)
        # Next day: should have penalty drain
        penalty = tracker.process_day(0, cash=-1000, emi_base=15000, emi_due_today=False,
                                       n_remaining_emis=10, rng=rng)
        assert penalty > 0

    def test_cascade_analysis_keys(self):
        from src.simulation.cascade import CascadeTracker
        tracker = CascadeTracker(n_paths=10, persona="unknown")
        analysis = tracker.cascade_analysis()
        for key in ["paths_reaching_stage1", "paths_reaching_stage2",
                    "paths_reaching_stage3", "paths_reaching_stage4",
                    "systemic_stress_flag"]:
            assert key in analysis

    def test_cascade_stage_fractions_monotone(self):
        """Fractions must be decreasing: stage1 >= stage2 >= stage3 >= stage4."""
        from src.simulation.cascade import CascadeTracker
        rng = np.random.default_rng(0)
        tracker = CascadeTracker(n_paths=100, persona="shell_circular")
        # Force stage 1 on all paths
        for k in range(100):
            tracker.process_day(k, cash=100, emi_base=15000, emi_due_today=True,
                                n_remaining_emis=5, rng=rng)
        a = tracker.cascade_analysis()
        assert a["paths_reaching_stage1"] >= a["paths_reaching_stage2"]
        assert a["paths_reaching_stage2"] >= a["paths_reaching_stage3"]
        assert a["paths_reaching_stage3"] >= a["paths_reaching_stage4"]

    def test_systemic_flag_when_over_20pct(self):
        from src.simulation.cascade import CascadeTracker
        rng = np.random.default_rng(0)
        tracker = CascadeTracker(n_paths=10, persona="shell_circular")
        # Manually force 3 paths to stage 2 (30% > 20% threshold)
        for k in range(3):
            tracker.states[k].stage = 2
            tracker.states[k].credit_limit_cut = True
        flag, _ = tracker.check_systemic_flag()
        assert flag is True


# ═══════════════════════════════════════════════════════════════════════════
# TestScenarioLibrary
# ═══════════════════════════════════════════════════════════════════════════

class TestScenarioLibrary:
    def test_baseline_all_ones(self):
        from src.simulation.scenario_library import ScenarioSpec, resolve_scenario
        spec = ScenarioSpec(type="baseline")
        resolved = resolve_scenario(spec, horizon=30)
        assert all(m == 1.0 for m in resolved.income_multipliers)
        assert all(m == 1.0 for m in resolved.ess_exp_multipliers)

    def test_atomic_income_drop(self):
        from src.simulation.scenario_library import ScenarioSpec, resolve_scenario
        spec = ScenarioSpec(type="atomic", components=["S_INC_DROP_20"], start_day=0)
        resolved = resolve_scenario(spec, horizon=60)
        # First 30 days should have 0.80 income multiplier
        assert resolved.income_multipliers[0] == 0.80
        assert resolved.income_multipliers[10] == 0.80
        # After duration, back to 1.0
        assert resolved.income_multipliers[35] == 1.0

    def test_atomic_job_loss_zero_income(self):
        from src.simulation.scenario_library import ScenarioSpec, resolve_scenario
        spec = ScenarioSpec(type="atomic", components=["S_JOB_LOSS"], start_day=0)
        resolved = resolve_scenario(spec, horizon=90)
        # Day 0: income = 0
        assert resolved.income_multipliers[0] == 0.0

    def test_atomic_medical_one_time_expense(self):
        from src.simulation.scenario_library import ScenarioSpec, resolve_scenario
        spec = ScenarioSpec(type="atomic", components=["S_MEDICAL"], start_day=5)
        resolved = resolve_scenario(spec, horizon=30)
        assert 5 in resolved.one_time_expenses
        assert resolved.one_time_expenses[5] > 0

    def test_compound_job_medical(self):
        from src.simulation.scenario_library import ScenarioSpec, resolve_scenario
        spec = ScenarioSpec(type="compound", components=["C_JOB_MEDICAL"], start_day=0)
        resolved = resolve_scenario(spec, horizon=90)
        # Should have income=0 (job loss) AND one-time expense (medical)
        assert resolved.income_multipliers[0] == 0.0
        assert 0 in resolved.one_time_expenses

    def test_cascading_fraud_spiral(self):
        from src.simulation.scenario_library import ScenarioSpec, resolve_scenario
        spec = ScenarioSpec(type="cascading", components=["CA_FRAUD_SPIRAL"], start_day=0)
        resolved = resolve_scenario(spec, horizon=60)
        # Day 0: S_FRAUD (income=0), Day 14+: S_INC_DROP_50
        assert resolved.income_multipliers[0] == 0.0
        assert resolved.income_multipliers[14] <= 0.50

    def test_custom_medical_amount(self):
        from src.simulation.scenario_library import ScenarioSpec, resolve_scenario
        spec = ScenarioSpec(type="atomic", components=["S_MEDICAL"], start_day=0,
                            custom_params={"medical_expense_amount": 90000})
        resolved = resolve_scenario(spec, horizon=10)
        assert resolved.one_time_expenses.get(0, 0) == 90000.0

    def test_list_scenarios_structure(self):
        from src.simulation.scenario_library import list_scenarios
        ls = list_scenarios()
        assert "atomic" in ls and "compound" in ls and "cascading" in ls
        assert "S_INC_DROP_20" in ls["atomic"]
        assert "C_FULL_STRESS" in ls["compound"]


# ═══════════════════════════════════════════════════════════════════════════
# TestEWS
# ═══════════════════════════════════════════════════════════════════════════

class TestEWS:
    def test_ews_zero_when_all_safe(self):
        from src.simulation.ews import compute_ews
        cash = np.full((100, 90), 100_000.0)
        ews = compute_ews(cash, monthly_emi_total=15000, horizon_days=14)
        assert ews == 0.0

    def test_ews_one_when_all_crash(self):
        from src.simulation.ews import compute_ews
        cash = np.full((100, 90), 100.0)  # well below 0.5 × emi
        ews = compute_ews(cash, monthly_emi_total=15000, horizon_days=14)
        assert ews == 1.0

    def test_ews_partial(self):
        from src.simulation.ews import compute_ews
        cash = np.full((100, 90), 100_000.0)
        # 30 paths go below threshold on day 5
        cash[:30, 5] = 100.0
        ews = compute_ews(cash, monthly_emi_total=15000, horizon_days=14)
        assert abs(ews - 0.30) < 0.01

    def test_severity_bands(self):
        from src.simulation.ews import classify_severity
        assert classify_severity(0.10) == "GREEN"
        assert classify_severity(0.20) == "AMBER"
        assert classify_severity(0.40) == "ORANGE"
        assert classify_severity(0.60) == "RED"

    def test_full_ews_keys(self):
        from src.simulation.ews import compute_full_ews
        cash = _cash_paths()
        result = compute_full_ews(cash, monthly_emi_total=15000)
        for key in ["ews_7d", "ews_14d", "ews_30d", "severity", "trigger_recommendation"]:
            assert key in result

    def test_ews_7d_lte_14d_lte_30d(self):
        """EWS at shorter horizon should be <= longer horizon (more time = more paths at risk)."""
        from src.simulation.ews import compute_full_ews
        cash = _cash_paths()
        result = compute_full_ews(cash, monthly_emi_total=15000)
        assert result["ews_7d"] <= result["ews_14d"] <= result["ews_30d"]


# ═══════════════════════════════════════════════════════════════════════════
# TestTailRisk
# ═══════════════════════════════════════════════════════════════════════════

class TestTailRisk:
    def test_var_cvar_positive(self):
        from src.simulation.tail_risk import compute_var_cvar
        cash = _cash_paths()
        var, cvar = compute_var_cvar(cash, cash0=40000)
        assert var >= 0
        assert cvar >= var   # CVaR >= VaR always

    def test_fan_chart_keys(self):
        from src.simulation.tail_risk import extract_fan_chart
        cash = _cash_paths()
        fan = extract_fan_chart(cash)
        for key in ["p10", "p25", "p50", "p75", "p90"]:
            assert key in fan
            assert len(fan[key]) == cash.shape[1]

    def test_fan_chart_monotone_percentiles(self):
        """At each time step, p10 <= p25 <= p50 <= p75 <= p90."""
        from src.simulation.tail_risk import extract_fan_chart
        cash = _cash_paths(n=500)
        fan = extract_fan_chart(cash)
        for t in range(cash.shape[1]):
            assert fan["p10"][t] <= fan["p25"][t] <= fan["p50"][t] <= fan["p75"][t] <= fan["p90"][t]

    def test_temporal_projections_keys(self):
        from src.simulation.tail_risk import compute_temporal_projections
        cash = _cash_paths()
        tp = compute_temporal_projections(cash, cash0=40000, monthly_emi_total=15000,
                                          default_threshold=-5000)
        for day_key in ["day_30", "day_60", "day_90"]:
            assert day_key in tp
            assert "default_probability" in tp[day_key]

    def test_default_probability_in_range(self):
        from src.simulation.tail_risk import default_probability
        cash = _cash_paths()
        dp = default_probability(cash, default_threshold=0.0)
        assert 0.0 <= dp <= 1.0

    def test_net_worth_delta_keys(self):
        from src.simulation.tail_risk import net_worth_delta
        cash = _cash_paths()
        nwd = net_worth_delta(cash, cash0=40000)
        for key in ["mean", "p10", "p50", "p90"]:
            assert key in nwd

    def test_liquidity_crash_when_never_crash(self):
        from src.simulation.tail_risk import liquidity_crash_stats
        cash = np.full((100, 90), 100_000.0)
        stats = liquidity_crash_stats(cash, monthly_emi_total=15000)
        assert stats["mean"] is None

    def test_emi_stress_score_range(self):
        from src.simulation.tail_risk import emi_stress_score
        stages = np.array([0, 1, 2, 3, 4], dtype=np.float32)
        score = emi_stress_score(stages, n_emi_due_dates=3)
        assert 0.0 <= score <= 1.0

    def test_regime_distribution_sums_to_one(self):
        from src.simulation.tail_risk import regime_distribution_at_day
        regimes = np.random.randint(0, 3, (100, 90), dtype=np.int8)
        dist = regime_distribution_at_day(regimes, day=89)
        total = dist["STABLE"] + dist["STRESSED"] + dist["CRISIS"]
        assert abs(total - 1.0) < 0.01


# ═══════════════════════════════════════════════════════════════════════════
# TestRecovery
# ═══════════════════════════════════════════════════════════════════════════

class TestRecovery:
    def test_trivial_plan_when_stable(self):
        from src.simulation.recovery import find_recovery_plan
        plan = find_recovery_plan(regime=0, cash_buffer_days=20, emi_overdue_count=0, emi_monthly=15000)
        assert plan["recovery_probability_full_compliance"] == 1.0
        assert plan["steps"] == []

    def test_plan_has_steps_when_stressed(self):
        from src.simulation.recovery import find_recovery_plan
        # STRESSED (regime=1) with overdue EMI — not at target state, should get steps
        plan = find_recovery_plan(regime=1, cash_buffer_days=8, emi_overdue_count=1, emi_monthly=15000)
        assert len(plan["steps"]) > 0

    def test_plan_keys(self):
        from src.simulation.recovery import find_recovery_plan
        plan = find_recovery_plan(regime=1, cash_buffer_days=8, emi_overdue_count=1, emi_monthly=15000)
        for key in ["plan_id", "steps", "projected_regime_at_45d",
                    "recovery_probability_full_compliance",
                    "recovery_probability_50pct_compliance",
                    "recovery_probability_no_action"]:
            assert key in plan

    def test_step_fields(self):
        from src.simulation.recovery import find_recovery_plan
        plan = find_recovery_plan(regime=2, cash_buffer_days=3, emi_overdue_count=1, emi_monthly=15000)
        if plan["steps"]:
            step = plan["steps"][0]
            for field in ["step", "day", "action", "description", "daily_cf_delta", "success_probability"]:
                assert field in step

    def test_recovery_probabilities_ordered(self):
        from src.simulation.recovery import find_recovery_plan
        plan = find_recovery_plan(regime=1, cash_buffer_days=10, emi_overdue_count=0, emi_monthly=15000)
        if plan["steps"]:
            assert (plan["recovery_probability_full_compliance"] >=
                    plan["recovery_probability_50pct_compliance"] >=
                    plan["recovery_probability_no_action"])

    def test_all_action_ids_valid(self):
        from src.simulation.recovery import find_recovery_plan, ACTIONS
        plan = find_recovery_plan(regime=2, cash_buffer_days=2, emi_overdue_count=2, emi_monthly=15000)
        for step in plan["steps"]:
            assert step["action"] in ACTIONS


# ═══════════════════════════════════════════════════════════════════════════
# TestBayesianUpdater
# ═══════════════════════════════════════════════════════════════════════════

class TestBayesianUpdater:
    def test_income_prior_initializes(self):
        from src.simulation.bayesian_updater import IncomePrior
        prior = IncomePrior(income_mean=50000, income_stability=0.7)
        assert prior.mu > 0
        assert prior.sigma > 0

    def test_update_tightens_sigma(self):
        from src.simulation.bayesian_updater import IncomePrior
        prior = IncomePrior(income_mean=50000, income_stability=0.5)
        sigma_before = prior.sigma
        prior.update(observed_income=52000)
        assert prior.sigma < sigma_before

    def test_update_shifts_mean_toward_observation(self):
        from src.simulation.bayesian_updater import IncomePrior
        import math
        prior = IncomePrior(income_mean=50000, income_stability=0.5)
        mu_before = prior.mu
        # Large positive observation should pull mu up
        prior.update(observed_income=100000, obs_sigma=0.05)
        assert prior.mu > mu_before

    def test_sample_positive(self):
        from src.simulation.bayesian_updater import IncomePrior
        rng = np.random.default_rng(0)
        prior = IncomePrior(income_mean=50000, income_stability=0.7)
        samples = prior.sample(100, rng)
        assert np.all(samples > 0)

    def test_regime_posterior_update_income_event(self):
        from src.simulation.bayesian_updater import regime_posterior_update, IncomePrior
        prior_ip = IncomePrior(50000, 0.7)
        probs = {0: 0.2, 1: 0.5, 2: 0.3}
        # Large income event: P(STABLE) should increase
        updated = regime_posterior_update(probs, "income", 80000, prior_ip)
        assert updated[0] > probs[0]
        total = sum(updated.values())
        assert abs(total - 1.0) < 0.01

    def test_regime_posterior_emi_paid(self):
        from src.simulation.bayesian_updater import regime_posterior_update, IncomePrior
        prior_ip = IncomePrior(50000, 0.7)
        probs = {0: 0.2, 1: 0.5, 2: 0.3}
        updated = regime_posterior_update(probs, "emi_paid", 15000, prior_ip)
        # CRISIS probability should decrease after successful EMI
        assert updated[2] < probs[2]


# ═══════════════════════════════════════════════════════════════════════════
# TestCounterfactual
# ═══════════════════════════════════════════════════════════════════════════

class TestCounterfactual:
    def test_run_counterfactual_keys(self):
        from src.simulation.counterfactual import run_counterfactual
        result = run_counterfactual(
            cf_id="CF_EARLIER_RESTRUC",
            actual_risk_score=0.41,
            actual_cash_buffer_days=14,
            actual_regime="STRESSED",
            cash0=42000,
            income_monthly=50000,
            expense_monthly=30000,
            emi_monthly=15000,
        )
        for key in ["scenario", "lookback_days", "actual_state_today",
                    "counterfactual_state_today", "value_of_earlier_intervention"]:
            assert key in result

    def test_earlier_restructuring_improves_state(self):
        from src.simulation.counterfactual import run_counterfactual
        result = run_counterfactual(
            cf_id="CF_EARLIER_RESTRUC",
            actual_risk_score=0.60,
            actual_cash_buffer_days=5,
            actual_regime="CRISIS",
            cash0=10000,
            income_monthly=50000,
            expense_monthly=35000,
            emi_monthly=15000,
        )
        val = result["value_of_earlier_intervention"]
        # Counterfactual should show improvement
        assert result["counterfactual_state_today"]["risk_score"] <= result["actual_state_today"]["risk_score"]

    def test_micro_loan_one_time_inflow(self):
        from src.simulation.counterfactual import run_counterfactual
        result = run_counterfactual(
            cf_id="CF_MICRO_LOAN_15",
            actual_risk_score=0.50,
            actual_cash_buffer_days=8,
            actual_regime="STRESSED",
            cash0=20000,
            income_monthly=45000,
            expense_monthly=30000,
            emi_monthly=12000,
        )
        assert result["lookback_days"] == 15

    def test_list_counterfactuals(self):
        from src.simulation.counterfactual import list_counterfactuals
        cfs = list_counterfactuals()
        assert "CF_EARLIER_RESTRUC" in cfs
        assert "CF_NO_INTERVENTION" in cfs
        assert isinstance(cfs["CF_EARLIER_RESTRUC"], str)

    def test_unknown_cf_raises(self):
        from src.simulation.counterfactual import run_counterfactual
        with pytest.raises(ValueError, match="Unknown counterfactual"):
            run_counterfactual("CF_NONEXISTENT", 0.3, 15, "STABLE", 40000, 50000, 30000, 15000)


# ═══════════════════════════════════════════════════════════════════════════
# TestEngine
# ═══════════════════════════════════════════════════════════════════════════

class TestEngine:
    def _make_request(self, persona="genuine_struggling", n=200) -> "SimulationRequest":
        from src.simulation.engine import SimulationRequest, TwinSnapshot, VarianceReduction
        twin = TwinSnapshot(
            income_stability=0.65,
            spending_volatility=0.35,
            risk_score=0.40,
            cash_buffer_days=14.0,
            emi_monthly=15000.0,
            emi_overdue_count=0,
            cash_balance_current=42000.0,
            cascade_susceptibility=0.45,
            persona=persona,
            income_monthly=50000.0,
            essential_expense_monthly=20000.0,
            discretionary_expense_monthly=10000.0,
        )
        return SimulationRequest(
            user_id="test_user",
            twin_snapshot=twin,
            num_simulations=n,
            horizon_days=30,
            variance_reduction=VarianceReduction(sobol=False, antithetic=True),
            run_counterfactual=True,
            seed=42,
        )

    def test_engine_runs(self):
        from src.simulation.engine import run_simulation
        req = self._make_request()
        result = run_simulation(req)
        assert result["user_id"] == "test_user"

    def test_result_top_level_keys(self):
        from src.simulation.engine import run_simulation
        req = self._make_request()
        result = run_simulation(req)
        expected_keys = [
            "user_id", "simulation_id", "seed", "horizon_days", "num_paths",
            "default_probability", "temporal_projections", "var_95", "cvar_95",
            "ews", "liquidity_crash_days", "emi_stress_score", "net_worth_delta_90d",
            "regime_distribution_at_90d", "fan_chart", "cascade_analysis",
            "recovery_plan", "counterfactual", "twin_update_emitted", "timestamp",
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_default_probability_in_range(self):
        from src.simulation.engine import run_simulation
        result = run_simulation(self._make_request())
        assert 0.0 <= result["default_probability"] <= 1.0

    def test_fan_chart_has_horizon_days(self):
        from src.simulation.engine import run_simulation
        result = run_simulation(self._make_request())
        fan = result["fan_chart"]
        assert fan["horizon_days"] == 30
        assert len(fan["p50"]) == 30

    def test_ews_keys_present(self):
        from src.simulation.engine import run_simulation
        result = run_simulation(self._make_request())
        ews = result["ews"]
        assert "ews_7d" in ews
        assert "severity" in ews
        assert ews["severity"] in ["GREEN", "AMBER", "ORANGE", "RED"]

    def test_temporal_projections_days(self):
        from src.simulation.engine import run_simulation
        req = self._make_request()
        req.horizon_days = 90  # Need at least 90d for all projections
        result = run_simulation(req)
        assert "day_30" in result["temporal_projections"]
        assert "day_60" in result["temporal_projections"]
        assert "day_90" in result["temporal_projections"]

    def test_cascade_analysis_fractions(self):
        from src.simulation.engine import run_simulation
        result = run_simulation(self._make_request())
        ca = result["cascade_analysis"]
        assert ca["paths_reaching_stage1"] >= ca["paths_reaching_stage2"]

    def test_recovery_plan_returned(self):
        from src.simulation.engine import run_simulation
        result = run_simulation(self._make_request())
        rp = result["recovery_plan"]
        assert "steps" in rp
        assert "recovery_probability_full_compliance" in rp

    def test_counterfactual_returned(self):
        from src.simulation.engine import run_simulation
        result = run_simulation(self._make_request())
        cf = result["counterfactual"]
        if cf is not None:
            assert "scenario" in cf
            assert "actual_state_today" in cf

    def test_deterministic_with_same_seed(self):
        from src.simulation.engine import run_simulation
        req1 = self._make_request()
        req2 = self._make_request()
        r1 = run_simulation(req1)
        r2 = run_simulation(req2)
        assert r1["default_probability"] == r2["default_probability"]

    def test_all_personas(self):
        from src.simulation.engine import run_simulation
        for persona in ["genuine_healthy", "genuine_struggling", "shell_circular",
                        "paper_trader", "new_to_credit"]:
            req = self._make_request(persona=persona, n=50)
            result = run_simulation(req)
            assert "default_probability" in result

    def test_stressed_has_higher_default_than_healthy(self):
        from src.simulation.engine import run_simulation
        # Healthy: high income, low EMI, large cash buffer, 90-day horizon
        req_healthy = self._make_request(persona="genuine_healthy", n=300)
        req_healthy.twin_snapshot.cash_buffer_days = 45.0
        req_healthy.twin_snapshot.cash_balance_current = 100_000.0
        req_healthy.twin_snapshot.income_monthly = 80_000.0
        req_healthy.twin_snapshot.emi_monthly = 5_000.0
        req_healthy.twin_snapshot.essential_expense_monthly = 15_000.0
        req_healthy.twin_snapshot.discretionary_expense_monthly = 5_000.0
        req_healthy.horizon_days = 90
        req_healthy.seed = 42

        # Crisis: very low cash, income barely covers expenses, many missed EMIs
        req_crisis = self._make_request(persona="genuine_struggling", n=300)
        req_crisis.twin_snapshot.cash_buffer_days = 2.0
        req_crisis.twin_snapshot.cash_balance_current = 2_000.0
        req_crisis.twin_snapshot.income_monthly = 25_000.0
        req_crisis.twin_snapshot.emi_monthly = 20_000.0
        req_crisis.twin_snapshot.essential_expense_monthly = 18_000.0
        req_crisis.twin_snapshot.discretionary_expense_monthly = 5_000.0
        req_crisis.twin_snapshot.emi_overdue_count = 2
        req_crisis.horizon_days = 90
        req_crisis.seed = 42

        r_healthy = run_simulation(req_healthy)
        r_crisis  = run_simulation(req_crisis)
        assert r_crisis["default_probability"] > r_healthy["default_probability"]

    def test_scenario_job_loss_reduces_cash(self):
        from src.simulation.engine import run_simulation
        from src.simulation.scenario_library import ScenarioSpec

        req_base = self._make_request(n=200)
        req_base.scenario = ScenarioSpec(type="baseline")
        req_base.seed = 42

        req_stress = self._make_request(n=200)
        req_stress.scenario = ScenarioSpec(type="atomic", components=["S_JOB_LOSS"], start_day=0)
        req_stress.seed = 42

        r_base   = run_simulation(req_base)
        r_stress = run_simulation(req_stress)
        # Stress should have lower median final cash (higher default probability)
        assert r_stress["default_probability"] >= r_base["default_probability"]


# ═══════════════════════════════════════════════════════════════════════════
# TestOutputEmitter
# ═══════════════════════════════════════════════════════════════════════════

class TestOutputEmitter:
    def _make_mock_redis(self) -> MagicMock:
        redis = MagicMock()
        redis.setex = AsyncMock(return_value=True)
        redis.hset = AsyncMock(return_value=True)
        redis.publish = AsyncMock(return_value=1)
        redis.get = AsyncMock(return_value=None)
        return redis

    def _make_sim_result(self) -> dict:
        return {
            "user_id": "u_0001",
            "simulation_id": "sim_test_0001",
            "seed": 42,
            "horizon_days": 90,
            "num_paths": 200,
            "default_probability": 0.15,
            "temporal_projections": {},
            "var_95": -10000,
            "cvar_95": -20000,
            "ews": {"ews_7d": 0.1, "ews_14d": 0.2, "ews_30d": 0.3, "severity": "AMBER"},
            "liquidity_crash_days": {"mean": 45, "p10": 20, "p50": 45, "p90": 80},
            "emi_stress_score": 0.15,
            "net_worth_delta_90d": {"mean": -5000, "p10": -20000, "p50": -4000, "p90": 2000},
            "regime_distribution_at_90d": {"STABLE": 0.6, "STRESSED": 0.3, "CRISIS": 0.1},
            "fan_chart": {"horizon_days": 90, "p10": [40000]*90, "p25": [42000]*90,
                          "p50": [44000]*90, "p75": [46000]*90, "p90": [48000]*90},
            "cascade_analysis": {"paths_reaching_stage1": 0.1, "paths_reaching_stage2": 0.05,
                                  "paths_reaching_stage3": 0.02, "paths_reaching_stage4": 0.01,
                                  "systemic_stress_flag": False},
            "recovery_plan": {"steps": [{"step": 1, "day": 0, "action": "A_EMI_RESTRUC",
                                         "description": "test", "daily_cf_delta": 300,
                                         "success_probability": 0.8}]},
            "counterfactual": None,
            "twin_update_emitted": False,
            "timestamp": "2026-04-11T12:00:00Z",
        }

    def test_emit_sets_keys(self):
        from src.simulation.output_emitter import emit_simulation_completed
        redis = self._make_mock_redis()
        result = self._make_sim_result()
        asyncio.run(emit_simulation_completed(redis, "u_0001", result))
        assert redis.setex.call_count >= 2
        assert redis.hset.called
        assert redis.publish.called

    def test_emit_marks_update(self):
        from src.simulation.output_emitter import emit_simulation_completed
        redis = self._make_mock_redis()
        result = self._make_sim_result()
        asyncio.run(emit_simulation_completed(redis, "u_0001", result))
        assert result["twin_update_emitted"] is True

    def test_get_cached_none_when_missing(self):
        from src.simulation.output_emitter import get_cached_simulation
        redis = self._make_mock_redis()
        cached = asyncio.run(get_cached_simulation(redis, "u_0001", "sim_missing"))
        assert cached is None

    def test_get_ews_snapshot_none_when_missing(self):
        from src.simulation.output_emitter import get_ews_snapshot
        redis = self._make_mock_redis()
        snap = asyncio.run(get_ews_snapshot(redis, "u_0001"))
        assert snap is None


# ═══════════════════════════════════════════════════════════════════════════
# TestAPI (simulation endpoints via FastAPI test client)
# ═══════════════════════════════════════════════════════════════════════════

class FakeRedisForSim:
    """In-memory Redis fake for API tests."""

    def __init__(self) -> None:
        self._store: dict = {}

    async def ping(self) -> bool:
        return True

    async def setex(self, key: str, ttl: int, val: str) -> None:
        self._store[key] = val

    async def get(self, key: str):
        return self._store.get(key)

    async def hset(self, key: str, mapping: dict | None = None, **kwargs) -> None:
        pass

    async def publish(self, channel: str, msg: str) -> None:
        pass

    async def aclose(self) -> None:
        pass


class TestSimulationAPI:
    def _make_app(self):
        from fastapi.testclient import TestClient
        from src.api.main import app
        client = TestClient(app)
        app.state.redis = FakeRedisForSim()
        return client

    def _sim_body(self, persona="unknown", n=50):
        return {
            "user_id": "u_api_test",
            "twin_snapshot": {
                "income_stability": 0.65,
                "spending_volatility": 0.35,
                "risk_score": 0.40,
                "cash_buffer_days": 14.0,
                "emi_monthly": 15000,
                "emi_overdue_count": 0,
                "cash_balance_current": 42000,
                "persona": persona,
                "income_monthly": 50000,
                "essential_expense_monthly": 20000,
                "discretionary_expense_monthly": 10000,
                "overdraft_limit": 5000,
            },
            "horizon_days": 30,
            "num_simulations": n,
            "scenario": {"type": "baseline"},
            "variance_reduction": {"sobol": False, "antithetic": False},
            "run_counterfactual": False,
            "seed": 42,
        }

    def test_simulation_run_200(self):
        client = self._make_app()
        resp = client.post("/simulation/run", json=self._sim_body())
        assert resp.status_code == 200, resp.text

    def test_simulation_run_returns_simulation_id(self):
        client = self._make_app()
        resp = client.post("/simulation/run", json=self._sim_body())
        data = resp.json()
        assert "simulation_id" in data
        assert data["simulation_id"].startswith("sim_")

    def test_simulation_run_missing_user_id_400(self):
        client = self._make_app()
        body = self._sim_body()
        body["user_id"] = ""
        resp = client.post("/simulation/run", json=body)
        assert resp.status_code == 400

    def test_simulation_run_fan_chart_present(self):
        client = self._make_app()
        resp = client.post("/simulation/run", json=self._sim_body())
        data = resp.json()
        fan = data.get("fan_chart", {})
        assert "p50" in fan

    def test_scenarios_endpoint(self):
        client = self._make_app()
        resp = client.get("/simulation/scenarios")
        assert resp.status_code == 200
        data = resp.json()
        assert "atomic" in data
        assert "S_JOB_LOSS" in data["atomic"]

    def test_counterfactuals_endpoint(self):
        client = self._make_app()
        resp = client.get("/simulation/counterfactuals")
        assert resp.status_code == 200
        data = resp.json()
        assert "CF_EARLIER_RESTRUC" in data

    def test_health_endpoint(self):
        client = self._make_app()
        resp = client.get("/simulation/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_ews_404_before_simulation(self):
        client = self._make_app()
        resp = client.get("/simulation/ews/no_such_user")
        assert resp.status_code == 404

    def test_fan_404_before_simulation(self):
        client = self._make_app()
        resp = client.get("/simulation/fan/no_such_user")
        assert resp.status_code == 404

    def test_get_simulation_404_unknown(self):
        client = self._make_app()
        resp = client.get("/simulation/sim_unknown_id_999", params={"user_id": "u_api_test"})
        assert resp.status_code == 404
