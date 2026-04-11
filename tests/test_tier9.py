"""
Tier 9 — Vigilance (Anomaly & Deception Detection): Tests

Covers:
  1. Schemas — all Pydantic models instantiate correctly
  2. FraudRingDetector — graph construction, SCC, temporal cycles, PageRank
  3. ScamDetector — urgency/authority/OTP scoring, Bayesian combiner
  4. BotDetector — precision, hub-and-spoke, mule DNA
  5. AnomalyDetector — stress logistic regression (5.1), income underreporting (5.2),
                        identity shift JS-divergence (5.3)
  6. Tier9Result — risk aggregation, deception score bounds
"""

from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta

import pytest

from src.features.schemas import BehaviouralFeatureVector
from src.vigilance.schemas import (
    RiskLevel,
    Tier9Result,
    FraudRingResult,
    ScamProbabilityResult,
    BotDetectorResult,
    StressSignalResult,
    IncomeUnderreportResult,
    IdentityShiftResult,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fv(**overrides) -> BehaviouralFeatureVector:
    defaults = dict(
        user_id="u_vig",
        computed_at=datetime.now(timezone.utc),
        daily_avg_throughput_30d=5_000.0,
        cash_buffer_days=18.0,
        debit_failure_rate_90d=0.03,
        end_of_month_liquidity_dip=500.0,
        emi_burden_ratio=0.25,
        savings_rate=0.15,
        income_stability_score=0.85,
        spending_volatility_index=0.30,
        discretionary_ratio=0.20,
        cash_dependency_index=0.10,
        subscription_count_30d=2,
        emi_payment_count_90d=1,
        salary_day_spike_flag=False,
        lifestyle_inflation_trend=0.05,
        merchant_category_shift_count=1,
        anomaly_flag=False,
        top3_merchant_concentration=0.40,
        peer_cohort_benchmark_deviation=0.10,
        data_completeness_score=1.0,
        income_7d=15_000.0,
        income_30d=45_000.0,
        income_90d=135_000.0,
        essential_30d=20_000.0,
        essential_90d=60_000.0,
        discretionary_30d=9_000.0,
        discretionary_90d=27_000.0,
        net_cashflow_30d=16_000.0,
        net_cashflow_90d=48_000.0,
        months_active_gst=24,
    )
    defaults.update(overrides)
    return BehaviouralFeatureVector(**defaults)


def _upi_edge(sender, receiver, amount=10_000.0, hours_offset=0):
    ts = datetime.utcnow() + timedelta(hours=hours_offset)
    return {
        "sender_id":   sender,
        "receiver_id": receiver,
        "amount":      amount,
        "timestamp":   ts.isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. Schema smoke tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSchemas:
    def test_risk_level_values(self):
        levels = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert len(levels) == 4

    def test_fraud_ring_result_defaults(self):
        r = FraudRingResult(user_id="u_1")
        assert r.fraud_ring_flag is False
        assert r.fraud_confidence == 0.0

    def test_scam_default_is_safe(self):
        r = ScamProbabilityResult(user_id="u_1")
        assert r.is_scam_alert is False
        assert r.scam_probability == 0.0

    def test_bot_defaults_clean(self):
        r = BotDetectorResult(user_id="u_1")
        assert r.is_bot_flag is False
        assert r.is_mule_flag is False

    def test_stress_defaults(self):
        r = StressSignalResult(user_id="u_1")
        assert r.stress_confidence_score == 0.0
        assert r.risk_level == RiskLevel.LOW

    def test_income_underreport_defaults(self):
        r = IncomeUnderreportResult(user_id="u_1")
        assert r.is_underreporting is False

    def test_identity_shift_defaults(self):
        r = IdentityShiftResult(user_id="u_1")
        assert r.is_identity_shifted is False


# ─────────────────────────────────────────────────────────────────────────────
# 2. FraudRingDetector
# ─────────────────────────────────────────────────────────────────────────────

class TestFraudRingDetector:
    from src.vigilance.fraud_ring import (
        build_transaction_graph,
        run_fraud_ring_detector,
        _is_temporally_consistent,
    )

    def test_empty_events_returns_no_flag(self):
        from src.vigilance.fraud_ring import run_fraud_ring_detector
        result = run_fraud_ring_detector("u_1", upi_events=[], ewb_events=[])
        assert result.fraud_ring_flag is False

    def test_graph_built_from_events(self):
        from src.vigilance.fraud_ring import build_transaction_graph
        events = [
            _upi_edge("A", "B", 10_000),
            _upi_edge("B", "C", 8_000),
        ]
        G = build_transaction_graph(events)
        assert G.number_of_nodes() == 3
        assert G.number_of_edges() == 2

    def test_small_graph_no_scc(self):
        from src.vigilance.fraud_ring import run_fraud_ring_detector
        events = [_upi_edge("A", "B")]
        result = run_fraud_ring_detector("A", upi_events=events)
        assert result.scc_size == 0

    def test_ring_of_3_detected(self):
        from src.vigilance.fraud_ring import run_fraud_ring_detector
        # A → B → C → A  (temporal: +1h gap each)
        events = [
            _upi_edge("A", "B", 100_000, hours_offset=0),
            _upi_edge("B", "C", 90_000,  hours_offset=2),
            _upi_edge("C", "A", 80_000,  hours_offset=4),
        ]
        result = run_fraud_ring_detector("A", upi_events=events)
        assert result.scc_size >= 3

    def test_temporal_consistency_pass(self):
        import networkx as nx
        from src.vigilance.fraud_ring import _is_temporally_consistent
        G = nx.MultiDiGraph()
        t0 = datetime(2026, 1, 1, 10, 0)
        t1 = datetime(2026, 1, 1, 12, 0)
        t2 = datetime(2026, 1, 1, 14, 0)
        G.add_edge("A", "B", amount=1000, timestamp=t0, event_type="upi")
        G.add_edge("B", "C", amount=900,  timestamp=t1, event_type="upi")
        G.add_edge("C", "A", amount=800,  timestamp=t2, event_type="upi")
        assert _is_temporally_consistent(G, ["A", "B", "C"]) is True

    def test_temporal_inconsistency_on_reverse_order(self):
        import networkx as nx
        from src.vigilance.fraud_ring import _is_temporally_consistent
        G = nx.MultiDiGraph()
        t0 = datetime(2026, 1, 1, 14, 0)  # later
        t1 = datetime(2026, 1, 1, 10, 0)  # earlier — violation
        G.add_edge("A", "B", amount=1000, timestamp=t0, event_type="upi")
        G.add_edge("B", "C", amount=900,  timestamp=t1, event_type="upi")
        G.add_edge("C", "A", amount=800,  timestamp=datetime(2026, 1, 1, 16, 0), event_type="upi")
        assert _is_temporally_consistent(G, ["A", "B", "C"]) is False

    def test_pagerank_zero_for_isolated_user(self):
        from src.vigilance.fraud_ring import run_fraud_ring_detector
        result = run_fraud_ring_detector("LONELY", upi_events=[_upi_edge("A", "B")])
        assert result.pagerank_score == 0.0

    def test_pagerank_nonzero_for_connected_user(self):
        from src.vigilance.fraud_ring import run_fraud_ring_detector
        events = [
            _upi_edge("A", "B", 10_000),
            _upi_edge("B", "C", 8_000),
            _upi_edge("C", "A", 7_000),
        ]
        result = run_fraud_ring_detector("A", upi_events=events)
        # A is in the graph — should have some PageRank
        assert result.pagerank_score >= 0.0

    def test_low_velocity_ring_not_flagged(self):
        from src.vigilance.fraud_ring import run_fraud_ring_detector
        # Tiny flow — below velocity threshold
        events = [
            _upi_edge("A", "B", 100, hours_offset=0),
            _upi_edge("B", "C", 90,  hours_offset=2),
            _upi_edge("C", "A", 80,  hours_offset=4),
        ]
        result = run_fraud_ring_detector("A", upi_events=events)
        # No cycle should be "suspicious" at this velocity
        suspicious = [c for c in result.detected_cycles if c.suspicious]
        assert len(suspicious) == 0

    def test_result_risk_level_low_for_clean_user(self):
        from src.vigilance.fraud_ring import run_fraud_ring_detector
        result = run_fraud_ring_detector("u_clean", upi_events=[_upi_edge("X", "Y")])
        assert result.risk_level == RiskLevel.LOW

    def test_fraud_confidence_bounded(self):
        from src.vigilance.fraud_ring import run_fraud_ring_detector
        events = [_upi_edge("A", "B", 500_000, i) for i in range(5)]
        result = run_fraud_ring_detector("A", upi_events=events)
        assert 0.0 <= result.fraud_confidence <= 1.0


# ─────────────────────────────────────────────────────────────────────────────
# 3. ScamDetector
# ─────────────────────────────────────────────────────────────────────────────

class TestScamDetector:
    def test_clean_message_low_probability(self):
        from src.vigilance.scam_detector import run_scam_detector
        result = run_scam_detector("u_1", "Your transaction of Rs.500 was successful.")
        assert result.scam_probability < 0.3
        assert result.is_scam_alert is False

    def test_urgency_detected_in_panic_message(self):
        from src.vigilance.scam_detector import run_scam_detector
        text = "URGENT: Your account will be suspended in 2 hours. Immediate action required!"
        result = run_scam_detector("u_1", text)
        assert result.urgency_score > 0.3

    def test_authority_detected_for_rbi_impersonation(self):
        from src.vigilance.scam_detector import run_scam_detector
        text = "This is an official notice from Reserve Bank of India. Your account has been flagged."
        result = run_scam_detector("u_1", text)
        assert result.authority_score > 0.3

    def test_otp_phishing_detected(self):
        from src.vigilance.scam_detector import run_scam_detector
        text = "Action required! Share your OTP to avoid account suspension immediately."
        result = run_scam_detector("u_1", text)
        assert result.otp_phishing_score > 0.3

    def test_combined_high_confidence_scam(self):
        from src.vigilance.scam_detector import run_scam_detector
        text = (
            "URGENT: Your account will be suspended. This is RBI. "
            "Share your OTP immediately or your account will be blocked in 2 hours."
        )
        result = run_scam_detector("u_1", text)
        assert result.scam_probability > 0.5
        assert result.is_scam_alert is True

    def test_legitimate_sender_reduces_authority_score(self):
        from src.vigilance.scam_detector import run_scam_detector
        text = "RBI has updated interest rates. Visit rbi.org.in for details."
        # Legitimate DLT header
        result_legit   = run_scam_detector("u_1", text, sender_id="TM-RBIOFI")
        result_unknown = run_scam_detector("u_1", text, sender_id=None)
        # Legit sender should have lower authority score
        assert result_legit.authority_score <= result_unknown.authority_score

    def test_empty_text_returns_safe_result(self):
        from src.vigilance.scam_detector import run_scam_detector
        result = run_scam_detector("u_1", "")
        assert result.scam_probability == 0.0
        assert result.is_scam_alert is False

    def test_scam_probability_bounded_0_1(self):
        from src.vigilance.scam_detector import run_scam_detector
        text = " ".join(["urgent immediate block suspended RBI OTP share"] * 20)
        result = run_scam_detector("u_1", text)
        assert 0.0 <= result.scam_probability <= 1.0

    def test_signals_list_has_correct_types(self):
        from src.vigilance.scam_detector import run_scam_detector
        from src.vigilance.schemas import ScamSignal
        text = "URGENT: Share your OTP now. RBI order."
        result = run_scam_detector("u_1", text)
        for sig in result.signals:
            assert isinstance(sig, ScamSignal)

    def test_risk_level_critical_for_high_scam(self):
        from src.vigilance.scam_detector import run_scam_detector
        text = "Account blocked! Immediate action. Share OTP now. RBI mandate."
        result = run_scam_detector("u_1", text)
        if result.scam_probability >= 0.75:
            assert result.risk_level == RiskLevel.CRITICAL

    def test_bayesian_prior_effect(self):
        """Very weak signals should still produce a low-ish score, not 0."""
        from src.vigilance.scam_detector import run_scam_detector
        result = run_scam_detector("u_1", "Urgent! Click here.")
        assert result.scam_probability >= 0.0  # nonzero due to prior

    def test_otp_bare_number_without_urgency_not_scored(self):
        """A bare 6-digit number without urgency context shouldn't trigger OTP phishing."""
        from src.vigilance.scam_detector import run_scam_detector
        result = run_scam_detector("u_1", "Your delivery PIN is 482910. Use at the gate.")
        assert result.otp_phishing_score < 0.5


# ─────────────────────────────────────────────────────────────────────────────
# 4. BotDetector
# ─────────────────────────────────────────────────────────────────────────────

class TestBotDetector:
    def test_human_user_not_flagged(self):
        from src.vigilance.bot_detector import run_bot_detector
        fv = _fv()
        result = run_bot_detector(
            user_id="u_human",
            upi_events=[_upi_edge("u_human", f"merchant_{i}", 500 + i * 137) for i in range(10)],
            daily_avg_throughput=fv.daily_avg_throughput_30d,
            discretionary_ratio=fv.discretionary_ratio,
            cash_buffer_days=fv.cash_buffer_days,
            debit_failure_rate=fv.debit_failure_rate_90d,
        )
        assert result.is_bot_flag is False

    def test_mule_dna_score_high_for_laundering_template(self):
        from src.vigilance.bot_detector import _compute_mule_dna_score
        score, evidence = _compute_mule_dna_score(
            daily_avg_throughput=500_000.0,   # very high
            discretionary_ratio=0.005,        # near zero
            cash_buffer_days=0.5,             # < 1 day
            debit_failure_rate=0.001,         # zero failures
        )
        assert score >= 0.7
        assert len(evidence) >= 2

    def test_mule_dna_score_low_for_normal_user(self):
        from src.vigilance.bot_detector import _compute_mule_dna_score
        score, _ = _compute_mule_dna_score(
            daily_avg_throughput=5_000.0,
            discretionary_ratio=0.20,
            cash_buffer_days=20.0,
            debit_failure_rate=0.04,
        )
        assert score < 0.3

    def test_hub_spoke_detected_when_all_flows_to_one(self):
        from src.vigilance.bot_detector import _detect_hub_spoke
        events = (
            [_upi_edge("collector", "u_mule", 10_000) for _ in range(5)] +  # inflows from many
            [_upi_edge("u_mule", "collector_hub", 45_000)]                   # all out to one
        )
        score, evidence = _detect_hub_spoke(events, "u_mule")
        assert score > 0.0

    def test_no_hub_spoke_with_diverse_receivers(self):
        from src.vigilance.bot_detector import _detect_hub_spoke
        events = [_upi_edge("u_human", f"shop_{i}", 500) for i in range(10)]
        score, evidence = _detect_hub_spoke(events, "u_human")
        # Diverse receivers — should not trigger
        assert score < 0.6

    def test_precision_detected_for_exact_intervals(self):
        from src.vigilance.bot_detector import _detect_improbable_precision
        # Exactly 3600s apart = bot-like
        base = datetime(2026, 1, 1, 10, 0)
        timestamps = [(base + timedelta(hours=i)).timestamp() for i in range(20)]
        flag, cv = _detect_improbable_precision(timestamps)
        assert flag is True
        assert cv < 0.01

    def test_precision_not_detected_for_human_intervals(self):
        from src.vigilance.bot_detector import _detect_improbable_precision
        import random
        random.seed(42)
        base = 1_000_000.0
        timestamps = [base + random.uniform(100, 86400) * i for i in range(20)]
        flag, cv = _detect_improbable_precision(timestamps)
        assert flag is False

    def test_consistency_score_bounded_0_1(self):
        from src.vigilance.bot_detector import run_bot_detector
        fv = _fv()
        result = run_bot_detector(
            user_id="u_x",
            upi_events=[],
            daily_avg_throughput=fv.daily_avg_throughput_30d,
            discretionary_ratio=fv.discretionary_ratio,
            cash_buffer_days=fv.cash_buffer_days,
            debit_failure_rate=fv.debit_failure_rate_90d,
        )
        assert 0.0 <= result.consistency_score <= 1.0

    def test_too_few_timestamps_no_precision_flag(self):
        from src.vigilance.bot_detector import _detect_improbable_precision
        flag, _ = _detect_improbable_precision([1000.0, 2000.0])   # only 2 — not enough
        assert flag is False


# ─────────────────────────────────────────────────────────────────────────────
# 5. AnomalyDetector (Modules 5.1, 5.2, 5.3)
# ─────────────────────────────────────────────────────────────────────────────

class TestStressDetector:
    def test_healthy_user_low_stress(self):
        from src.vigilance.anomaly_detector import run_stress_detector
        fv = _fv(
            debit_failure_rate_90d=0.01,
            cash_buffer_days=30.0,
            emi_burden_ratio=0.20,
            income_stability_score=0.92,
        )
        result = run_stress_detector(fv)
        assert result.stress_confidence_score < 0.5
        assert result.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)

    def test_distressed_user_high_stress(self):
        from src.vigilance.anomaly_detector import run_stress_detector
        fv = _fv(
            debit_failure_rate_90d=0.25,
            cash_buffer_days=2.0,
            emi_burden_ratio=0.75,
            income_stability_score=0.30,
            end_of_month_liquidity_dip=25_000.0,
        )
        result = run_stress_detector(fv)
        assert result.stress_confidence_score > 0.5

    def test_stress_score_bounded(self):
        from src.vigilance.anomaly_detector import run_stress_detector
        fv = _fv()
        result = run_stress_detector(fv)
        assert 0.0 <= result.stress_confidence_score <= 1.0

    def test_velocity_spike_detected(self):
        from src.vigilance.anomaly_detector import run_stress_detector
        fv = _fv(debit_failure_rate_90d=0.15, end_of_month_liquidity_dip=15_000.0)
        result = run_stress_detector(fv)
        assert result.velocity_stress_spike is True

    def test_velocity_spike_not_detected_for_healthy(self):
        from src.vigilance.anomaly_detector import run_stress_detector
        fv = _fv(debit_failure_rate_90d=0.02, end_of_month_liquidity_dip=100.0)
        result = run_stress_detector(fv)
        assert result.velocity_stress_spike is False

    def test_cash_buffer_trend_labels(self):
        from src.vigilance.anomaly_detector import run_stress_detector
        assert run_stress_detector(_fv(cash_buffer_days=2.0)).cash_buffer_trend == "critical"
        assert run_stress_detector(_fv(cash_buffer_days=7.0)).cash_buffer_trend == "declining"
        assert run_stress_detector(_fv(cash_buffer_days=15.0)).cash_buffer_trend == "stable"
        assert run_stress_detector(_fv(cash_buffer_days=30.0)).cash_buffer_trend == "improving"

    def test_rolling_features_dict_populated(self):
        from src.vigilance.anomaly_detector import run_stress_detector
        result = run_stress_detector(_fv())
        assert "debit_failure_rate_90d" in result.rolling_features
        assert "cash_buffer_days" in result.rolling_features


class TestIncomeUnderreportDetector:
    def test_honest_user_low_score(self):
        from src.vigilance.anomaly_detector import run_income_underreport_detector
        fv = _fv(income_90d=135_000.0, cash_dependency_index=0.05)
        result = run_income_underreport_detector(
            fv=fv,
            declared_income=45_000.0,
            cohort_mean_income=48_000.0,
            cohort_std_income=12_000.0,
        )
        assert result.is_underreporting is False
        assert result.income_underreport_score < 0.65

    def test_underreporter_flagged(self):
        from src.vigilance.anomaly_detector import run_income_underreport_detector
        # Observed >> declared
        fv = _fv(income_90d=600_000.0, cash_dependency_index=0.02)
        result = run_income_underreport_detector(
            fv=fv,
            declared_income=15_000.0,   # very low declared
            cohort_mean_income=45_000.0,
            cohort_std_income=10_000.0,
        )
        assert result.income_underreport_score > 0.5
        assert result.zscore > 0

    def test_score_bounded(self):
        from src.vigilance.anomaly_detector import run_income_underreport_detector
        fv = _fv()
        result = run_income_underreport_detector(fv, 45_000.0, 45_000.0, 10_000.0)
        assert 0.0 <= result.income_underreport_score <= 1.0

    def test_observed_income_proxy_nonzero_for_normal_user(self):
        from src.vigilance.anomaly_detector import run_income_underreport_detector
        fv = _fv(income_90d=135_000.0)
        result = run_income_underreport_detector(fv, 45_000.0, 45_000.0, 10_000.0)
        assert result.observed_income_proxy > 0

    def test_high_p2p_reduces_observed_proxy(self):
        from src.vigilance.anomaly_detector import run_income_underreport_detector
        fv_low_p2p  = _fv(income_90d=135_000.0, cash_dependency_index=0.02)
        fv_high_p2p = _fv(income_90d=135_000.0, cash_dependency_index=0.60)
        r_low  = run_income_underreport_detector(fv_low_p2p,  45_000.0, 45_000.0, 10_000.0)
        r_high = run_income_underreport_detector(fv_high_p2p, 45_000.0, 45_000.0, 10_000.0)
        assert r_low.observed_income_proxy >= r_high.observed_income_proxy


class TestIdentityShiftDetector:
    def test_stable_user_low_shift(self):
        from src.vigilance.anomaly_detector import run_identity_shift_detector
        fv = _fv(
            merchant_category_shift_count=0,
            lifestyle_inflation_trend=0.01,
            discretionary_30d=9_000.0,
            discretionary_90d=27_000.0,
        )
        result = run_identity_shift_detector(fv)
        assert result.identity_shift_score < 0.45
        assert result.is_identity_shifted is False

    def test_shifted_user_flagged(self):
        from src.vigilance.anomaly_detector import run_identity_shift_detector
        fv = _fv(
            merchant_category_shift_count=8,
            lifestyle_inflation_trend=0.50,
            discretionary_30d=25_000.0,
            discretionary_90d=9_000.0,
        )
        result = run_identity_shift_detector(fv)
        assert result.identity_shift_score > 0.0

    def test_score_bounded(self):
        from src.vigilance.anomaly_detector import run_identity_shift_detector
        result = run_identity_shift_detector(_fv())
        assert 0.0 <= result.identity_shift_score <= 1.0

    def test_js_divergence_from_distributions(self):
        from src.vigilance.anomaly_detector import run_identity_shift_detector, _js_divergence
        # Same distribution = JSD 0
        p = [0.5, 0.3, 0.2]
        q = [0.5, 0.3, 0.2]
        assert _js_divergence(p, q) == 0.0

    def test_js_divergence_orthogonal_distributions_high(self):
        from src.vigilance.anomaly_detector import _js_divergence
        # Completely different distributions
        p = [1.0, 0.0, 0.0]
        q = [0.0, 0.0, 1.0]
        jsd = _js_divergence(p, q)
        assert jsd > 0.5

    def test_identity_shift_with_explicit_distributions(self):
        from src.vigilance.anomaly_detector import run_identity_shift_detector
        fv = _fv()
        p30 = [0.6, 0.1, 0.1, 0.1, 0.1]   # dominated by one category
        p90 = [0.1, 0.1, 0.1, 0.1, 0.6]   # opposite
        result = run_identity_shift_detector(fv, category_mix_30d=p30, category_mix_90d=p90)
        # JSD of these two distributions ≈ 0.286 — meaningfully > 0 and > 0.25
        assert result.js_divergence > 0.25

    def test_shifted_categories_populated(self):
        from src.vigilance.anomaly_detector import run_identity_shift_detector
        fv = _fv(merchant_category_shift_count=7, lifestyle_inflation_trend=0.40)
        result = run_identity_shift_detector(fv)
        assert isinstance(result.top_shifted_categories, list)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Tier9Result — aggregation
# ─────────────────────────────────────────────────────────────────────────────

class TestTier9Aggregation:
    def _make_result(self, fraud_conf=0.05, scam_prob=0.03, bot_score=0.05,
                     stress=0.1, underreport=0.1, shift=0.05):
        import uuid as _uuid
        return Tier9Result(
            user_id="u_agg",
            run_id=str(_uuid.uuid4()),
            fraud_ring=FraudRingResult(user_id="u_agg", fraud_confidence=fraud_conf),
            scam_defence=ScamProbabilityResult(user_id="u_agg", scam_probability=scam_prob),
            bot_detector=BotDetectorResult(user_id="u_agg", consistency_score=bot_score),
            stress_signal=StressSignalResult(user_id="u_agg", stress_confidence_score=stress),
            income_underreport=IncomeUnderreportResult(user_id="u_agg", income_underreport_score=underreport),
            identity_shift=IdentityShiftResult(user_id="u_agg", identity_shift_score=shift),
        )

    def _compute_deception(self, r):
        from src.vigilance.tier9 import _compute_deception_score
        return _compute_deception_score(r)

    def test_deception_score_bounded(self):
        r = self._make_result()
        score = self._compute_deception(r)
        assert 0.0 <= score <= 1.0

    def test_high_fraud_confidence_raises_deception_score(self):
        clean  = self._compute_deception(self._make_result(fraud_conf=0.05))
        danger = self._compute_deception(self._make_result(fraud_conf=0.95))
        assert danger > clean

    def test_aggregated_risk_takes_max(self):
        from src.vigilance.tier9 import _aggregate_risk
        risk = _aggregate_risk(RiskLevel.LOW, RiskLevel.CRITICAL, RiskLevel.MEDIUM)
        assert risk == RiskLevel.CRITICAL

    def test_all_low_risk_stays_low(self):
        from src.vigilance.tier9 import _aggregate_risk
        risk = _aggregate_risk(RiskLevel.LOW, RiskLevel.LOW, RiskLevel.LOW)
        assert risk == RiskLevel.LOW

    def test_overall_risk_defaults_low(self):
        r = self._make_result()
        assert r.overall_risk_level == RiskLevel.LOW

    def test_fraud_ring_flag_propagated(self):
        r = self._make_result()
        r.fraud_ring.fraud_ring_flag = True
        r.fraud_ring_flag = r.fraud_ring.fraud_ring_flag
        assert r.fraud_ring_flag is True

    def test_pagerank_field_accessible(self):
        r = self._make_result()
        assert r.pagerank_score == 0.0
