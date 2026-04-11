"""
Tests for Tier 4 — Digital Twin Layer

Covers:
  - DigitalTwin model: construction, field validation, derived helpers
  - build_financial_dna: dimensionality, bounds, determinism, sensitivity
  - TwinStore: save / get / history / reconstruct_at (fake Redis)
  - TwinService: update_from_features lifecycle, persona inference, risk score
  - twin_embedding: cosine similarity, DNACohortIndex nearest-neighbour
  - AvatarState: expression selection per liquidity + persona
  - CIBIL-like score mapping
  - Integration: feature vector → twin update → version increment
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.twin.twin_model import (
    AvatarState,
    DigitalTwin,
    DNA_DIM,
    build_financial_dna,
)
from src.twin.twin_embedding import DNACohortIndex, cosine_similarity, euclidean_distance
from src.features.schemas import BehaviouralFeatureVector


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_twin(
    user_id: str = "u_test",
    risk_score: float = 0.3,
    liquidity_health: str = "HIGH",
    emi_burden_ratio: float = 0.25,
    cash_buffer_days: float = 20.0,
    spending_volatility: float = 0.3,
    income_stability: float = 0.8,
    persona: str = "genuine_healthy",
) -> DigitalTwin:
    return DigitalTwin(
        user_id=user_id,
        risk_score=risk_score,
        liquidity_health=liquidity_health,
        emi_burden_ratio=emi_burden_ratio,
        cash_buffer_days=cash_buffer_days,
        spending_volatility=spending_volatility,
        income_stability=income_stability,
        persona=persona,
    )


def _make_feature_vector(**overrides) -> BehaviouralFeatureVector:
    """Minimal valid BehaviouralFeatureVector with sensible defaults."""
    base = dict(
        user_id="u_test",
        computed_at=datetime(2026, 4, 11, 12, 0, 0),
        daily_avg_throughput_30d=5000.0,
        cash_buffer_days=20.0,
        debit_failure_rate_90d=0.05,
        end_of_month_liquidity_dip=1000.0,
        emi_burden_ratio=0.25,
        savings_rate=0.15,
        income_stability_score=0.8,
        spending_volatility_index=0.3,
        discretionary_ratio=0.25,
        cash_dependency_index=0.1,
        subscription_count_30d=3,
        emi_payment_count_90d=2,
        salary_day_spike_flag=False,
        lifestyle_inflation_trend=0.02,
        merchant_category_shift_count=1,
        anomaly_flag=False,
        top3_merchant_concentration=0.4,
        peer_cohort_benchmark_deviation=0.1,
        income_7d=15000.0,
        income_30d=60000.0,
        income_90d=180000.0,
        essential_7d=5000.0,
        essential_30d=20000.0,
        essential_90d=60000.0,
        discretionary_7d=2000.0,
        discretionary_30d=8000.0,
        discretionary_90d=25000.0,
        net_cashflow_7d=8000.0,
        net_cashflow_30d=32000.0,
        net_cashflow_90d=95000.0,
    )
    base.update(overrides)
    return BehaviouralFeatureVector(**base)


# ─────────────────────────────────────────────────────────────────────────────
# DigitalTwin model
# ─────────────────────────────────────────────────────────────────────────────

class TestDigitalTwinModel:

    def test_default_construction(self):
        twin = DigitalTwin(user_id="u_0001")
        assert twin.user_id == "u_0001"
        assert twin.version == 0
        assert twin.persona == "unknown"
        assert twin.risk_score == 0.5
        assert twin.liquidity_health == "HIGH"
        assert len(twin.financial_dna) == DNA_DIM

    def test_risk_score_bounds(self):
        twin = DigitalTwin(user_id="u_1", risk_score=0.0)
        assert twin.risk_score == 0.0
        twin2 = DigitalTwin(user_id="u_2", risk_score=1.0)
        assert twin2.risk_score == 1.0

    def test_invalid_risk_score_raises(self):
        with pytest.raises(Exception):
            DigitalTwin(user_id="u_bad", risk_score=1.5)

    def test_liquidity_health_valid_values(self):
        for lh in ("LOW", "MEDIUM", "HIGH"):
            twin = DigitalTwin(user_id="u_1", liquidity_health=lh)
            assert twin.liquidity_health == lh

    def test_risk_history_capped_at_20(self):
        twin = DigitalTwin(user_id="u_1", risk_history=[0.5] * 30)
        assert len(twin.risk_history) == 20

    def test_feature_history_summary_capped_at_10(self):
        summaries = [{"version": i, "ts": "2026-01-01"} for i in range(15)]
        twin = DigitalTwin(user_id="u_1", feature_history_summary=summaries)
        assert len(twin.feature_history_summary) == 10

    def test_json_round_trip(self):
        twin = _make_twin()
        payload = twin.model_dump_json()
        restored = DigitalTwin.model_validate_json(payload)
        assert restored.user_id == twin.user_id
        assert restored.risk_score == twin.risk_score
        assert restored.version == twin.version

    def test_snapshot_summary_keys(self):
        twin = _make_twin(risk_score=0.42)
        snap = twin.snapshot_summary()
        assert "version" in snap
        assert "ts" in snap
        assert "risk_score" in snap
        assert "liquidity_health" in snap
        assert snap["risk_score"] == round(0.42, 4)


class TestCIBILScore:

    def test_excellent_range(self):
        twin = DigitalTwin(user_id="u_1", risk_score=0.0)
        assert twin.cibil_like_score() == 900

    def test_poor_range(self):
        twin = DigitalTwin(user_id="u_1", risk_score=1.0)
        assert twin.cibil_like_score() == 300

    def test_midpoint(self):
        twin = DigitalTwin(user_id="u_1", risk_score=0.5)
        assert twin.cibil_like_score() == 600

    def test_score_monotonically_decreasing(self):
        scores = [DigitalTwin(user_id="u", risk_score=r / 10.0).cibil_like_score()
                  for r in range(11)]
        assert scores == sorted(scores, reverse=True)

    def test_score_within_300_900(self):
        for r in [0.0, 0.25, 0.5, 0.75, 1.0]:
            s = DigitalTwin(user_id="u", risk_score=r).cibil_like_score()
            assert 300 <= s <= 900


class TestAvatarState:

    def test_low_liquidity_gives_urgent(self):
        twin = _make_twin(liquidity_health="LOW", persona="genuine_healthy")
        twin.derive_avatar()
        assert twin.avatar_state.expression == "urgent"
        assert twin.avatar_state.liquidity_label == "LOW"

    def test_medium_liquidity_gives_concerned(self):
        twin = _make_twin(liquidity_health="MEDIUM", persona="genuine_healthy")
        twin.derive_avatar()
        assert twin.avatar_state.expression == "concerned"

    def test_high_liquidity_gives_calm(self):
        twin = _make_twin(liquidity_health="HIGH", persona="genuine_healthy")
        twin.derive_avatar()
        assert twin.avatar_state.expression == "calm"

    def test_new_to_credit_overrides_to_educational(self):
        twin = _make_twin(liquidity_health="HIGH", persona="new_to_credit")
        twin.derive_avatar()
        assert twin.avatar_state.expression == "educational"

    def test_shell_circular_overrides_to_concerned(self):
        twin = _make_twin(liquidity_health="HIGH", persona="shell_circular")
        twin.derive_avatar()
        assert twin.avatar_state.expression == "concerned"

    def test_persona_mood_message_set(self):
        for persona in ("genuine_healthy", "genuine_struggling", "new_to_credit",
                        "shell_circular", "paper_trader", "unknown"):
            twin = _make_twin(persona=persona)
            twin.derive_avatar()
            assert len(twin.avatar_state.mood_message) > 5


# ─────────────────────────────────────────────────────────────────────────────
# Financial DNA
# ─────────────────────────────────────────────────────────────────────────────

class TestFinancialDNA:

    def test_output_dimension(self):
        dna = build_financial_dna({})
        assert len(dna) == DNA_DIM

    def test_all_values_in_0_1(self):
        features = {
            "emi_burden_ratio": 0.3,
            "savings_rate": 0.2,
            "cash_buffer_days": 25.0,
            "income_30d": 60000.0,
        }
        dna = build_financial_dna(features)
        for val in dna:
            assert 0.0 <= val <= 1.0, f"DNA value {val} out of [0,1]"

    def test_deterministic(self):
        features = {"emi_burden_ratio": 0.4, "cash_buffer_days": 10.0}
        dna1 = build_financial_dna(features)
        dna2 = build_financial_dna(features)
        assert dna1 == dna2

    def test_zero_features_valid(self):
        dna = build_financial_dna({})
        assert len(dna) == DNA_DIM
        assert all(isinstance(v, float) for v in dna)

    def test_high_risk_vs_low_risk_differ(self):
        high_risk = build_financial_dna({
            "emi_burden_ratio": 1.5,
            "debit_failure_rate_90d": 0.8,
            "cash_buffer_days": 1.0,
            "savings_rate": -0.5,
        })
        low_risk = build_financial_dna({
            "emi_burden_ratio": 0.1,
            "debit_failure_rate_90d": 0.01,
            "cash_buffer_days": 60.0,
            "savings_rate": 0.4,
        })
        # Vectors should be meaningfully different
        dist = sum((a - b) ** 2 for a, b in zip(high_risk, low_risk)) ** 0.5
        assert dist > 0.1, "High-risk and low-risk DNA should differ"

    def test_extreme_values_clamped(self):
        dna = build_financial_dna({
            "emi_burden_ratio": 999.0,
            "cash_buffer_days": -999.0,
        })
        for val in dna:
            assert 0.0 <= val <= 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Twin Embedding utilities
# ─────────────────────────────────────────────────────────────────────────────

class TestTwinEmbedding:

    def test_cosine_identical_vectors(self):
        v = [0.5] * DNA_DIM
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-5

    def test_cosine_opposite_vectors(self):
        a = [1.0] * DNA_DIM
        b = [-1.0] * DNA_DIM
        assert abs(cosine_similarity(a, b) - (-1.0)) < 1e-5

    def test_cosine_orthogonal(self):
        a = [1.0 if i % 2 == 0 else 0.0 for i in range(DNA_DIM)]
        b = [0.0 if i % 2 == 0 else 1.0 for i in range(DNA_DIM)]
        assert abs(cosine_similarity(a, b)) < 1e-5

    def test_cosine_mismatched_dims_raises(self):
        with pytest.raises(ValueError):
            cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])

    def test_cosine_zero_vector(self):
        zero = [0.0] * DNA_DIM
        other = [0.5] * DNA_DIM
        assert cosine_similarity(zero, other) == 0.0

    def test_euclidean_zero(self):
        v = [0.3] * DNA_DIM
        assert euclidean_distance(v, v) == pytest.approx(0.0, abs=1e-9)

    def test_cohort_index_nearest(self):
        idx = DNACohortIndex()
        idx.add("u_0", [1.0] * DNA_DIM)
        idx.add("u_1", [0.0] * DNA_DIM)
        idx.add("u_2", [0.9] + [1.0] * (DNA_DIM - 1))
        query = [1.0] * DNA_DIM
        results = idx.nearest(query, k=2)
        assert results[0][0] in ("u_0", "u_2")
        assert results[0][1] > results[1][1]  # similarity descending

    def test_cohort_index_excludes_self(self):
        idx = DNACohortIndex()
        idx.add("u_self", [1.0] * DNA_DIM)
        idx.add("u_other", [0.9] * DNA_DIM)
        results = idx.nearest([1.0] * DNA_DIM, k=5, exclude="u_self")
        ids = [r[0] for r in results]
        assert "u_self" not in ids

    def test_cohort_index_len(self):
        idx = DNACohortIndex()
        for i in range(10):
            idx.add(f"u_{i}", [float(i)] * DNA_DIM)
        assert len(idx) == 10


# ─────────────────────────────────────────────────────────────────────────────
# TwinStore (fake Redis)
# ─────────────────────────────────────────────────────────────────────────────

class FakeRedis:
    """Minimal in-memory fake for Redis operations used by TwinStore."""

    def __init__(self):
        self._kv: dict[str, str] = {}
        self._lists: dict[str, list[str]] = {}

    def pipeline(self):
        return FakePipeline(self)

    async def get(self, key: str):
        return self._kv.get(key)

    async def set(self, key: str, value: str):
        self._kv[key] = value

    async def lpush(self, key: str, value: str):
        self._lists.setdefault(key, []).insert(0, value)

    async def ltrim(self, key: str, start: int, stop: int):
        lst = self._lists.get(key, [])
        if stop == -1:
            self._lists[key] = lst[start:]
        else:
            self._lists[key] = lst[start : stop + 1]

    async def lrange(self, key: str, start: int, stop: int):
        lst = self._lists.get(key, [])
        if stop == -1:
            return lst[start:]
        return lst[start : stop + 1]

    async def delete(self, *keys):
        for key in keys:
            self._kv.pop(key, None)
            self._lists.pop(key, None)

    async def publish(self, channel: str, message: str):
        pass  # no-op


class FakePipeline:
    def __init__(self, redis: FakeRedis):
        self._redis = redis
        self._ops: list = []

    def set(self, key, value):
        self._ops.append(("set", key, value))
        return self

    def lpush(self, key, value):
        self._ops.append(("lpush", key, value))
        return self

    def ltrim(self, key, start, stop):
        self._ops.append(("ltrim", key, start, stop))
        return self

    def delete(self, *keys):
        self._ops.append(("delete", keys))
        return self

    async def execute(self):
        for op in self._ops:
            if op[0] == "set":
                await self._redis.set(op[1], op[2])
            elif op[0] == "lpush":
                await self._redis.lpush(op[1], op[2])
            elif op[0] == "ltrim":
                await self._redis.ltrim(op[1], op[2], op[3])
            elif op[0] == "delete":
                await self._redis.delete(*op[1])
        self._ops.clear()


class TestTwinStore:

    def _store(self):
        from src.twin.twin_store import TwinStore
        return TwinStore(FakeRedis())

    def test_get_nonexistent_returns_none(self):
        store = self._store()
        result = asyncio.run(store.get("u_missing"))
        assert result is None

    def test_save_and_get_round_trip(self):
        store = self._store()
        twin = _make_twin("u_0042", risk_score=0.22)
        asyncio.run(store.save(twin))
        loaded = asyncio.run(store.get("u_0042"))
        assert loaded is not None
        assert loaded.user_id == "u_0042"
        assert loaded.risk_score == pytest.approx(0.22, abs=1e-6)

    def test_history_has_entry_after_save(self):
        store = self._store()
        twin = _make_twin("u_hist")
        asyncio.run(store.save(twin))
        history = asyncio.run(store.get_history("u_hist", limit=10))
        assert len(history) >= 1

    def test_multiple_saves_builds_history(self):
        store = self._store()
        twin = _make_twin("u_multi")
        for v in range(3):
            twin.version = v
            asyncio.run(store.save(twin))
        history = asyncio.run(store.get_history("u_multi", limit=10))
        assert len(history) == 3

    def test_history_newest_first(self):
        store = self._store()
        twin = _make_twin("u_order")
        for v in range(3):
            twin.version = v
            asyncio.run(store.save(twin))
        history = asyncio.run(store.get_history("u_order", limit=5))
        # LPUSH → newest first (index 0 is last saved)
        versions = [h["version"] for h in history]
        assert versions[0] >= versions[-1]

    def test_reconstruct_at_before_any_save_returns_none(self):
        store = self._store()
        result = asyncio.run(
            store.reconstruct_at("u_none", datetime(2026, 1, 1))
        )
        assert result is None

    def test_reconstruct_at_finds_snapshot_before_target(self):
        store = self._store()
        twin = _make_twin("u_travel")
        past_ts = datetime(2026, 1, 15, 10, 0, 0)
        twin.last_updated = past_ts
        twin.version = 1
        asyncio.run(store.save(twin))

        result = asyncio.run(
            store.reconstruct_at("u_travel", datetime(2026, 4, 11))
        )
        assert result is not None
        assert result["version"] == 1

    def test_delete_clears_state_and_history(self):
        store = self._store()
        twin = _make_twin("u_del")
        asyncio.run(store.save(twin))
        asyncio.run(store.delete("u_del"))
        assert asyncio.run(store.get("u_del")) is None
        assert asyncio.run(store.get_history("u_del")) == []

    def test_bulk_save(self):
        store = self._store()
        twins = [_make_twin(f"u_{i:03d}") for i in range(5)]
        count = asyncio.run(store.bulk_save(twins))
        assert count == 5
        for t in twins:
            loaded = asyncio.run(store.get(t.user_id))
            assert loaded is not None


# ─────────────────────────────────────────────────────────────────────────────
# TwinService — update lifecycle
# ─────────────────────────────────────────────────────────────────────────────

class TestTwinService:

    def _svc(self):
        from src.twin.twin_service import TwinService
        return TwinService(FakeRedis())

    def test_update_increments_version(self):
        svc = self._svc()
        fv = _make_feature_vector()
        twin = asyncio.run(svc.update_from_features(fv, emit_event=False))
        assert twin.version == 1

    def test_update_twice_version_is_2(self):
        svc = self._svc()
        fv = _make_feature_vector()
        asyncio.run(svc.update_from_features(fv, emit_event=False))
        twin = asyncio.run(svc.update_from_features(fv, emit_event=False))
        assert twin.version == 2

    def test_update_sets_risk_score_in_0_1(self):
        svc = self._svc()
        fv = _make_feature_vector()
        twin = asyncio.run(svc.update_from_features(fv, emit_event=False))
        assert 0.0 <= twin.risk_score <= 1.0

    def test_update_sets_liquidity_health(self):
        svc = self._svc()
        fv = _make_feature_vector(cash_buffer_days=3.0)
        twin = asyncio.run(svc.update_from_features(fv, emit_event=False))
        assert twin.liquidity_health == "LOW"

    def test_update_medium_liquidity(self):
        svc = self._svc()
        fv = _make_feature_vector(cash_buffer_days=10.0)
        twin = asyncio.run(svc.update_from_features(fv, emit_event=False))
        assert twin.liquidity_health == "MEDIUM"

    def test_update_high_liquidity(self):
        svc = self._svc()
        fv = _make_feature_vector(cash_buffer_days=30.0)
        twin = asyncio.run(svc.update_from_features(fv, emit_event=False))
        assert twin.liquidity_health == "HIGH"

    def test_high_burden_infers_struggling_persona(self):
        svc = self._svc()
        fv = _make_feature_vector(emi_burden_ratio=0.7, savings_rate=0.01)
        twin = asyncio.run(svc.update_from_features(fv, emit_event=False))
        assert twin.persona in ("genuine_struggling", "emi_at_risk", "genuine_healthy",
                                "shell_circular", "paper_trader", "new_to_credit", "unknown")
        # struggling specifically
        fv2 = _make_feature_vector(emi_burden_ratio=0.8, savings_rate=0.0)
        twin2 = asyncio.run(svc.update_from_features(fv2, emit_event=False))
        assert twin2.persona == "genuine_struggling"

    def test_new_to_credit_persona_sparse_income(self):
        svc = self._svc()
        fv = _make_feature_vector(
            income_90d=10000.0,
            income_30d=3000.0,
            income_7d=500.0,
            emi_payment_count_90d=0,
            daily_avg_throughput_30d=500.0,
        )
        twin = asyncio.run(svc.update_from_features(fv, emit_event=False))
        assert twin.persona == "new_to_credit"

    def test_shell_circular_high_concentration_failure(self):
        svc = self._svc()
        fv = _make_feature_vector(
            top3_merchant_concentration=0.95,
            debit_failure_rate_90d=0.5,
            daily_avg_throughput_30d=200_000.0,
        )
        twin = asyncio.run(svc.update_from_features(fv, emit_event=False))
        assert twin.persona == "shell_circular"

    def test_dna_has_correct_dim(self):
        svc = self._svc()
        fv = _make_feature_vector()
        twin = asyncio.run(svc.update_from_features(fv, emit_event=False))
        assert len(twin.financial_dna) == DNA_DIM

    def test_avatar_derived_after_update(self):
        svc = self._svc()
        fv = _make_feature_vector(cash_buffer_days=2.0)
        twin = asyncio.run(svc.update_from_features(fv, emit_event=False))
        assert twin.avatar_state.expression == "urgent"

    def test_risk_history_appended(self):
        svc = self._svc()
        fv = _make_feature_vector()
        twin = asyncio.run(svc.update_from_features(fv, emit_event=False))
        assert len(twin.risk_history) == 1
        assert 0.0 <= twin.risk_history[0] <= 1.0

    def test_get_returns_none_for_unknown_user(self):
        svc = self._svc()
        result = asyncio.run(svc.get("u_nobody"))
        assert result is None

    def test_get_returns_saved_twin(self):
        svc = self._svc()
        fv = _make_feature_vector()
        asyncio.run(svc.update_from_features(fv, emit_event=False))
        twin = asyncio.run(svc.get("u_test"))
        assert twin is not None
        assert twin.user_id == "u_test"

    def test_high_risk_fv_produces_higher_score_than_low_risk(self):
        svc_high = self._svc()
        svc_low = self._svc()
        fv_high = _make_feature_vector(
            emi_burden_ratio=1.8,
            debit_failure_rate_90d=0.9,
            cash_buffer_days=1.0,
            savings_rate=-0.3,
            spending_volatility_index=2.5,
        )
        fv_low = _make_feature_vector(
            emi_burden_ratio=0.05,
            debit_failure_rate_90d=0.0,
            cash_buffer_days=80.0,
            savings_rate=0.4,
            spending_volatility_index=0.05,
        )
        twin_high = asyncio.run(svc_high.update_from_features(fv_high, emit_event=False))
        twin_low = asyncio.run(svc_low.update_from_features(fv_low, emit_event=False))
        assert twin_high.risk_score > twin_low.risk_score

    def test_cibil_score_higher_for_low_risk(self):
        svc_high = self._svc()
        svc_low = self._svc()
        fv_high = _make_feature_vector(
            emi_burden_ratio=1.5, debit_failure_rate_90d=0.8, cash_buffer_days=1.0)
        fv_low = _make_feature_vector(
            emi_burden_ratio=0.1, debit_failure_rate_90d=0.0, cash_buffer_days=70.0)
        t_high = asyncio.run(svc_high.update_from_features(fv_high, emit_event=False))
        t_low = asyncio.run(svc_low.update_from_features(fv_low, emit_event=False))
        assert t_low.cibil_like_score() > t_high.cibil_like_score()

    def test_get_history_empty_before_update(self):
        svc = self._svc()
        history = asyncio.run(svc.get_history("u_fresh"))
        assert history == []

    def test_get_history_populated_after_update(self):
        svc = self._svc()
        fv = _make_feature_vector()
        asyncio.run(svc.update_from_features(fv, emit_event=False))
        history = asyncio.run(svc.get_history("u_test"))
        assert len(history) >= 1

    def test_twin_persisted_across_service_instances(self):
        fake_redis = FakeRedis()
        from src.twin.twin_service import TwinService
        svc1 = TwinService(fake_redis)
        svc2 = TwinService(fake_redis)

        fv = _make_feature_vector()
        asyncio.run(svc1.update_from_features(fv, emit_event=False))
        twin = asyncio.run(svc2.get("u_test"))
        assert twin is not None
        assert twin.user_id == "u_test"
