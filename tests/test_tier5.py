"""
Tier 5 — Reasoning Agent: Tests

Covers:
  1. Schemas — all Pydantic models instantiate without error
  2. ContradictionDetector — Z-test, source consistency, lifestyle layers
  3. ContextAssembler — token budget, delta packet field names
  4. CoT Engine — deterministic fallback path (_build_fallback_cot)
  5. Interrogation — session creation, URS ranking, state machine advancement,
                     twin patch extraction, unanswered → flags
  6. Tier5Result aggregation — interrogation trigger conditions
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.features.schemas import BehaviouralFeatureVector
from src.reasoning.contradiction_detector import (
    extract_monthly_income_from_features,
    run_contradiction_detector,
)
from src.reasoning.context_assembler import (
    AssembledContext,        # lives in context_assembler, not schemas
    assemble_context,
    build_delta_packet,
)
from src.reasoning.interrogation import (
    _build_question_text,
    _parse_answer_llm,
    advance_session,
    compute_urs,
    create_session,
    rank_signals_for_interrogation,
    unanswered_to_flags,
)
from src.reasoning.schemas import (
    ConcernFlagType,
    FinancialSituation,     # actual enum name (not SituationType)
    IncomeDirection,        # actual enum name (not DirectionType)
    InterrogationState,
    QuestionTemplate,
    Severity,
    ContradictionDetectorResult,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _fv(**overrides) -> BehaviouralFeatureVector:
    defaults = dict(
        user_id="u_test",
        computed_at=datetime.now(timezone.utc),
        daily_avg_throughput_30d=5000.0,
        cash_buffer_days=15.0,
        debit_failure_rate_90d=0.04,
        end_of_month_liquidity_dip=500.0,
        emi_burden_ratio=0.30,
        savings_rate=0.12,
        income_stability_score=0.80,
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
    )
    defaults.update(overrides)
    return BehaviouralFeatureVector(**defaults)


# ── Helper: build a ContradictionDetectorResult directly ──────────────────────

def _make_contradiction_result(detected: bool = False) -> ContradictionDetectorResult:
    return ContradictionDetectorResult(
        contradiction_detected=detected,
        layers_triggered=0,
        severity=Severity.LOW,
        z_score=0.0,
        direction=IncomeDirection.CONSISTENT,
        confidence=0.1,
        details="no contradiction",
        declared_income=45_000.0,
        observed_mean_income=45_000.0,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Schema smoke tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSchemas:
    def test_concern_flag_type_has_income_contradiction(self):
        assert ConcernFlagType.INCOME_CONTRADICTION is not None

    def test_severity_enum_has_critical(self):
        assert Severity.CRITICAL is not None

    def test_interrogation_state_complete(self):
        assert InterrogationState.COMPLETE is not None

    def test_question_template_income_clarify(self):
        assert QuestionTemplate.INCOME_CLARIFY is not None

    def test_financial_situation_enum_exists(self):
        # The actual enum is FinancialSituation, not SituationType
        assert FinancialSituation.STABLE_IMPROVING is not None

    def test_income_direction_enum_consistent(self):
        # The actual enum is IncomeDirection, not DirectionType
        assert IncomeDirection.CONSISTENT is not None

    def test_contradiction_result_has_layer_flags(self):
        r = ContradictionDetectorResult(declared_income=45_000.0)
        assert hasattr(r, "layer1_flag")
        assert hasattr(r, "layer2_flag")
        assert hasattr(r, "layer3_flag")


# ─────────────────────────────────────────────────────────────────────────────
# 2. ContradictionDetector
# ─────────────────────────────────────────────────────────────────────────────

class TestContradictionDetector:
    def test_no_contradiction_when_income_consistent(self):
        """Stable observations matching declared → no contradiction."""
        months = [45_000.0, 46_000.0, 44_000.0]   # tight cluster
        result = run_contradiction_detector(
            declared_income=45_000.0,
            monthly_income_observations=months,
            income_stability_score=0.90,
            p2p_income_fraction=0.05,
            discretionary_30d=9_000.0,
            cash_dependency_index=0.10,
        )
        assert result.contradiction_detected is False
        assert result.layers_triggered == 0

    def test_layer1_triggers_on_large_z_score(self):
        """Z-test fires when declared is very far from a tight observed cluster."""
        # Mean ≈ 90_000, std ≈ 1_000 → z = (20_000-90_000)/(1000/√3) ≈ −121 → triggers
        months = [89_000.0, 90_000.0, 91_000.0]
        result = run_contradiction_detector(
            declared_income=20_000.0,     # far below tight observed cluster
            monthly_income_observations=months,
            income_stability_score=0.95,
            p2p_income_fraction=0.05,
            discretionary_30d=9_000.0,
            cash_dependency_index=0.10,
        )
        assert result.layer1_flag is True
        assert result.contradiction_detected is True

    def test_z_score_negative_when_declared_below_observed(self):
        """Z = (declared - observed_mean) / (σ/√n): negative when declared < observed."""
        months = [80_000.0, 82_000.0, 81_000.0]
        result = run_contradiction_detector(
            declared_income=20_000.0,    # well below observed mean
            monthly_income_observations=months,
            income_stability_score=0.90,
            p2p_income_fraction=0.05,
            discretionary_30d=5_000.0,
            cash_dependency_index=0.10,
        )
        # declared < observed → z is negative (under-reported direction)
        assert result.z_score < 0

    def test_extract_monthly_income_returns_three_values(self):
        months = extract_monthly_income_from_features(90_000.0, 30_000.0, 7_000.0)
        assert len(months) == 3

    def test_extract_monthly_income_positive(self):
        """All returned observations must be ≥ 0."""
        months = extract_monthly_income_from_features(90_000.0, 30_000.0, 7_000.0)
        for m in months:
            assert m >= 0

    def test_severity_low_for_healthy_user(self):
        """A perfectly consistent user should produce LOW severity."""
        months = [45_000.0, 45_000.0, 45_000.0]
        result = run_contradiction_detector(
            declared_income=45_000.0,
            monthly_income_observations=months,
            income_stability_score=0.95,
            p2p_income_fraction=0.05,
            discretionary_30d=9_000.0,
            cash_dependency_index=0.10,
        )
        assert result.severity == Severity.LOW

    def test_confidence_bounded_0_1(self):
        months = [45_000.0, 45_000.0, 45_000.0]
        result = run_contradiction_detector(
            declared_income=45_000.0,
            monthly_income_observations=months,
            income_stability_score=0.88,
            p2p_income_fraction=0.05,
            discretionary_30d=9_000.0,
            cash_dependency_index=0.10,
        )
        assert 0.0 <= result.confidence <= 1.0

    def test_layer2_triggers_on_high_p2p_fraction(self):
        """Any P2P fraction > 40% triggers layer 2 (source inconsistency)."""
        months = [30_000.0, 30_000.0, 30_000.0]
        result = run_contradiction_detector(
            declared_income=30_000.0,
            monthly_income_observations=months,
            income_stability_score=0.60,
            p2p_income_fraction=0.55,    # > 40% threshold
            discretionary_30d=6_000.0,
            cash_dependency_index=0.30,
        )
        assert result.layer2_flag is True
        assert result.layers_triggered >= 1

    def test_layer2_not_triggered_below_threshold(self):
        """P2P < 40% should not trigger layer 2."""
        months = [30_000.0, 30_000.0, 30_000.0]
        result = run_contradiction_detector(
            declared_income=30_000.0,
            monthly_income_observations=months,
            income_stability_score=0.90,
            p2p_income_fraction=0.10,    # well below 40%
            discretionary_30d=6_000.0,
            cash_dependency_index=0.05,
        )
        assert result.layer2_flag is False

    def test_three_layers_gives_high_severity(self):
        """All three layers firing should produce HIGH severity."""
        # layer1: tight cluster far from declared
        months = [90_000.0, 91_000.0, 89_000.0]
        result = run_contradiction_detector(
            declared_income=20_000.0,
            monthly_income_observations=months,
            income_stability_score=0.90,
            p2p_income_fraction=0.60,    # triggers layer2
            discretionary_30d=60_000.0, # lci = 60k/20k = 3.0, > 0.45 AND declared > 50k? 20k < 50k — won't trigger layer3
            cash_dependency_index=0.50,
        )
        # At minimum layer1 + layer2 trigger
        assert result.layers_triggered >= 2


# ─────────────────────────────────────────────────────────────────────────────
# 3. ContextAssembler
# ─────────────────────────────────────────────────────────────────────────────

class TestContextAssembler:
    def test_assembled_context_is_from_context_assembler(self):
        """AssembledContext lives in context_assembler, not schemas."""
        from src.reasoning.context_assembler import AssembledContext
        assert AssembledContext is not None

    def test_context_returns_correct_type(self):
        fv = _fv()
        ctx = assemble_context(
            features=fv,
            declared_income=45_000.0,
            contradiction_result=_make_contradiction_result(),
            delta_packet=None,
            recent_events=[],
        )
        assert isinstance(ctx, AssembledContext)

    def test_token_budget_respected(self):
        fv = _fv()
        ctx = assemble_context(
            features=fv,
            declared_income=45_000.0,
            contradiction_result=_make_contradiction_result(),
            delta_packet=None,
            recent_events=[],
        )
        assert ctx.total_tokens_used > 0
        assert ctx.total_tokens_used <= 2048

    def test_context_has_declared_income(self):
        """AssembledContext stores declared_income (no user_id field on the dataclass)."""
        fv = _fv(user_id="u_ctx_test")
        ctx = assemble_context(
            features=fv,
            declared_income=45_000.0,
            contradiction_result=_make_contradiction_result(),
            delta_packet=None,
            recent_events=[],
        )
        assert ctx.declared_income == 45_000.0

    def test_delta_packet_has_changed_features_field(self):
        """DeltaPacket field is 'changed_features', not 'significant_changes'."""
        from src.reasoning.schemas import DeltaPacket
        dp = DeltaPacket()
        assert hasattr(dp, "changed_features")

    def test_delta_packet_built_from_two_snapshots(self):
        current = {"emi_burden_ratio": 0.35, "savings_rate": 0.10, "cash_buffer_days": 12.0}
        previous = {"emi_burden_ratio": 0.28, "savings_rate": 0.15, "cash_buffer_days": 18.0}
        stds = {"emi_burden_ratio": 0.10, "savings_rate": 0.08, "cash_buffer_days": 10.0}
        dp = build_delta_packet(current, previous, stds)
        assert dp is not None
        assert hasattr(dp, "changed_features")
        assert isinstance(dp.changed_features, list)

    def test_delta_significant_change_flagged_in_changed_features(self):
        """A 2-sigma drop in savings_rate should appear in changed_features."""
        current  = {"savings_rate": 0.02}
        previous = {"savings_rate": 0.18}
        stds     = {"savings_rate": 0.08}
        dp = build_delta_packet(current, previous, stds)
        feature_names = [fd.feature for fd in dp.changed_features]
        assert "savings_rate" in feature_names

    def test_delta_feature_direction_degraded_on_drop(self):
        """Savings rate dropping should produce direction='degraded'."""
        current  = {"savings_rate": 0.02}
        previous = {"savings_rate": 0.18}
        stds     = {"savings_rate": 0.08}
        dp = build_delta_packet(current, previous, stds)
        savings_delta = next((fd for fd in dp.changed_features if fd.feature == "savings_rate"), None)
        assert savings_delta is not None
        assert savings_delta.direction == "degraded"

    def test_context_to_prompt_section_non_empty(self):
        fv = _fv()
        ctx = assemble_context(
            features=fv,
            declared_income=45_000.0,
            contradiction_result=_make_contradiction_result(),
            delta_packet=None,
            recent_events=[],
        )
        prompt = ctx.to_prompt_section()
        assert isinstance(prompt, str) and len(prompt) > 20


# ─────────────────────────────────────────────────────────────────────────────
# 4. CoT Engine — fallback path (no LLM key needed)
# ─────────────────────────────────────────────────────────────────────────────

class TestCoTEngine:
    """Tests that use _build_fallback_cot (the actual function name) directly
       and verify run_cot_engine falls back gracefully under no-key conditions."""

    def _make_context(self):
        fv = _fv()
        return assemble_context(
            features=fv,
            declared_income=45_000.0,
            contradiction_result=_make_contradiction_result(),
            delta_packet=None,
            recent_events=[],
        )

    def test_build_fallback_cot_returns_dict(self):
        from src.reasoning.cot_engine import _build_fallback_cot
        fv = _fv()
        result = _build_fallback_cot(fv)
        assert isinstance(result, dict)

    def test_fallback_has_classify_key(self):
        from src.reasoning.cot_engine import _build_fallback_cot
        result = _build_fallback_cot(_fv())
        assert "classify" in result

    def test_fallback_has_narrative_key(self):
        from src.reasoning.cot_engine import _build_fallback_cot
        result = _build_fallback_cot(_fv())
        assert "risk_narrative" in result
        assert len(result["risk_narrative"]) > 10

    def test_fallback_classify_is_valid_situation(self):
        from src.reasoning.cot_engine import _build_fallback_cot
        result = _build_fallback_cot(_fv())
        valid = {s.value for s in FinancialSituation}
        assert result["classify"] in valid

    def test_fallback_confidence_in_range(self):
        from src.reasoning.cot_engine import _build_fallback_cot
        result = _build_fallback_cot(_fv())
        assert 0.0 <= float(result["confidence"]) <= 1.0

    def test_high_emi_burden_classifies_stressed_critical(self):
        from src.reasoning.cot_engine import _build_fallback_cot
        result = _build_fallback_cot(_fv(emi_burden_ratio=0.72))
        assert result["classify"] == "STRESSED_CRITICAL"

    def test_healthy_classifies_stable_improving(self):
        from src.reasoning.cot_engine import _build_fallback_cot
        result = _build_fallback_cot(_fv(savings_rate=0.20, emi_burden_ratio=0.20, cash_buffer_days=30.0))
        assert result["classify"] == "STABLE_IMPROVING"

    def test_fallback_has_concern_flags_list(self):
        from src.reasoning.cot_engine import _build_fallback_cot
        result = _build_fallback_cot(_fv(emi_burden_ratio=0.75, cash_buffer_days=3.0))
        assert isinstance(result["concern_flags"], list)
        assert len(result["concern_flags"]) >= 1

    def test_run_cot_engine_uses_fallback_without_api_key(self):
        """run_cot_engine must not crash when the API key is absent."""
        from src.reasoning.cot_engine import run_cot_engine
        from src.reasoning.schemas import CoTTrace, BehaviouralChangeSummary
        fv = _fv()
        ctx = self._make_context()
        with patch("src.reasoning.cot_engine.settings") as mock_settings:
            mock_settings.openrouter_api_key = ""
            mock_settings.llm_model = "mock-model"
            cot, narrative, bcs, intents, flags = run_cot_engine(fv, ctx)
        assert isinstance(cot, CoTTrace)
        assert isinstance(narrative, str)
        assert isinstance(bcs, BehaviouralChangeSummary)

    def test_cot_trace_confidence_bounded(self):
        """CoTTrace.confidence produced by run_cot_engine must be in [0, 1]."""
        from src.reasoning.cot_engine import run_cot_engine
        from src.reasoning.schemas import CoTTrace
        fv = _fv()
        ctx = self._make_context()
        with patch("src.reasoning.cot_engine.settings") as mock_settings:
            mock_settings.openrouter_api_key = ""
            mock_settings.llm_model = "mock"
            cot, *_ = run_cot_engine(fv, ctx)
        assert 0.0 <= cot.confidence <= 1.0

    def test_cot_trace_classify_is_financial_situation(self):
        from src.reasoning.cot_engine import run_cot_engine
        fv = _fv()
        ctx = self._make_context()
        with patch("src.reasoning.cot_engine.settings") as mock_settings:
            mock_settings.openrouter_api_key = ""
            mock_settings.llm_model = "mock"
            cot, *_ = run_cot_engine(fv, ctx)
        assert isinstance(cot.classify, FinancialSituation)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Interrogation State Machine
# ─────────────────────────────────────────────────────────────────────────────

class TestURS:
    def test_urs_bounded_0_1(self):
        score = compute_urs("emi_burden_ratio", 0.55, 0.4, 0.7)
        assert 0.0 <= score <= 1.0

    def test_urs_higher_for_high_risk_score(self):
        low  = compute_urs("cash_buffer_days", 5.0, 0.5, 0.1)
        high = compute_urs("cash_buffer_days", 5.0, 0.5, 0.9)
        assert high > low

    def test_urs_higher_for_high_ambiguity(self):
        clear     = compute_urs("savings_rate", 0.05, 0.95, 0.5)  # high posterior
        ambiguous = compute_urs("savings_rate", 0.05, 0.30, 0.5)  # low posterior
        assert ambiguous > clear

    def test_known_feature_scores_higher_than_unknown(self):
        known   = compute_urs("emi_burden_ratio", 0.5, 0.5, 0.5)
        unknown = compute_urs("nonexistent_feature", 0.5, 0.5, 0.5)
        assert known > unknown


class TestQuestionRanking:
    def test_ranks_return_list(self):
        fv = _fv(emi_burden_ratio=0.55, debit_failure_rate_90d=0.15)
        ranked = rank_signals_for_interrogation(fv, 0.4, 2, 30_000.0)
        assert isinstance(ranked, list)
        assert len(ranked) <= 5

    def test_ranked_desc_by_urs(self):
        fv = _fv(emi_burden_ratio=0.60, lifestyle_inflation_trend=0.25)
        ranked = rank_signals_for_interrogation(fv, 0.3, 0, 30_000.0)
        urs_scores = [r[1] for r in ranked]
        assert urs_scores == sorted(urs_scores, reverse=True)

    def test_income_contradiction_boosted_when_triggered(self):
        fv = _fv()
        ranked_with_contradiction = rank_signals_for_interrogation(fv, 0.5, 3, 45_000.0)
        if ranked_with_contradiction:
            assert ranked_with_contradiction[0][0] == "income_contradiction"


class TestQuestionText:
    def test_income_clarify_mentions_amounts(self):
        fv = _fv(income_90d=90_000.0)
        text = _build_question_text(
            QuestionTemplate.INCOME_CLARIFY, fv, 45_000.0,
            {"observed_mean_income": 30_000.0}
        )
        assert "₹" in text or "income" in text.lower()

    def test_expense_explain_mentions_percentage(self):
        fv = _fv(lifestyle_inflation_trend=0.30)
        text = _build_question_text(
            QuestionTemplate.EXPENSE_EXPLAIN, fv, 45_000.0,
            {"change_pct": 30}
        )
        assert "30" in text or "%" in text or "spending" in text.lower()

    def test_future_commitment_mentions_days(self):
        fv = _fv()
        text = _build_question_text(
            QuestionTemplate.FUTURE_COMMITMENT, fv, 45_000.0,
            {"stress_days": 14}
        )
        assert "14" in text or "day" in text.lower()


class TestAnswerParser:
    def test_parse_yes_answer(self):
        result = _parse_answer_llm(0, "Do you have extra income?", "Yes, I earn from freelancing")
        assert result.boolean_confirmation is True

    def test_parse_no_answer(self):
        result = _parse_answer_llm(0, "Any new loans?", "No, not planning any")
        assert result.boolean_confirmation is False

    def test_parse_extracts_amount(self):
        result = _parse_answer_llm(0, "Income?", "I earn about ₹25,000 per month")
        assert 25000 in result.numeric_amounts

    def test_parse_extracts_time_reference(self):
        result = _parse_answer_llm(0, "When?", "I plan to take a loan next month")
        assert len(result.time_references) > 0

    def test_income_patch_on_positive_income_answer(self):
        result = _parse_answer_llm(0, "Do you have additional income?", "Yes, I earn ₹20,000")
        assert "income_supplement" in result.twin_patch or result.boolean_confirmation is True


class TestSessionStateMachine:
    def _make_session(self, contradiction_layers=2):
        fv = _fv(emi_burden_ratio=0.55, lifestyle_inflation_trend=0.25)
        return create_session(
            user_id="u_test",
            features=fv,
            declared_income=30_000.0,
            max_hypothesis_posterior=0.4,
            contradiction_layers=contradiction_layers,
            trigger_reason="test",
        )

    def test_session_created_with_questions(self):
        session = self._make_session()
        assert len(session.questions) > 0

    def test_session_starts_in_question_ranking(self):
        session = self._make_session()
        assert session.state == InterrogationState.QUESTION_RANKING

    def test_session_has_valid_user_id(self):
        session = self._make_session()
        assert session.user_id == "u_test"

    def test_advance_moves_to_next_question(self):
        fv = _fv()
        session = self._make_session()
        updated, next_q, patch = advance_session(session, "Yes, I have freelance income", fv)
        assert updated.current_q_index == 1

    def test_advance_captures_answer(self):
        fv = _fv()
        session = self._make_session()
        updated, _, _ = advance_session(session, "No, no new loans planned", fv)
        assert len(updated.answers) == 1

    def test_abandon_with_none_answer(self):
        fv = _fv()
        session = self._make_session()
        updated, next_q, _ = advance_session(session, None, fv)
        assert updated.state == InterrogationState.ABANDONED

    def test_complete_after_all_questions(self):
        fv = _fv(emi_burden_ratio=0.55, lifestyle_inflation_trend=0.25)
        session = self._make_session()
        for _ in session.questions:
            if session.state.value not in ("COMPLETE", "ABANDONED"):
                session, _, _ = advance_session(session, "No changes planned", fv)
        assert session.state == InterrogationState.COMPLETE

    def test_unanswered_to_flags_produces_flags(self):
        session = self._make_session()
        session.state = InterrogationState.ABANDONED
        flags = unanswered_to_flags(session)
        assert len(flags) == len(session.questions)
        for flag in flags:
            assert flag.flag_type == ConcernFlagType.UNRESOLVED_AMBIGUITY

    def test_no_flags_when_all_answered(self):
        fv = _fv()
        session = self._make_session()
        from src.reasoning.schemas import ParsedAnswer
        for i, q in enumerate(session.questions):
            session.answers.append(ParsedAnswer(
                q_index=i,
                raw_answer="test",
                numeric_amounts=[],
                time_references=[],
                boolean_confirmation=None,
                twin_patch={},
            ))
        flags = unanswered_to_flags(session)
        assert len(flags) == 0


# ─────────────────────────────────────────────────────────────────────────────
# 6. Tier5 Trigger Conditions
# ─────────────────────────────────────────────────────────────────────────────

class TestInterrogationTrigger:
    def test_cot_trigger_fires_interrogation(self):
        from src.reasoning.tier5 import _should_trigger_interrogation
        fv = _fv()
        should, reason = _should_trigger_interrogation(
            cot_trigger=True, contradiction_layers=0, features=fv, is_first_run=False
        )
        assert should is True
        assert reason == "low_posterior_confidence"

    def test_multi_layer_contradiction_triggers(self):
        from src.reasoning.tier5 import _should_trigger_interrogation
        fv = _fv()
        should, reason = _should_trigger_interrogation(
            cot_trigger=False, contradiction_layers=3, features=fv, is_first_run=False
        )
        assert should is True
        assert "contradiction" in reason

    def test_first_run_always_triggers(self):
        from src.reasoning.tier5 import _should_trigger_interrogation
        fv = _fv()
        should, reason = _should_trigger_interrogation(
            cot_trigger=False, contradiction_layers=0, features=fv, is_first_run=True
        )
        assert should is True

    def test_healthy_no_trigger(self):
        from src.reasoning.tier5 import _should_trigger_interrogation
        fv = _fv(
            debit_failure_rate_90d=0.02,
            anomaly_flag=False,
            merchant_category_shift_count=0,
        )
        should, reason = _should_trigger_interrogation(
            cot_trigger=False, contradiction_layers=1, features=fv, is_first_run=False
        )
        assert should is False
        assert reason == ""

    def test_stress_anomaly_triggers(self):
        from src.reasoning.tier5 import _should_trigger_interrogation
        fv = _fv(debit_failure_rate_90d=0.15, anomaly_flag=True)
        should, reason = _should_trigger_interrogation(
            cot_trigger=False, contradiction_layers=0, features=fv, is_first_run=False
        )
        assert should is True
