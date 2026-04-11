"""
Tier 8 — Intervention Agent Orchestrator

Autonomous agent loop (tier4_tier8.md §11):

  Listen → Evaluate → Decide → Act → Log

The orchestrator subscribes to the `twin_updated` Redis Pub/Sub channel.
On each event it:
  1. Loads the latest twin state
  2. Evaluates all triggers (trigger_engine)
  3. Computes relevance scores
  4. Dispatches notifications if relevance ≥ 0.75 AND consent = true
  5. Generates daily report at EOD if scheduled
  6. Logs everything via AuditLogger

Run as a standalone async task alongside the FastAPI server:
  python -m src.intervention.agent_orchestrator
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

import redis.asyncio as aioredis

from src.intervention.audit_logger import AuditLogger
from src.intervention.dialogue_manager import DialogueManager
from src.intervention.notification_service import NotificationService
from src.intervention.report_generator import generate_report
from src.intervention.trigger_engine import (
    TriggerResult,
    compute_relevance_score,
    evaluate_triggers,
)
from src.twin.twin_service import TwinService

logger = logging.getLogger(__name__)

_PUBSUB_CHANNEL = "twin_updated"
_RELEVANCE_THRESHOLD = 0.75

# Simulated user consent store — in production read from DB / AA consent service
_CONSENT_STORE: dict[str, bool] = {}  # user_id → consent granted


def _get_consent(user_id: str) -> bool:
    """Check if user has consented to interventions. Defaults to True for prototype."""
    return _CONSENT_STORE.get(user_id, True)


class InterventionAgent:
    """
    Autonomous intervention agent loop.
    One instance per deployment; handles all users via Pub/Sub.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379") -> None:
        self._redis_url = redis_url
        self._redis: aioredis.Redis | None = None
        self._twin_svc: TwinService | None = None
        self._notif_svc: NotificationService | None = None
        self._audit: AuditLogger | None = None
        self._dialogue = DialogueManager()
        self._running = False
        self._acceptance_history: dict[str, float] = {}  # user_id → rolling acceptance rate

    async def start(self) -> None:
        self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
        self._twin_svc = TwinService(self._redis)
        self._notif_svc = NotificationService(self._redis)
        self._audit = AuditLogger(self._redis)
        self._running = True
        logger.info("[agent] Intervention Agent started, listening on '%s'", _PUBSUB_CHANNEL)
        await self._listen_loop()

    async def stop(self) -> None:
        self._running = False
        if self._redis:
            await self._redis.aclose()

    # ── main listen loop ──────────────────────────────────────────────────────

    async def _listen_loop(self) -> None:
        assert self._redis is not None
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(_PUBSUB_CHANNEL)
        try:
            while self._running:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message["type"] == "message":
                    await self._handle_event(message["data"])
        finally:
            await pubsub.unsubscribe(_PUBSUB_CHANNEL)
            await pubsub.aclose()

    # ── event handler ─────────────────────────────────────────────────────────

    async def _handle_event(self, data: str) -> None:
        """Process a single twin_updated pub/sub message."""
        try:
            event: dict[str, Any] = json.loads(data)
        except json.JSONDecodeError:
            return

        user_id: str = event.get("user_id", "")
        if not user_id:
            return

        assert self._twin_svc is not None
        assert self._audit is not None

        # Step 1: Load latest twin
        twin = await self._twin_svc.get(user_id)
        if twin is None:
            return

        # Step 2: Get previous volatility for lifestyle inflation check
        history = await self._twin_svc.get_history(user_id, limit=5)
        prev_volatility: float | None = None
        if len(history) >= 2:
            older = history[-1]  # oldest in the fetched window
            prev_volatility = older.get("spending_volatility")

        # Step 3: Evaluate triggers
        fired_triggers = evaluate_triggers(twin, prev_spending_volatility=prev_volatility)

        if not fired_triggers:
            return

        # Step 4: Log trigger events
        await self._audit.log(
            user_id,
            "trigger_fired",
            {
                "triggers": [t.trigger_type for t in fired_triggers],
                "twin_version": twin.version,
                "risk_score": twin.risk_score,
                "liquidity_health": twin.liquidity_health,
            },
            consent_status=_get_consent(user_id),
        )

        # Step 5: Decide & Act
        consent = _get_consent(user_id)
        acceptance = self._acceptance_history.get(user_id, 0.5)

        for trigger in fired_triggers:
            # Shell/circular → no credit offers, force human escalation
            if trigger.trigger_type == "fraud_anomaly" and twin.persona == "shell_circular":
                await self._audit.log(
                    user_id, "intervention_sent",
                    {"action": "human_escalation", "trigger": trigger.trigger_type},
                    consent_status=consent,
                )
                continue

            relevance = compute_relevance_score(
                trigger,
                personalization=0.7,  # could be personalised per user in prod
                acceptance_history=acceptance,
                safety_factor=1.0,
            )

            sent_ids = await self._notif_svc.dispatch(  # type: ignore[union-attr]
                user_id, trigger,
                consent=consent,
                relevance_score=relevance,
                relevance_threshold=_RELEVANCE_THRESHOLD,
            )

            if sent_ids:
                await self._audit.log(
                    user_id, "notification_sent",
                    {
                        "trigger_type": trigger.trigger_type,
                        "relevance_score": round(relevance, 3),
                        "channels": trigger.channels,
                        "notification_ids": sent_ids,
                    },
                    consent_status=consent,
                )

    # ── scheduled EOD report ──────────────────────────────────────────────────

    async def send_daily_report(self, user_id: str) -> dict | None:
        """
        Generate and dispatch an end-of-day report for a user.
        Called by a scheduler (cron / APScheduler) at EOD.
        """
        assert self._twin_svc is not None
        assert self._notif_svc is not None
        assert self._audit is not None

        twin = await self._twin_svc.get(user_id)
        if twin is None:
            return None

        consent = _get_consent(user_id)
        if not consent:
            return None

        report = generate_report(twin, report_type="daily_summary")

        # Log report generation
        await self._audit.log(
            user_id, "report_generated",
            {"report_type": "daily_summary", "cibil_score": report["cibil_like_score"]},
            consent_status=consent,
        )

        # Simulate WhatsApp delivery (LOW priority channel)
        from src.intervention.trigger_engine import TriggerResult
        report_trigger = TriggerResult(
            trigger_type="savings_opportunity",
            fired=True,
            priority="LOW",
            channels=["whatsapp"],
            urgency=0.3,
            reason="Daily report",
        )
        await self._notif_svc.dispatch(
            user_id, report_trigger,
            consent=consent,
            relevance_score=0.80,  # reports always delivered if consented
        )

        return report


# ── standalone entry point ────────────────────────────────────────────────────

async def _main() -> None:
    import os
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    agent = InterventionAgent(redis_url)
    try:
        await agent.start()
    except KeyboardInterrupt:
        await agent.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())
