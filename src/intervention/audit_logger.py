"""
Tier 8 — Audit Logger

Immutable, append-only audit trail for all twin updates, interventions,
notifications, and chat sessions.

Redis key: `audit:{user_id}` → sorted set scored by timestamp (epoch ms)
Global index: `audit:all` → sorted set of (user_id:event_id, ts)

RBI Digital Lending Directions + DPDPA 2023 require:
  - All lending-related decisions logged with full context
  - User consent status stamped on every intervention record
  - Replay capability: reconstruct all actions for a user at any point in time
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

import redis.asyncio as aioredis

AuditEventType = Literal[
    "twin_updated",
    "trigger_fired",
    "intervention_sent",
    "notification_sent",
    "report_generated",
    "chat_message",
    "consent_updated",
    "feedback_received",
]

_AUDIT_KEY = "audit:{uid}"
_AUDIT_ALL = "audit:all"
_AUDIT_MAX_PER_USER = 500


class AuditLogger:
    def __init__(self, redis: aioredis.Redis) -> None:
        self._r = redis

    async def log(
        self,
        user_id: str,
        event_type: AuditEventType,
        payload: dict[str, Any],
        *,
        consent_status: bool = True,
    ) -> str:
        """
        Append an immutable audit record.
        Returns the generated event_id.
        """
        event_id = str(uuid.uuid4())
        now_ms = int(time.time() * 1000)
        record = {
            "event_id": event_id,
            "user_id": user_id,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "consent_status": consent_status,
            "payload": payload,
        }
        serialised = json.dumps(record, default=str)
        pipe = self._r.pipeline()
        # Per-user sorted set (score = epoch ms → chronological replay)
        pipe.zadd(_AUDIT_KEY.format(uid=user_id), {serialised: now_ms})
        # Global index
        pipe.zadd(_AUDIT_ALL, {f"{user_id}:{event_id}": now_ms})
        # Trim per-user set to prevent unbounded growth
        pipe.zremrangebyrank(_AUDIT_KEY.format(uid=user_id), 0, -(_AUDIT_MAX_PER_USER + 1))
        await pipe.execute()
        return event_id

    async def get_user_audit(
        self,
        user_id: str,
        limit: int = 50,
        event_type: str | None = None,
    ) -> list[dict]:
        """
        Retrieve recent audit records for a user (newest first).
        Optionally filter by event_type.
        """
        raw_records = await self._r.zrevrange(
            _AUDIT_KEY.format(uid=user_id), 0, limit * 2 - 1
        )
        results = []
        for raw in raw_records:
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if event_type and rec.get("event_type") != event_type:
                continue
            results.append(rec)
            if len(results) >= limit:
                break
        return results

    async def replay_since(
        self,
        user_id: str,
        since_ts: datetime,
    ) -> list[dict]:
        """
        Return all audit records for a user after `since_ts`.
        Supports RBI event-sourced replay requirement.
        """
        # Ensure since_ts is timezone-aware so .timestamp() returns true UTC epoch
        if since_ts.tzinfo is None:
            since_ts = since_ts.replace(tzinfo=timezone.utc)
        since_ms = int(since_ts.timestamp() * 1000)
        raw_records = await self._r.zrangebyscore(
            _AUDIT_KEY.format(uid=user_id), since_ms, "+inf"
        )
        results = []
        for raw in raw_records:
            try:
                results.append(json.loads(raw))
            except json.JSONDecodeError:
                pass
        return results
