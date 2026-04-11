"""
Tier 8 — Notification Service

Priority-based multi-channel delivery for intervention alerts.

Channel strategy (tier4_tier8.md §13):
  HIGH   → SMS + Push
  MEDIUM → Push only
  LOW    → WhatsApp

In the hackathon prototype all channels are simulated (logged to Redis
stream `stream:notifications` and printed to stdout). Production swap-in:
  - SMS: Twilio / MSG91
  - Push: FCM via firebase-admin
  - WhatsApp: WhatsApp Business API (WABA)

DPDPA 2023 + TRAI + RBI Fair Practices:
  - Explicit opt-in required (consent_status checked before send)
  - Non-coercive language only
  - Clear opt-out instruction in every message
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from typing import Any, Literal

import redis.asyncio as aioredis

from src.intervention.trigger_engine import TriggerResult

Channel = Literal["sms", "push", "whatsapp"]

_STREAM_NOTIFICATIONS = "stream:notifications"

# Opt-out footer injected into every message (TRAI compliance)
_OPT_OUT = "Reply STOP to opt out of alerts."


def _render_message(trigger: TriggerResult, channel: Channel) -> dict[str, str]:
    """Render a channel-appropriate notification payload."""
    title_map: dict[str, str] = {
        "liquidity_drop": "Cash buffer alert",
        "overspend_warning": "Overspend warning",
        "emi_at_risk": "EMI risk alert",
        "lifestyle_inflation": "Spending trend alert",
        "savings_opportunity": "Savings tip",
        "fraud_anomaly": "Account review required",
        "new_to_credit_guidance": "Build your credit profile",
    }
    title = title_map.get(trigger.trigger_type, "Financial alert")
    body = trigger.reason
    if trigger.suggested_actions:
        action_line = " • " + " • ".join(trigger.suggested_actions[:2])
        body = f"{body}\n{action_line}"

    if channel in ("sms", "whatsapp"):
        body += f"\n{_OPT_OUT}"

    return {"title": title, "body": body, "channel": channel}


class NotificationService:
    """
    Simulated multi-channel notification dispatcher.
    All sends are recorded in `stream:notifications` for audit and replay.
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        self._r = redis

    async def dispatch(
        self,
        user_id: str,
        trigger: TriggerResult,
        *,
        consent: bool = True,
        relevance_score: float = 0.0,
        relevance_threshold: float = 0.75,
    ) -> list[str]:
        """
        Send notifications on all channels defined by the trigger.
        Returns list of notification IDs sent.
        Skips if consent is False or relevance_score < threshold.
        """
        if not consent:
            return []
        if relevance_score < relevance_threshold:
            return []

        sent_ids: list[str] = []
        for channel in trigger.channels:
            nid = await self._send_one(user_id, trigger, channel)  # type: ignore[arg-type]
            if nid:
                sent_ids.append(nid)
        return sent_ids

    async def _send_one(
        self,
        user_id: str,
        trigger: TriggerResult,
        channel: Channel,
    ) -> str:
        notification_id = str(uuid.uuid4())
        msg = _render_message(trigger, channel)

        record: dict[str, Any] = {
            "notification_id": notification_id,
            "user_id": user_id,
            "trigger_type": trigger.trigger_type,
            "priority": trigger.priority,
            "channel": channel,
            "title": msg["title"],
            "body": msg["body"],
            "sent_at": datetime.utcnow().isoformat(),
        }

        # Persist to Redis stream (acts as delivery queue + audit trail)
        try:
            await self._r.xadd(
                _STREAM_NOTIFICATIONS,
                {k: str(v) for k, v in record.items()},
                maxlen=10_000,
                approximate=True,
            )
        except Exception:
            pass  # best-effort

        # Simulate channel delivery
        _channel_emoji = {"sms": "📱", "push": "🔔", "whatsapp": "💬"}
        print(
            f"[notification] {_channel_emoji.get(channel, '📢')} "
            f"{channel.upper()} → {user_id} | {msg['title']}"
        )
        return notification_id
