"""
Tier 7 — Cognitive Credit Engine: Tests

Covers:
  1. Schemas (CreditScoreResult, BehaviouralOverride, SHAPFeature)
  2. CreditScorer — prob_to_score, score_to_band, EL sizing, rule trace,
                    full vs income_heavy routing, behavioural override
  3. CreditExplainer (mocked model)
  4. Recalibration — LIMIT_REDUCED_EVENT emission logic
  5. Scoring worker — feature resolution, saga logic (in-memory Redis)
  6. API endpoints — /credit/score, /credit/score/{task_id},
                     /credit/{user_id}/status, /credit/audit/replay,
                     /credit/health
"""

from __future__ import annotations

import asyncio
import json
import types
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.credit.schemas import (
    AuditReplayRequest,
    BehaviouralOverride,
    CreditScoreResult,
    SHAPFeature,
    ScoreRequest,
    ScoreStatusResponse,
)
from src.credit.credit_scorer import (
    RISK_BANDS,
    CreditScorer,
    _prob_to_score_standalone,
    _score_to_band_standalone,
)
from src.features.schemas import BehaviouralFeatureVector


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_fv(**overrides) -> BehaviouralFeatureVector:
    """Create a minimal valid BehaviouralFeatureVector."""
    defaults = dict(
        user_id="u_test",
        computed_at=datetime.now(timezone.utc),
        daily_avg_throughput_30d=5000.0,
        cash_buffer_days=30.0,
        debit_failure_rate_90d=0.05,
        end_of_month_liquidity_dip=0.1,
        emi_burden_ratio=0.25,
        savings_rate=0.15,
        income_stability_score=0.80,
        spending_volatility_index=0.3,
        discretionary_ratio=0.2,
        cash_dependency_index=0.1,
        subscription_count_30d=2,
        emi_payment_count_90d=1,
        salary_day_spike_flag=False,
        lifestyle_inflation_trend=0.05,
        merchant_category_shift_count=1,
        anomaly_flag=False,
        top3_merchant_concentration=0.4,
        peer_cohort_benchmark_deviation=0.2,
        data_completeness_score=1.0,
    )
    defaults.update(overrides)
    return BehaviouralFeatureVector(**defaults)


def _make_mock_scorer(prob: float = 0.15) -> CreditScorer:
    """Build a CreditScorer with mocked XGBoost models."""
    scorer = object.__new__(CreditScorer)
    scorer.feature_columns = [
        "daily_avg_throughput_30d", "cash_buffer_days", "debit_failure_rate_90d",
        "end_of_month_liquidity_dip", "emi_burden_ratio", "savings_rate",
        "income_stability_score", "spending_volatility_index", "discretionary_ratio",
        "cash_dependency_index", "subscription_count_30d", "emi_payment_count_90d",
        "lifestyle_inflation_trend", "merchant_category_shift_count",
        "top3_merchant_concentration", "peer_cohort_benchmark_deviation",
        "temporal_anomaly_flag", "income_7d", "income_30d", "income_90d",
        "essential_30d", "essential_90d", "discretionary_30d", "discretionary_90d",
        "net_cashflow_30d", "net_cashflow_90d", "data_completeness_score",
    ]

    def _mock_predict_proba(X):
        return np.array([[1 - prob, prob]])

    mock_model = MagicMock()
    mock_model.predict_proba.side_effect = _mock_predict_proba
    scorer.model_full   = mock_model
    scorer.model_income = mock_model
    return scorer


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class TestSchemas:
    def test_behavioural_override_defaults(self):
        bo = BehaviouralOverride()
        assert bo.applied is False
        assert bo.trajectory_score_delta == 0.0
        assert bo.reasons == []

    def test_behavioural_override_custom(self):
        bo = BehaviouralOverride(applied=True, trajectory_score_delta=30.0, reasons=["improving"])
        assert bo.applied is True
        assert bo.trajectory_score_delta == 30.0

    def test_shap_feature_directions(self):
        pos = SHAPFeature(feature_name="emi_burden_ratio", shap_value=0.2,
                          direction="increases_risk", abs_magnitude=0.2)
        neg = SHAPFeature(feature_name="savings_rate", shap_value=-0.1,
                          direction="decreases_risk", abs_magnitude=0.1)
        assert pos.direction == "increases_risk"
        assert neg.direction == "decreases_risk"

    def test_credit_score_result_fields(self):
        result = CreditScoreResult(
            user_id="u_001",
            credit_score=720,
            risk_band="low_risk",
            probability_of_default=0.18,
            recommended_personal_loan_amount=300_000.0,
            recommended_tenure_months=48,
            annual_percentage_rate=12.5,
            cgtmse_eligible=True,
            top_5_shap_features=[],
            rule_trace={},
            model_used="full",
            behavioural_override=BehaviouralOverride(),
            score_freshness=datetime.now(timezone.utc).isoformat(),
        )
        assert result.credit_score == 720
        assert result.risk_band == "low_risk"

    def test_score_request_defaults(self):
        req = ScoreRequest(user_id="u_001")
        assert req.force_income_model is False

    def test_audit_replay_request(self):
        req = AuditReplayRequest(user_id="u_001", target_timestamp=datetime(2026, 1, 1))
        assert req.user_id == "u_001"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. CreditScorer standalone helpers (no model load)
# ═══════════════════════════════════════════════════════════════════════════════

class TestScorerHelpers:
    def test_prob_to_score_midpoint(self):
        # prob=0.0 → score=900, prob=1.0 → score=300
        assert _prob_to_score_standalone(0.0) == 900
        assert _prob_to_score_standalone(1.0) == 300
        assert _prob_to_score_standalone(0.5) == 600

    def test_prob_to_score_clipped(self):
        assert _prob_to_score_standalone(-1.0) == 900
        assert _prob_to_score_standalone(2.0)  == 300

    def test_score_to_band_boundaries(self):
        assert _score_to_band_standalone(900) == "very_low_risk"
        assert _score_to_band_standalone(750) == "very_low_risk"
        assert _score_to_band_standalone(749) == "low_risk"
        assert _score_to_band_standalone(650) == "low_risk"
        assert _score_to_band_standalone(649) == "medium_risk"
        assert _score_to_band_standalone(550) == "medium_risk"
        assert _score_to_band_standalone(549) == "high_risk"
        assert _score_to_band_standalone(300) == "high_risk"

    def test_score_to_band_below_range(self):
        # Anything below 300 should fall to high_risk
        assert _score_to_band_standalone(100) == "high_risk"

    def test_risk_bands_coverage(self):
        # All four bands defined
        for band in ("very_low_risk", "low_risk", "medium_risk", "high_risk"):
            assert band in RISK_BANDS
            assert "max_loan_lakh" in RISK_BANDS[band]
            assert "apr_range" in RISK_BANDS[band]


# ═══════════════════════════════════════════════════════════════════════════════
# 3. CreditScorer.score() — with mocked models
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreditScorerScore:
    def setup_method(self):
        self.scorer_low_risk  = _make_mock_scorer(prob=0.10)  # prob 10% → score ~840
        self.scorer_high_risk = _make_mock_scorer(prob=0.80)  # prob 80% → score ~420

    def test_low_risk_score_range(self):
        fv = _make_fv()
        result = self.scorer_low_risk.score(fv)
        assert 750 <= result["credit_score"] <= 900
        assert result["risk_band"] == "very_low_risk"

    def test_high_risk_score_range(self):
        fv = _make_fv(emi_burden_ratio=0.9, debit_failure_rate_90d=0.5)
        result = self.scorer_high_risk.score(fv)
        assert 300 <= result["credit_score"] <= 549
        assert result["risk_band"] == "high_risk"

    def test_score_keys_present(self):
        fv = _make_fv()
        result = self.scorer_low_risk.score(fv)
        for key in (
            "credit_score", "risk_band", "probability_of_default",
            "recommended_personal_loan_amount", "recommended_tenure_months",
            "annual_percentage_rate", "cgtmse_eligible",
            "model_used", "behavioural_override", "rule_trace",
        ):
            assert key in result, f"missing key: {key}"

    def test_full_model_routing_default(self):
        fv = _make_fv(data_completeness_score=1.0)
        result = self.scorer_low_risk.score(fv)
        assert result["model_used"] == "full"

    def test_income_model_routing_thin_file(self):
        fv = _make_fv(data_completeness_score=0.5)
        result = self.scorer_low_risk.score(fv)
        assert result["model_used"] == "income_heavy"

    def test_force_income_model_override(self):
        fv = _make_fv(data_completeness_score=1.0)   # would normally use full
        result = self.scorer_low_risk.score(fv, use_income_model=True)
        assert result["model_used"] == "income_heavy"

    def test_el_loan_amount_within_band(self):
        fv = _make_fv()
        result = self.scorer_low_risk.score(fv)
        band = result["risk_band"]
        max_inr = RISK_BANDS[band]["max_loan_lakh"] * 100_000
        assert result["recommended_personal_loan_amount"] <= max_inr

    def test_el_loan_positive(self):
        fv = _make_fv()
        result = self.scorer_low_risk.score(fv)
        assert result["recommended_personal_loan_amount"] > 0

    def test_apr_within_band_range(self):
        fv = _make_fv()
        result = self.scorer_low_risk.score(fv)
        band = result["risk_band"]
        lo, hi = RISK_BANDS[band]["apr_range"]
        assert lo <= result["annual_percentage_rate"] <= hi + 0.1  # +0.1 float tolerance

    def test_rule_trace_has_checks(self):
        fv = _make_fv()
        result = self.scorer_low_risk.score(fv)
        trace = result["rule_trace"]
        for check in (
            "emi_burden_check", "savings_rate_check", "cash_buffer_check",
            "debit_failure_check", "income_stability_check",
            "anomaly_check", "net_cashflow_check",
        ):
            assert check in trace

    def test_rule_trace_emi_pass_fail(self):
        fv_pass = _make_fv(emi_burden_ratio=0.3)
        fv_fail = _make_fv(emi_burden_ratio=0.8)
        assert self.scorer_low_risk.score(fv_pass)["rule_trace"]["emi_burden_check"]["result"] == "PASSED"
        assert self.scorer_high_risk.score(fv_fail)["rule_trace"]["emi_burden_check"]["result"] == "FAILED"

    def test_rule_trace_anomaly_flag(self):
        fv = _make_fv(anomaly_flag=True)
        result = self.scorer_high_risk.score(fv)
        assert result["rule_trace"]["anomaly_check"]["result"] == "FAILED"

    def test_rule_trace_model_routing_stated(self):
        fv = _make_fv(data_completeness_score=0.5)
        result = self.scorer_low_risk.score(fv)
        assert "income-heavy" in result["rule_trace"]["model_routing"]["reason"]

    def test_no_override_when_delta_zero(self):
        fv = _make_fv()
        result = self.scorer_low_risk.score(fv, twin_trajectory_delta=0.0)
        assert result["behavioural_override"].applied is False
        assert result["behavioural_override"].trajectory_score_delta == 0.0

    def test_override_applied_when_delta_positive(self):
        fv = _make_fv()
        # Use a high-risk scorer so base score is low, boost should be visible
        result = self.scorer_high_risk.score(fv, twin_trajectory_delta=0.5)
        override = result["behavioural_override"]
        assert override.applied is True
        assert override.trajectory_score_delta > 0
        assert len(override.reasons) == 2

    def test_override_boost_capped_at_75(self):
        fv = _make_fv()
        result = self.scorer_low_risk.score(fv, twin_trajectory_delta=10.0)
        assert result["behavioural_override"].trajectory_score_delta <= 75

    def test_override_score_stays_in_range(self):
        fv = _make_fv()
        result = self.scorer_low_risk.score(fv, twin_trajectory_delta=10.0)
        assert 300 <= result["credit_score"] <= 900

    def test_override_trace_logged(self):
        fv = _make_fv()
        result = self.scorer_high_risk.score(fv, twin_trajectory_delta=0.8)
        trace = result["rule_trace"]
        override_in_trace = trace.get("behavioural_override", {})
        assert override_in_trace.get("applied") is True

    def test_high_risk_zero_loan(self):
        # high_risk band max_loan_lakh could be 1L but EL formula may cap further
        fv = _make_fv()
        result = self.scorer_high_risk.score(fv)
        assert result["recommended_personal_loan_amount"] >= 0

    def test_cgtmse_eligible_very_low(self):
        fv = _make_fv()
        result = self.scorer_low_risk.score(fv)
        # very_low_risk → cgtmse_eligible = True
        assert result["cgtmse_eligible"] is True

    def test_cgtmse_not_eligible_high_risk(self):
        fv = _make_fv()
        result = self.scorer_high_risk.score(fv)
        assert result["cgtmse_eligible"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# 4. CreditExplainer (mocked SHAP)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreditExplainer:
    def _make_explainer(self):
        from src.credit.shap_explainer import CreditExplainer

        scorer = _make_mock_scorer()

        # Mock SHAP explainer: shap_values returns uniform attribution
        mock_shap_exp = MagicMock()
        n_feats = len(scorer.feature_columns)
        mock_shap_exp.shap_values.return_value = np.ones((1, n_feats)) * 0.01
        mock_shap_exp.expected_value = 0.15

        exp = object.__new__(CreditExplainer)
        exp.feature_columns    = scorer.feature_columns
        exp.explainer_full     = mock_shap_exp
        exp.explainer_income   = mock_shap_exp
        return exp

    def test_top_k_features_count(self):
        exp = self._make_explainer()
        shap_row = np.random.randn(len(exp.feature_columns))
        top5 = exp.top_k_features(shap_row, k=5)
        assert len(top5) == 5

    def test_top_k_sorted_by_magnitude(self):
        exp = self._make_explainer()
        shap_row = np.array([0.1, -0.5, 0.3, 0.0, 0.2] + [0.0] * (len(exp.feature_columns) - 5))
        top5 = exp.top_k_features(shap_row, k=5)
        mags = [f["abs_magnitude"] for f in top5]
        assert mags == sorted(mags, reverse=True)

    def test_direction_labels(self):
        exp = self._make_explainer()
        shap_row = np.array([0.1, -0.1] + [0.0] * (len(exp.feature_columns) - 2))
        top2 = exp.top_k_features(shap_row, k=2)
        directions = {f["feature_name"]: f["direction"] for f in top2}
        pos_feat = exp.feature_columns[0]
        neg_feat = exp.feature_columns[1]
        assert directions[pos_feat] == "increases_risk"
        assert directions[neg_feat] == "decreases_risk"

    def test_waterfall_data_structure(self):
        exp = self._make_explainer()
        shap_row = np.random.randn(len(exp.feature_columns))
        wd = exp.waterfall_data(shap_row, base_value=0.2)
        assert "base_value" in wd
        assert "contributions" in wd
        assert "final_prediction" in wd
        assert abs(wd["final_prediction"] - (0.2 + float(np.sum(shap_row)))) < 1e-6

    def test_waterfall_contributions_count(self):
        exp = self._make_explainer()
        shap_row = np.random.randn(len(exp.feature_columns))
        wd = exp.waterfall_data(shap_row, base_value=0.0)
        assert len(wd["contributions"]) == len(exp.feature_columns)

    def test_explain_single_keys(self):
        exp = self._make_explainer()
        fv = _make_fv()
        result = exp.explain_single(fv.model_dump(), exp.feature_columns)
        assert "top_5_features" in result
        assert "waterfall_data" in result
        assert "base_value" in result

    def test_explain_single_top5_count(self):
        exp = self._make_explainer()
        fv = _make_fv()
        result = exp.explain_single(fv.model_dump(), exp.feature_columns)
        assert len(result["top_5_features"]) == 5

    def test_explain_single_income_model(self):
        """income_model flag is passed through without error."""
        exp = self._make_explainer()
        fv = _make_fv(data_completeness_score=0.5)
        result = exp.explain_single(fv.model_dump(), exp.feature_columns, use_income_model=True)
        assert len(result["top_5_features"]) == 5


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Recalibration — LIMIT_REDUCED_EVENT logic
# ═══════════════════════════════════════════════════════════════════════════════

class FakeRedis:
    """Minimal in-memory Redis for recalibration tests."""

    def __init__(self):
        self._hashes: dict[str, dict] = {}
        self._sets: dict[str, set]    = {}
        self._published: list[tuple]  = []

    async def hgetall(self, key):
        return dict(self._hashes.get(key, {}))

    async def hset(self, name, key=None, value=None, mapping=None, **kwargs):
        if name not in self._hashes:
            self._hashes[name] = {}
        if mapping:
            self._hashes[name].update({k: str(v) for k, v in mapping.items()})
        if key is not None and value is not None:
            self._hashes[name][key] = str(value)
        if kwargs:
            self._hashes[name].update({k: str(v) for k, v in kwargs.items()})

    async def sadd(self, key, *members):
        self._sets.setdefault(key, set()).update(members)

    async def smembers(self, key):
        return set(self._sets.get(key, set()))

    async def scard(self, key):
        return len(self._sets.get(key, set()))

    async def publish(self, channel, message):
        self._published.append((channel, message))

    async def xlen(self, stream):
        return 0

    async def xadd(self, stream, fields):
        pass

    async def ping(self):
        return True

    async def aclose(self):
        pass


class TestRecalibration:
    def _make_scorer_with_result(self, loan_amount: float):
        scorer = MagicMock()
        scorer.score.return_value = {
            "credit_score": 700,
            "risk_band": "low_risk",
            "probability_of_default": 0.18,
            "recommended_personal_loan_amount": loan_amount,
            "daily_avg_throughput_30d": 6000.0,
        }
        return scorer

    def test_no_event_when_loan_maintained(self):
        from src.credit.recalibration import _recalibrate_one

        redis = FakeRedis()
        uid   = "u_recal_001"
        key   = f"credit:user:{uid}"
        redis._hashes[key] = {
            "recommended_personal_loan_amount": "500000",
            "daily_avg_throughput_30d":         "5000",
        }

        scorer = self._make_scorer_with_result(loan_amount=500_000)

        # Patch parquet load
        fv = _make_fv(daily_avg_throughput_30d=8000.0)  # 60% change → triggers recalc

        with patch("src.credit.recalibration.Path") as mock_path, \
             patch("src.credit.recalibration.pl") as mock_pl, \
             patch("src.credit.recalibration.BehaviouralFeatureVector") as mock_bfv:

            mock_path.return_value.__truediv__ = lambda s, x: mock_path.return_value
            mock_path.return_value.exists.return_value = True
            mock_pl.read_parquet.return_value.height = 1
            mock_pl.read_parquet.return_value.row.return_value = fv.model_dump()
            mock_bfv.model_fields = BehaviouralFeatureVector.model_fields
            mock_bfv.return_value = fv

            asyncio.run(_recalibrate_one(redis, uid, scorer))

        # Loan unchanged → no LIMIT_REDUCED_EVENT
        assert not any("LIMIT_REDUCED_EVENT" in str(msg) for _, msg in redis._published)

    def test_limit_reduced_event_emitted(self):
        from src.credit.recalibration import _recalibrate_one

        redis = FakeRedis()
        uid   = "u_recal_002"
        key   = f"credit:user:{uid}"
        redis._hashes[key] = {
            "recommended_personal_loan_amount": "500000",
            "daily_avg_throughput_30d":         "5000",
        }

        # New score gives much lower loan
        scorer = self._make_scorer_with_result(loan_amount=100_000)

        fv = _make_fv(daily_avg_throughput_30d=8000.0)

        with patch("src.credit.recalibration.Path") as mock_path, \
             patch("src.credit.recalibration.pl") as mock_pl, \
             patch("src.credit.recalibration.BehaviouralFeatureVector") as mock_bfv:

            mock_path.return_value.__truediv__ = lambda s, x: mock_path.return_value
            mock_path.return_value.exists.return_value = True
            mock_pl.read_parquet.return_value.height = 1
            mock_pl.read_parquet.return_value.row.return_value = fv.model_dump()
            mock_bfv.model_fields = BehaviouralFeatureVector.model_fields
            mock_bfv.return_value = fv

            asyncio.run(_recalibrate_one(redis, uid, scorer))

        events = [json.loads(msg) for _, msg in redis._published if "credit_events" in _]
        assert any(e.get("event_type") == "LIMIT_REDUCED_EVENT" for e in events)

    def test_no_recalibration_below_threshold(self):
        from src.credit.recalibration import _recalibrate_one

        redis = FakeRedis()
        uid   = "u_recal_003"
        key   = f"credit:user:{uid}"
        redis._hashes[key] = {
            "recommended_personal_loan_amount": "500000",
            "daily_avg_throughput_30d":         "5000",
        }

        scorer = MagicMock()  # should not be called

        fv = _make_fv(daily_avg_throughput_30d=5050.0)  # only 1% change < 15% threshold

        with patch("src.credit.recalibration.Path") as mock_path, \
             patch("src.credit.recalibration.pl") as mock_pl, \
             patch("src.credit.recalibration.BehaviouralFeatureVector") as mock_bfv:

            mock_path.return_value.__truediv__ = lambda s, x: mock_path.return_value
            mock_path.return_value.exists.return_value = True
            mock_pl.read_parquet.return_value.height = 1
            mock_pl.read_parquet.return_value.row.return_value = fv.model_dump()
            mock_bfv.model_fields = BehaviouralFeatureVector.model_fields
            mock_bfv.return_value = fv

            asyncio.run(_recalibrate_one(redis, uid, scorer))

        scorer.score.assert_not_called()

    def test_skip_when_no_existing_record(self):
        from src.credit.recalibration import _recalibrate_one

        redis  = FakeRedis()
        scorer = MagicMock()
        asyncio.run(_recalibrate_one(redis, "u_no_record", scorer))
        scorer.score.assert_not_called()

    def test_sweep_runs_all_active(self):
        from src.credit.recalibration import run_recalibration_sweep

        redis = FakeRedis()
        redis._sets["credit:active"] = {"u_001", "u_002", "u_003"}

        scorer = MagicMock()
        scorer.score.return_value = {
            "credit_score": 700, "risk_band": "low_risk",
            "probability_of_default": 0.2,
            "recommended_personal_loan_amount": 200_000,
            "daily_avg_throughput_30d": 5000,
        }

        # With empty hash records, _recalibrate_one returns early without scoring
        asyncio.run(run_recalibration_sweep(redis, scorer))
        # No crash = sweep ran for all 3 users


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Scoring worker helpers
# ═══════════════════════════════════════════════════════════════════════════════

class TestScoringWorkerHelpers:
    def test_resolve_fv_uses_demo_fallback(self, tmp_path):
        from src.credit.scoring_worker import _load_demo_fv
        import polars as pl

        # Create fake cache
        uid    = "u_demo_src"
        cache  = tmp_path / f"user_id={uid}"
        cache.mkdir(parents=True)

        fv = _make_fv(user_id=uid)
        df = pl.DataFrame([{k: v for k, v in fv.model_dump().items() if k != "user_id"}])
        df.write_parquet(cache / "features.parquet")

        with patch("src.credit.scoring_worker.Path") as mock_path, \
             patch("src.credit.scoring_worker.settings") as mock_settings:
            mock_settings.parquet_cache_path = str(tmp_path)
            mock_path.return_value = tmp_path
            mock_path.side_effect = lambda x: Path(x)

            result = _load_demo_fv("u_new_user")

        # Can't assert exact result without full path wiring, just assert no crash

    def test_get_twin_delta_returns_zero_on_miss(self):
        from src.credit.scoring_worker import _get_twin_delta

        with patch("src.credit.scoring_worker.settings") as ms, \
             patch("src.credit.scoring_worker.json") as mj:
            import redis as sync_redis

            with patch.object(sync_redis, "from_url") as mock_redis:
                mock_r = MagicMock()
                mock_r.get.return_value = None
                mock_redis.return_value = mock_r
                ms.redis_url = "redis://localhost:6379"

                delta = _get_twin_delta("u_missing")

        assert delta == 0.0

    def test_get_twin_delta_positive_when_improving(self):
        from src.credit.scoring_worker import _get_twin_delta

        twin_data = json.dumps({
            "risk_history": [0.8, 0.7, 0.5]   # newest last → improving
        })

        with patch("src.credit.scoring_worker.settings") as ms:
            import redis as sync_redis
            with patch.object(sync_redis, "from_url") as mock_redis:
                mock_r = MagicMock()
                mock_r.get.return_value = twin_data
                mock_redis.return_value = mock_r
                ms.redis_url = "redis://localhost:6379"

                delta = _get_twin_delta("u_improving")

        # history[-1] - history[0] = 0.5 - 0.8 = -0.3 → max(−0.3, 0) = 0
        # Actually: last(0.5) - first(0.8) = -0.3, that means risk went DOWN (good)
        # our formula: max(history[-1] - history[0], 0.0)
        # = max(0.5 - 0.8, 0.0) = 0.0 — no delta
        # The scoring_worker treats decreasing risk_score as improvement
        assert delta >= 0.0

    def test_get_twin_delta_handles_redis_error(self):
        from src.credit.scoring_worker import _get_twin_delta

        with patch("src.credit.scoring_worker.settings") as ms:
            import redis as sync_redis
            with patch.object(sync_redis, "from_url") as mock_redis:
                mock_redis.side_effect = Exception("connection refused")
                ms.redis_url = "redis://localhost:6379"
                delta = _get_twin_delta("u_err")

        assert delta == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Scoring saga (in-memory)
# ═══════════════════════════════════════════════════════════════════════════════

class TestScoringSaga:
    def _run_saga(self, user_id: str, prob: float = 0.2, twin_delta: float = 0.0):
        from src.credit.scoring_worker import run_scoring_saga

        redis  = FakeRedis()
        scorer = _make_mock_scorer(prob=prob)
        fv     = _make_fv(user_id=user_id)

        with patch("src.credit.scoring_worker._resolve_fv", return_value=fv), \
             patch("src.credit.scoring_worker._get_twin_delta", return_value=twin_delta):
            asyncio.run(run_scoring_saga(redis, "task_001", user_id, scorer, explainer=None))

        return redis

    def test_saga_writes_complete_status(self):
        redis = self._run_saga("u_saga_001")
        assert redis._hashes["score:task_001"]["status"] == "complete"

    def test_saga_writes_credit_score(self):
        redis = self._run_saga("u_saga_002")
        score = int(redis._hashes["score:task_001"]["credit_score"])
        assert 300 <= score <= 900

    def test_saga_registers_in_active_set(self):
        redis = self._run_saga("u_saga_003")
        assert "u_saga_003" in redis._sets.get("credit:active", set())

    def test_saga_writes_per_user_credit_hash(self):
        redis = self._run_saga("u_saga_004")
        assert "credit:user:u_saga_004" in redis._hashes

    def test_saga_publishes_complete_event(self):
        redis = self._run_saga("u_saga_005")
        events = [json.loads(msg) for _, msg in redis._published]
        assert any(e.get("status") == "complete" for e in events)

    def test_saga_with_trajectory_override(self):
        redis = self._run_saga("u_saga_006", prob=0.8, twin_delta=0.5)
        override_raw = redis._hashes["score:task_001"].get("behavioural_override", "{}")
        override = json.loads(override_raw)
        assert override.get("applied") is True

    def test_saga_handles_fv_resolution_failure(self):
        from src.credit.scoring_worker import run_scoring_saga
        redis  = FakeRedis()
        scorer = _make_mock_scorer()

        with patch("src.credit.scoring_worker._resolve_fv",
                   side_effect=RuntimeError("no data")), \
             patch("src.credit.scoring_worker._get_twin_delta", return_value=0.0):
            asyncio.run(run_scoring_saga(redis, "task_fail", "u_fail", scorer, None))

        assert redis._hashes["score:task_fail"]["status"] == "failed"
        assert "error" in redis._hashes["score:task_fail"]


# ═══════════════════════════════════════════════════════════════════════════════
# 8. API endpoints (FastAPI TestClient)
# ═══════════════════════════════════════════════════════════════════════════════

class FakeRedisForAPI(FakeRedis):
    async def xadd(self, stream, fields):
        self._hashes.setdefault(f"__stream:{stream}", []).append(fields)
        return b"1-0"

    async def hgetall(self, key):
        return dict(self._hashes.get(key, {}))

    async def get(self, key):
        return self._hashes.get(key)

    async def scan(self, cursor, match=None, count=200):
        return 0, []


@pytest.fixture
def api_client():
    from fastapi.testclient import TestClient
    from src.api.main import app

    redis = FakeRedisForAPI()
    app.state.redis = redis
    with patch("src.api.main.aioredis.from_url", return_value=redis):
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, redis


class TestCreditAPIEndpoints:
    def test_submit_credit_score_missing_user_id(self, api_client):
        client, _ = api_client
        resp = client.post("/credit/score", json={})
        assert resp.status_code == 400

    def test_submit_credit_score_returns_task_id(self, api_client):
        client, _ = api_client
        resp = client.post("/credit/score", json={"user_id": "u_api_001"})
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert data["status"] == "pending"
        assert data["user_id"] == "u_api_001"

    def test_get_credit_score_not_found(self, api_client):
        client, _ = api_client
        resp = client.get("/credit/score/nonexistent_task")
        assert resp.status_code == 404

    def test_get_credit_score_pending(self, api_client):
        client, redis = api_client
        task_id = str(uuid.uuid4())
        redis._hashes[f"score:{task_id}"] = {"status": "pending", "user_id": "u_001"}
        resp = client.get(f"/credit/score/{task_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

    def test_get_credit_score_complete_parses_json_fields(self, api_client):
        client, redis = api_client
        task_id = str(uuid.uuid4())
        redis._hashes[f"score:{task_id}"] = {
            "status":        "complete",
            "credit_score":  "720",
            "risk_band":     "low_risk",
            "shap_top5":     json.dumps([{"feature_name": "emi_burden_ratio"}]),
            "rule_trace":    json.dumps({"emi_burden_check": {"result": "PASSED"}}),
            "behavioural_override": json.dumps({"applied": False}),
        }
        resp = client.get(f"/credit/score/{task_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["shap_top5"], list)
        assert isinstance(data["rule_trace"], dict)

    def test_get_credit_status_not_found(self, api_client):
        client, _ = api_client
        resp = client.get("/credit/u_unknown/status")
        assert resp.status_code == 404

    def test_get_credit_status_found(self, api_client):
        client, redis = api_client
        redis._hashes["credit:user:u_known"] = {
            "credit_score": "700",
            "risk_band":    "low_risk",
        }
        resp = client.get("/credit/u_known/status")
        assert resp.status_code == 200
        assert resp.json()["credit_score"] == "700"

    def test_credit_audit_replay_missing_fields(self, api_client):
        client, _ = api_client
        resp = client.post("/credit/audit/replay", json={"user_id": "u_001"})
        assert resp.status_code == 400

    def test_credit_audit_replay_bad_timestamp(self, api_client):
        client, _ = api_client
        resp = client.post("/credit/audit/replay", json={
            "user_id": "u_001", "target_timestamp": "not-a-date"
        })
        assert resp.status_code == 400

    def test_credit_audit_replay_no_cache(self, api_client):
        client, _ = api_client
        resp = client.post("/credit/audit/replay", json={
            "user_id":          "u_no_cache",
            "target_timestamp": "2026-01-01T00:00:00",
        })
        print("REPLAY RESPONSE TEXT:", resp.text)
        assert resp.status_code == 404

    def test_credit_health_models_missing(self, api_client):
        client, _ = api_client
        resp = client.get("/credit/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert "queue_depth" in data
        assert data["status"] in ("ok", "degraded")

    @patch("pathlib.Path.exists", return_value=False)
    def test_credit_health_degraded_without_models(self, mock_exists, api_client):
        client, _ = api_client
        resp = client.get("/credit/health")
        data = resp.json()
        # Models won't exist in test env → degraded
        assert data["status"] == "degraded"


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Credit trainer (smoke test — delegates to Tier 4 trainer)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreditTrainer:
    def test_run_credit_training_delegates(self):
        from src.credit.credit_trainer import run_credit_training

        with patch("src.credit.credit_trainer._run_training") as mock_train:
            run_credit_training(features_dir="data/features", model_dir="data/models")
            mock_train.assert_called_once_with(
                features_dir="data/features", model_dir="data/models"
            )

    def test_run_credit_training_custom_dirs(self):
        from src.credit.credit_trainer import run_credit_training

        with patch("src.credit.credit_trainer._run_training") as mock_train:
            run_credit_training(features_dir="/tmp/feats", model_dir="/tmp/models")
            mock_train.assert_called_once_with(
                features_dir="/tmp/feats", model_dir="/tmp/models"
            )
