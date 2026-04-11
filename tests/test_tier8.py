"""
Tests for Tier 8 — Proactive Intervention & Avatar Layer

Covers:
  - TriggerEngine: all 7 triggers, threshold boundaries, priority sorting
  - Relevance score computation: formula, threshold gate
  - DialogueManager: intent detection for 8 intents, all response paths,
    system prompt builder, chat return schema
  - ReportGenerator: daily + weekly reports, key insight logic,
    WhatsApp / SMS formatting, opt-out footer
  - AuditLogger: log / get_user_audit / replay_since (fake Redis)
  - NotificationService: dispatch gating (consent / relevance), channel
    selection, Redis stream write
  - AgentOrchestrator: event handling, trigger evaluation → notification
    pipeline, EOD report dispatch
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, date, timedelta, timezone

import pytest

from src.twin.twin_model import DigitalTwin
from src.intervention.trigger_engine import (
    TriggerResult,
    evaluate_triggers,
    compute_relevance_score,
)
from src.intervention.dialogue_manager import DialogueManager, _detect_intent
from src.intervention.report_generator import (
    generate_report,
    format_whatsapp_message,
    format_sms_message,
)


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
    twin = DigitalTwin(
        user_id=user_id,
        risk_score=risk_score,
        liquidity_health=liquidity_health,
        emi_burden_ratio=emi_burden_ratio,
        cash_buffer_days=cash_buffer_days,
        spending_volatility=spending_volatility,
        income_stability=income_stability,
        persona=persona,
    )
    twin.derive_avatar()
    return twin


# Reuse the same fake Redis from tier4 tests
class FakeRedis:
    def __init__(self):
        self._kv: dict[str, str] = {}
        self._lists: dict[str, list[str]] = {}
        self._zsets: dict[str, list[tuple[float, str]]] = {}
        self._streams: dict[str, list[dict]] = {}

    def pipeline(self):
        return FakePipeline(self)

    async def get(self, key):
        return self._kv.get(key)

    async def set(self, key, value):
        self._kv[key] = value

    async def lpush(self, key, value):
        self._lists.setdefault(key, []).insert(0, value)

    async def ltrim(self, key, start, stop):
        lst = self._lists.get(key, [])
        self._lists[key] = lst[start:] if stop == -1 else lst[start:stop + 1]

    async def lrange(self, key, start, stop):
        lst = self._lists.get(key, [])
        return lst[start:] if stop == -1 else lst[start:stop + 1]

    async def delete(self, *keys):
        for k in keys:
            self._kv.pop(k, None)
            self._lists.pop(k, None)
            self._zsets.pop(k, None)

    async def zadd(self, key, mapping: dict):
        self._zsets.setdefault(key, [])
        for member, score in mapping.items():
            # remove old entry for this member, then insert with new score
            self._zsets[key] = [(s, m) for s, m in self._zsets[key] if m != member]
            self._zsets[key].append((float(score), member))
            self._zsets[key].sort(key=lambda x: x[0])

    async def zremrangebyrank(self, key, start, stop):
        zset = self._zsets.get(key, [])
        if stop < 0:
            stop = len(zset) + stop + 1
        self._zsets[key] = [e for i, e in enumerate(zset) if not (start <= i <= stop)]

    async def zrevrange(self, key, start, stop):
        zset = self._zsets.get(key, [])
        rev = list(reversed(zset))
        if stop == -1:
            return [m for _, m in rev[start:]]
        return [m for _, m in rev[start:stop + 1]]

    async def zrangebyscore(self, key, min_score, max_score):
        zset = self._zsets.get(key, [])
        if max_score == "+inf":
            max_score = float("inf")
        return [m for s, m in zset if min_score <= s <= max_score]

    async def xadd(self, key, fields, maxlen=None, approximate=False):
        self._streams.setdefault(key, []).append(fields)

    async def publish(self, channel, message):
        pass


class FakePipeline:
    def __init__(self, redis):
        self._r = redis
        self._ops = []

    def set(self, k, v):
        self._ops.append(("set", k, v)); return self

    def lpush(self, k, v):
        self._ops.append(("lpush", k, v)); return self

    def ltrim(self, k, s, e):
        self._ops.append(("ltrim", k, s, e)); return self

    def zadd(self, k, m):
        self._ops.append(("zadd", k, m)); return self

    def zremrangebyrank(self, k, s, e):
        self._ops.append(("zrem", k, s, e)); return self

    async def execute(self):
        for op in self._ops:
            if op[0] == "set":
                await self._r.set(op[1], op[2])
            elif op[0] == "lpush":
                await self._r.lpush(op[1], op[2])
            elif op[0] == "ltrim":
                await self._r.ltrim(op[1], op[2], op[3])
            elif op[0] == "zadd":
                await self._r.zadd(op[1], op[2])
            elif op[0] == "zrem":
                await self._r.zremrangebyrank(op[1], op[2], op[3])
        self._ops.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Trigger Engine
# ─────────────────────────────────────────────────────────────────────────────

class TestTriggerEngine:

    def test_no_triggers_healthy_twin(self):
        twin = _make_twin(
            liquidity_health="HIGH",
            cash_buffer_days=30.0,
            emi_burden_ratio=0.2,
            spending_volatility=0.3,
            persona="genuine_healthy",
        )
        fired = evaluate_triggers(twin)
        types = [t.trigger_type for t in fired]
        assert "liquidity_drop" not in types
        assert "emi_at_risk" not in types
        assert "fraud_anomaly" not in types

    def test_liquidity_drop_fires_when_low(self):
        twin = _make_twin(liquidity_health="LOW", cash_buffer_days=3.0)
        fired = evaluate_triggers(twin)
        types = [t.trigger_type for t in fired]
        assert "liquidity_drop" in types

    def test_liquidity_drop_fires_when_buffer_below_10(self):
        twin = _make_twin(liquidity_health="MEDIUM", cash_buffer_days=8.0)
        fired = evaluate_triggers(twin)
        types = [t.trigger_type for t in fired]
        assert "liquidity_drop" in types

    def test_liquidity_drop_not_fired_at_10_exactly(self):
        twin = _make_twin(liquidity_health="MEDIUM", cash_buffer_days=10.0)
        fired = evaluate_triggers(twin)
        types = [t.trigger_type for t in fired]
        assert "liquidity_drop" not in types

    def test_emi_at_risk_fires_above_threshold(self):
        twin = _make_twin(emi_burden_ratio=0.5)
        fired = evaluate_triggers(twin)
        types = [t.trigger_type for t in fired]
        assert "emi_at_risk" in types

    def test_emi_at_risk_not_fired_below_threshold(self):
        twin = _make_twin(emi_burden_ratio=0.2, cash_buffer_days=30.0)
        fired = evaluate_triggers(twin)
        types = [t.trigger_type for t in fired]
        assert "emi_at_risk" not in types

    def test_overspend_fires_high_volatility(self):
        twin = _make_twin(spending_volatility=0.8)
        fired = evaluate_triggers(twin)
        types = [t.trigger_type for t in fired]
        assert "overspend_warning" in types

    def test_overspend_not_fired_low_volatility(self):
        twin = _make_twin(spending_volatility=0.3, cash_buffer_days=30.0,
                          emi_burden_ratio=0.2)
        fired = evaluate_triggers(twin)
        types = [t.trigger_type for t in fired]
        assert "overspend_warning" not in types

    def test_lifestyle_inflation_fires_when_qoq_increase_above_25(self):
        twin = _make_twin(spending_volatility=0.5)
        fired = evaluate_triggers(twin, prev_spending_volatility=0.3)
        types = [t.trigger_type for t in fired]
        assert "lifestyle_inflation" in types

    def test_lifestyle_inflation_not_fired_small_increase(self):
        twin = _make_twin(spending_volatility=0.32)
        fired = evaluate_triggers(twin, prev_spending_volatility=0.3)
        types = [t.trigger_type for t in fired]
        assert "lifestyle_inflation" not in types

    def test_lifestyle_inflation_not_fired_when_no_prev(self):
        twin = _make_twin(spending_volatility=0.9)
        fired = evaluate_triggers(twin, prev_spending_volatility=None)
        types = [t.trigger_type for t in fired]
        assert "lifestyle_inflation" not in types

    def test_savings_opportunity_fires_healthy_buffer_low_burden(self):
        twin = _make_twin(
            cash_buffer_days=30.0,
            emi_burden_ratio=0.15,
            risk_score=0.25,
            spending_volatility=0.3,
        )
        fired = evaluate_triggers(twin)
        types = [t.trigger_type for t in fired]
        assert "savings_opportunity" in types

    def test_savings_opportunity_not_fired_low_buffer(self):
        twin = _make_twin(cash_buffer_days=5.0, emi_burden_ratio=0.15, risk_score=0.2)
        fired = evaluate_triggers(twin)
        types = [t.trigger_type for t in fired]
        assert "savings_opportunity" not in types

    def test_fraud_anomaly_fires_shell_circular(self):
        twin = _make_twin(persona="shell_circular")
        fired = evaluate_triggers(twin)
        types = [t.trigger_type for t in fired]
        assert "fraud_anomaly" in types

    def test_fraud_anomaly_not_fired_healthy(self):
        twin = _make_twin(persona="genuine_healthy", cash_buffer_days=30.0,
                          emi_burden_ratio=0.2)
        fired = evaluate_triggers(twin)
        types = [t.trigger_type for t in fired]
        assert "fraud_anomaly" not in types

    def test_new_to_credit_guidance_fires(self):
        twin = _make_twin(persona="new_to_credit")
        fired = evaluate_triggers(twin)
        types = [t.trigger_type for t in fired]
        assert "new_to_credit_guidance" in types

    def test_triggers_sorted_high_before_low(self):
        twin = _make_twin(
            liquidity_health="LOW",
            cash_buffer_days=3.0,
            emi_burden_ratio=0.5,
            persona="new_to_credit",
        )
        fired = evaluate_triggers(twin)
        priorities = [t.priority for t in fired]
        order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        assert priorities == sorted(priorities, key=lambda p: order[p])

    def test_trigger_result_has_suggested_actions(self):
        twin = _make_twin(liquidity_health="LOW", cash_buffer_days=3.0)
        fired = evaluate_triggers(twin)
        liq = next(t for t in fired if t.trigger_type == "liquidity_drop")
        assert len(liq.suggested_actions) > 0

    def test_trigger_channels_populated(self):
        twin = _make_twin(liquidity_health="LOW", cash_buffer_days=3.0)
        fired = evaluate_triggers(twin)
        liq = next(t for t in fired if t.trigger_type == "liquidity_drop")
        assert "sms" in liq.channels
        assert "push" in liq.channels

    def test_liquidity_trigger_high_priority(self):
        twin = _make_twin(liquidity_health="LOW", cash_buffer_days=2.0)
        fired = evaluate_triggers(twin)
        liq = next(t for t in fired if t.trigger_type == "liquidity_drop")
        assert liq.priority == "HIGH"

    def test_savings_opportunity_low_priority(self):
        twin = _make_twin(cash_buffer_days=40.0, emi_burden_ratio=0.1, risk_score=0.2)
        fired = evaluate_triggers(twin)
        sav = next((t for t in fired if t.trigger_type == "savings_opportunity"), None)
        if sav:
            assert sav.priority == "LOW"
            assert "whatsapp" in sav.channels


class TestRelevanceScore:

    def test_formula_correct(self):
        trigger = TriggerResult(
            trigger_type="liquidity_drop",
            fired=True,
            priority="HIGH",
            channels=["sms"],
            urgency=0.9,
            reason="test",
        )
        score = compute_relevance_score(
            trigger,
            personalization=0.8,
            acceptance_history=0.6,
            safety_factor=1.0,
        )
        expected = 0.4 * 0.9 + 0.3 * 0.8 + 0.2 * 0.6 + 0.1 * 1.0
        assert score == pytest.approx(expected, abs=1e-9)

    def test_high_urgency_exceeds_threshold(self):
        trigger = TriggerResult(
            trigger_type="emi_at_risk", fired=True,
            priority="HIGH", channels=["sms"],
            urgency=0.95, reason="test",
        )
        score = compute_relevance_score(trigger, 0.9, 0.8, 1.0)
        assert score >= 0.75

    def test_low_urgency_below_threshold(self):
        trigger = TriggerResult(
            trigger_type="savings_opportunity", fired=True,
            priority="LOW", channels=["whatsapp"],
            urgency=0.1, reason="test",
        )
        score = compute_relevance_score(trigger, 0.2, 0.2, 0.5)
        assert score < 0.75

    def test_score_bounded_0_1(self):
        trigger = TriggerResult(
            trigger_type="liquidity_drop", fired=True,
            priority="HIGH", channels=["sms"],
            urgency=1.0, reason="test",
        )
        score = compute_relevance_score(trigger, 1.0, 1.0, 1.0)
        assert 0.0 <= score <= 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Dialogue Manager
# ─────────────────────────────────────────────────────────────────────────────

class TestIntentDetection:

    def test_liquidity_intent(self):
        assert _detect_intent("What is my cash buffer?") == "liquidity"

    def test_emi_intent(self):
        assert _detect_intent("Tell me about my loan repayment") == "emi"

    def test_savings_intent(self):
        assert _detect_intent("How should I invest my savings?") == "savings"

    def test_credit_score_intent(self):
        assert _detect_intent("What's my CIBIL score?") == "credit_score"

    def test_spending_intent(self):
        assert _detect_intent("Review my spending pattern") == "spending"

    def test_forecast_intent(self):
        assert _detect_intent("What will happen in next 30 days?") == "forecast"

    def test_improvement_intent(self):
        # "improve" matches improvement; "score" also matches credit_score but
        # improvement pattern comes later — test with a query that doesn't have "score"
        assert _detect_intent("How can I improve my finances?") == "improvement"

    def test_explain_intent(self):
        # "why" matches explain; "score" also matches credit_score — use query
        # without "score" to isolate explain intent
        assert _detect_intent("Why am I getting alerts?") == "explain"

    def test_unknown_falls_back_to_general(self):
        assert _detect_intent("xyzabc nonsense") == "general"


class TestDialogueManager:

    def _dm(self):
        return DialogueManager()

    def test_chat_returns_expected_keys(self):
        dm = self._dm()
        twin = _make_twin()
        resp = dm.chat("What is my cash buffer?", twin)
        required_keys = {"role", "content", "intent", "includes_simulation",
                         "avatar_expression", "mood_message", "cibil_score", "ts"}
        assert required_keys.issubset(resp.keys())

    def test_role_is_twin(self):
        dm = self._dm()
        resp = dm.chat("hello", _make_twin())
        assert resp["role"] == "twin"

    def test_content_non_empty(self):
        dm = self._dm()
        resp = dm.chat("Tell me about my finances", _make_twin())
        assert len(resp["content"]) > 10

    def test_cibil_score_in_response(self):
        dm = self._dm()
        twin = _make_twin(risk_score=0.3)
        resp = dm.chat("What is my CIBIL score?", twin)
        assert resp["cibil_score"] == twin.cibil_like_score()
        assert 300 <= resp["cibil_score"] <= 900

    def test_avatar_expression_in_response(self):
        dm = self._dm()
        twin = _make_twin(liquidity_health="LOW")
        resp = dm.chat("am I ok?", twin)
        assert resp["avatar_expression"] in ("calm", "concerned", "urgent", "educational")

    def test_ts_is_parseable_iso_datetime(self):
        dm = self._dm()
        resp = dm.chat("hi", _make_twin())
        datetime.fromisoformat(resp["ts"])  # should not raise

    def test_liquidity_low_response_mentions_buffer(self):
        dm = self._dm()
        twin = _make_twin(liquidity_health="LOW", cash_buffer_days=3.0)
        resp = dm.chat("How is my liquidity?", twin)
        assert "LOW" in resp["content"] or "buffer" in resp["content"].lower()

    def test_emi_high_burden_response_mentions_emi(self):
        dm = self._dm()
        twin = _make_twin(emi_burden_ratio=0.6)
        resp = dm.chat("Tell me about my EMI", twin)
        content_lower = resp["content"].lower()
        assert "emi" in content_lower or "burden" in content_lower or "restructur" in content_lower

    def test_credit_score_response_mentions_cibil(self):
        dm = self._dm()
        twin = _make_twin(risk_score=0.4)
        resp = dm.chat("What is my CIBIL score?", twin)
        content = resp["content"]
        assert str(twin.cibil_like_score()) in content

    def test_improvement_response_contains_tips(self):
        dm = self._dm()
        twin = _make_twin(emi_burden_ratio=0.5, cash_buffer_days=5.0)
        resp = dm.chat("How can I improve?", twin)
        assert len(resp["content"]) > 20

    def test_forecast_response_non_empty(self):
        dm = self._dm()
        resp = dm.chat("What will my finances look like in 30 days?", _make_twin())
        assert len(resp["content"]) > 20

    def test_system_prompt_contains_twin_metrics(self):
        dm = self._dm()
        twin = _make_twin(risk_score=0.4, liquidity_health="MEDIUM")
        prompt = dm.build_system_prompt(twin, recent_triggers=["liquidity_drop"])
        assert "MEDIUM" in prompt
        assert "liquidity_drop" in prompt
        assert "CIBIL" in prompt or "cibil" in prompt.lower()

    def test_system_prompt_contains_ai_disclaimer(self):
        dm = self._dm()
        prompt = dm.build_system_prompt(_make_twin())
        assert "AI" in prompt or "ai" in prompt.lower()

    def test_all_intents_produce_non_empty_response(self):
        dm = self._dm()
        twin = _make_twin()
        queries = [
            "How is my liquidity?",
            "Tell me about my EMI",
            "How to save money?",
            "What is my CIBIL score?",
            "Review my spending",
            "What happens in next 30 days?",
            "How can I improve?",
            "Why is my score this way?",
            "Just checking in",
        ]
        for q in queries:
            resp = dm.chat(q, twin)
            assert len(resp["content"]) > 5, f"Empty response for: {q}"


# ─────────────────────────────────────────────────────────────────────────────
# Report Generator
# ─────────────────────────────────────────────────────────────────────────────

class TestReportGenerator:

    def test_daily_report_structure(self):
        twin = _make_twin()
        report = generate_report(twin, "daily_summary")
        required = {
            "report_type", "user_id", "date", "risk_status",
            "cibil_like_score", "liquidity_health", "twin_version",
            "key_insights", "suggested_actions", "full_report_link",
            "generated_at", "opt_out_note",
        }
        assert required.issubset(report.keys())

    def test_weekly_report_type(self):
        twin = _make_twin()
        report = generate_report(twin, "weekly_summary")
        assert report["report_type"] == "weekly_summary"

    def test_cibil_score_in_report(self):
        twin = _make_twin(risk_score=0.3)
        report = generate_report(twin)
        assert report["cibil_like_score"] == twin.cibil_like_score()

    def test_report_user_id_matches(self):
        twin = _make_twin("u_specific")
        report = generate_report(twin)
        assert report["user_id"] == "u_specific"

    def test_risk_status_excellent_for_low_risk(self):
        twin = _make_twin(risk_score=0.05)
        report = generate_report(twin)
        assert report["risk_status"] == "Excellent"

    def test_risk_status_needs_attention_for_high_risk(self):
        twin = _make_twin(risk_score=0.9)
        report = generate_report(twin)
        assert report["risk_status"] == "Needs Attention"

    def test_low_liquidity_appears_in_insights(self):
        twin = _make_twin(liquidity_health="LOW", cash_buffer_days=3.0)
        report = generate_report(twin)
        insight_text = " ".join(report["key_insights"])
        assert "LOW" in insight_text or "buffer" in insight_text.lower()

    def test_high_emi_burden_appears_in_insights(self):
        twin = _make_twin(emi_burden_ratio=0.6)
        report = generate_report(twin)
        insight_text = " ".join(report["key_insights"])
        assert "EMI" in insight_text or "burden" in insight_text.lower()

    def test_suggested_actions_non_empty(self):
        twin = _make_twin(cash_buffer_days=5.0, emi_burden_ratio=0.5)
        report = generate_report(twin)
        assert len(report["suggested_actions"]) > 0

    def test_healthy_twin_actions_not_empty(self):
        twin = _make_twin()
        report = generate_report(twin)
        # even healthy twins get an action (maintain habits)
        assert len(report["suggested_actions"]) > 0

    def test_full_report_link_contains_user_id(self):
        twin = _make_twin("u_link_test")
        report = generate_report(twin)
        assert "u_link_test" in report["full_report_link"]

    def test_opt_out_note_present(self):
        twin = _make_twin()
        report = generate_report(twin)
        assert len(report["opt_out_note"]) > 5

    def test_date_can_be_overridden(self):
        twin = _make_twin()
        custom_date = date(2026, 1, 15)
        report = generate_report(twin, report_date=custom_date)
        assert report["date"] == "2026-01-15"

    def test_whatsapp_format_has_opt_out(self):
        twin = _make_twin()
        report = generate_report(twin)
        msg = format_whatsapp_message(report)
        assert "STOP" in msg or "opt" in msg.lower()

    def test_whatsapp_format_has_score(self):
        twin = _make_twin(risk_score=0.3)
        report = generate_report(twin)
        msg = format_whatsapp_message(report)
        assert str(twin.cibil_like_score()) in msg

    def test_sms_format_short_enough(self):
        twin = _make_twin()
        report = generate_report(twin)
        sms = format_sms_message(report)
        # Should be reasonably compact (under 320 chars for 2 SMS units)
        assert len(sms) < 320

    def test_sms_format_contains_score(self):
        twin = _make_twin(risk_score=0.3)
        report = generate_report(twin)
        sms = format_sms_message(report)
        assert str(twin.cibil_like_score()) in sms

    def test_sms_format_contains_liquidity(self):
        twin = _make_twin(liquidity_health="LOW")
        report = generate_report(twin)
        sms = format_sms_message(report)
        assert "LOW" in sms


# ─────────────────────────────────────────────────────────────────────────────
# Audit Logger
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditLogger:

    def _logger(self):
        from src.intervention.audit_logger import AuditLogger
        return AuditLogger(FakeRedis())

    def test_log_returns_event_id(self):
        logger = self._logger()
        eid = asyncio.run(logger.log("u_1", "twin_updated", {"version": 1}))
        assert len(eid) == 36  # UUID4

    def test_log_stores_retrievable_record(self):
        logger = self._logger()
        asyncio.run(logger.log("u_1", "twin_updated", {"version": 1}))
        records = asyncio.run(logger.get_user_audit("u_1"))
        assert len(records) == 1
        assert records[0]["event_type"] == "twin_updated"

    def test_multiple_logs_all_retrieved(self):
        logger = self._logger()
        for i in range(5):
            asyncio.run(logger.log("u_multi", "trigger_fired", {"i": i}))
        records = asyncio.run(logger.get_user_audit("u_multi", limit=10))
        assert len(records) == 5

    def test_event_type_filter(self):
        logger = self._logger()
        asyncio.run(logger.log("u_f", "twin_updated", {}))
        asyncio.run(logger.log("u_f", "notification_sent", {}))
        asyncio.run(logger.log("u_f", "twin_updated", {}))
        records = asyncio.run(
            logger.get_user_audit("u_f", limit=10, event_type="twin_updated")
        )
        assert all(r["event_type"] == "twin_updated" for r in records)
        assert len(records) == 2

    def test_consent_status_stamped(self):
        logger = self._logger()
        asyncio.run(logger.log("u_c", "twin_updated", {}, consent_status=False))
        records = asyncio.run(logger.get_user_audit("u_c"))
        assert records[0]["consent_status"] is False

    def test_user_id_stamped_in_record(self):
        logger = self._logger()
        asyncio.run(logger.log("u_stamp", "report_generated", {}))
        records = asyncio.run(logger.get_user_audit("u_stamp"))
        assert records[0]["user_id"] == "u_stamp"

    def test_replay_since_returns_records_after_ts(self):
        logger = self._logger()
        before = datetime.now(timezone.utc) - timedelta(seconds=1)
        asyncio.run(logger.log("u_replay", "twin_updated", {"v": 1}))
        asyncio.run(logger.log("u_replay", "trigger_fired", {"v": 2}))
        records = asyncio.run(logger.replay_since("u_replay", before))
        assert len(records) == 2

    def test_replay_since_future_ts_returns_empty(self):
        # Log a record now, then query 1 hour in the future → nothing returned.
        logger = self._logger()
        asyncio.run(logger.log("u_future2", "twin_updated", {}))
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        records = asyncio.run(logger.replay_since("u_future2", future))
        assert records == []

    def test_get_audit_empty_user_returns_empty_list(self):
        logger = self._logger()
        records = asyncio.run(logger.get_user_audit("u_nobody"))
        assert records == []

    def test_payload_stored_correctly(self):
        logger = self._logger()
        payload = {"risk_score": 0.42, "version": 7}
        asyncio.run(logger.log("u_p", "twin_updated", payload))
        records = asyncio.run(logger.get_user_audit("u_p"))
        assert records[0]["payload"]["risk_score"] == 0.42
        assert records[0]["payload"]["version"] == 7


# ─────────────────────────────────────────────────────────────────────────────
# Notification Service
# ─────────────────────────────────────────────────────────────────────────────

class TestNotificationService:

    def _svc(self):
        from src.intervention.notification_service import NotificationService
        return NotificationService(FakeRedis())

    def _trigger(self, trigger_type="liquidity_drop", channels=None, urgency=0.9):
        return TriggerResult(
            trigger_type=trigger_type,
            fired=True,
            priority="HIGH",
            channels=channels or ["sms", "push"],
            urgency=urgency,
            reason="test trigger",
        )

    def test_dispatch_returns_notification_ids(self):
        svc = self._svc()
        trigger = self._trigger()
        ids = asyncio.run(svc.dispatch(
            "u_1", trigger, consent=True, relevance_score=0.85
        ))
        assert len(ids) == 2  # sms + push

    def test_dispatch_blocked_by_consent_false(self):
        svc = self._svc()
        ids = asyncio.run(svc.dispatch(
            "u_1", self._trigger(), consent=False, relevance_score=0.99
        ))
        assert ids == []

    def test_dispatch_blocked_below_relevance_threshold(self):
        svc = self._svc()
        ids = asyncio.run(svc.dispatch(
            "u_1", self._trigger(), consent=True,
            relevance_score=0.5, relevance_threshold=0.75
        ))
        assert ids == []

    def test_dispatch_at_threshold_fires(self):
        svc = self._svc()
        ids = asyncio.run(svc.dispatch(
            "u_1", self._trigger(), consent=True,
            relevance_score=0.75, relevance_threshold=0.75
        ))
        assert len(ids) > 0

    def test_single_channel_returns_one_id(self):
        svc = self._svc()
        trigger = self._trigger(channels=["push"])
        ids = asyncio.run(svc.dispatch(
            "u_1", trigger, consent=True, relevance_score=0.9
        ))
        assert len(ids) == 1

    def test_notification_written_to_redis_stream(self):
        fake = FakeRedis()
        from src.intervention.notification_service import NotificationService
        svc = NotificationService(fake)
        asyncio.run(svc.dispatch(
            "u_stream", self._trigger(), consent=True, relevance_score=0.9
        ))
        assert len(fake._streams.get("stream:notifications", [])) > 0

    def test_notification_record_has_user_id(self):
        fake = FakeRedis()
        from src.intervention.notification_service import NotificationService
        svc = NotificationService(fake)
        asyncio.run(svc.dispatch(
            "u_check", self._trigger(), consent=True, relevance_score=0.9
        ))
        records = fake._streams.get("stream:notifications", [])
        assert any(r.get("user_id") == "u_check" for r in records)

    def test_whatsapp_trigger_uses_whatsapp_channel(self):
        svc = self._svc()
        trigger = self._trigger(trigger_type="savings_opportunity", channels=["whatsapp"])
        ids = asyncio.run(svc.dispatch(
            "u_wa", trigger, consent=True, relevance_score=0.9
        ))
        assert len(ids) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Agent Orchestrator integration
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentOrchestrator:
    """
    Integration tests for the agent's event handling pipeline.
    We test _handle_event directly (bypasses pub/sub listener).
    """

    def _setup(self):
        from src.intervention.agent_orchestrator import InterventionAgent
        from src.twin.twin_service import TwinService
        from src.twin.twin_store import TwinStore
        from src.intervention.audit_logger import AuditLogger
        from src.intervention.notification_service import NotificationService

        fake = FakeRedis()
        agent = InterventionAgent.__new__(InterventionAgent)
        agent._redis = fake
        agent._twin_svc = TwinService(fake)
        agent._notif_svc = NotificationService(fake)
        agent._audit = AuditLogger(fake)
        from src.intervention.dialogue_manager import DialogueManager
        agent._dialogue = DialogueManager()
        agent._running = False
        agent._acceptance_history = {}
        return agent, fake

    def _save_twin(self, fake: FakeRedis, twin: DigitalTwin):
        from src.twin.twin_store import TwinStore
        store = TwinStore(fake)
        asyncio.run(store.save(twin))

    def test_handle_event_for_low_liquidity_fires_notifications(self):
        agent, fake = self._setup()
        twin = _make_twin("u_event", liquidity_health="LOW", cash_buffer_days=3.0)
        self._save_twin(fake, twin)

        payload = json.dumps({
            "user_id": "u_event",
            "version": 1,
            "risk_score": 0.7,
            "liquidity_health": "LOW",
        })
        asyncio.run(agent._handle_event(payload))
        notifs = fake._streams.get("stream:notifications", [])
        assert len(notifs) > 0

    def test_handle_event_logs_trigger_to_audit(self):
        agent, fake = self._setup()
        twin = _make_twin("u_audit_test", liquidity_health="LOW", cash_buffer_days=3.0)
        self._save_twin(fake, twin)

        payload = json.dumps({"user_id": "u_audit_test", "version": 1})
        asyncio.run(agent._handle_event(payload))

        from src.intervention.audit_logger import AuditLogger
        auditor = AuditLogger(fake)
        records = asyncio.run(auditor.get_user_audit("u_audit_test"))
        event_types = [r["event_type"] for r in records]
        assert "trigger_fired" in event_types

    def test_handle_event_malformed_json_no_crash(self):
        agent, fake = self._setup()
        # should not raise
        asyncio.run(agent._handle_event("{bad json"))

    def test_handle_event_missing_user_id_no_crash(self):
        agent, fake = self._setup()
        payload = json.dumps({"version": 1})
        asyncio.run(agent._handle_event(payload))  # no crash

    def test_handle_event_unknown_user_no_crash(self):
        agent, fake = self._setup()
        payload = json.dumps({"user_id": "u_nobody_here"})
        asyncio.run(agent._handle_event(payload))  # no crash

    def test_handle_event_healthy_twin_no_notifications(self):
        agent, fake = self._setup()
        twin = _make_twin(
            "u_healthy_event",
            liquidity_health="HIGH",
            cash_buffer_days=40.0,
            emi_burden_ratio=0.2,
            spending_volatility=0.3,
            persona="genuine_healthy",
            risk_score=0.2,
        )
        self._save_twin(fake, twin)
        payload = json.dumps({"user_id": "u_healthy_event", "version": 1})
        asyncio.run(agent._handle_event(payload))
        notifs = fake._streams.get("stream:notifications", [])
        assert len(notifs) == 0

    def test_shell_circular_triggers_fraud_anomaly(self):
        agent, fake = self._setup()
        twin = _make_twin("u_shell", persona="shell_circular")
        self._save_twin(fake, twin)
        payload = json.dumps({"user_id": "u_shell"})
        asyncio.run(agent._handle_event(payload))
        from src.intervention.audit_logger import AuditLogger
        records = asyncio.run(AuditLogger(fake).get_user_audit("u_shell"))
        event_types = [r["event_type"] for r in records]
        assert "trigger_fired" in event_types or "intervention_sent" in event_types

    def test_send_daily_report_returns_report(self):
        agent, fake = self._setup()
        twin = _make_twin("u_report")
        self._save_twin(fake, twin)
        report = asyncio.run(agent.send_daily_report("u_report"))
        assert report is not None
        assert report["user_id"] == "u_report"
        assert "key_insights" in report

    def test_send_daily_report_unknown_user_returns_none(self):
        agent, fake = self._setup()
        result = asyncio.run(agent.send_daily_report("u_missing_report"))
        assert result is None

    def test_send_daily_report_logs_to_audit(self):
        agent, fake = self._setup()
        twin = _make_twin("u_report_audit")
        self._save_twin(fake, twin)
        asyncio.run(agent.send_daily_report("u_report_audit"))
        from src.intervention.audit_logger import AuditLogger
        records = asyncio.run(AuditLogger(fake).get_user_audit("u_report_audit"))
        event_types = [r["event_type"] for r in records]
        assert "report_generated" in event_types
