"""
Tier 4 — Twin Store

Handles Redis persistence for Digital Twins:
  - GET  current twin state  →  `twin:{user_id}`
  - SET  current twin state
  - LPUSH immutable snapshots → `twin:{user_id}:history`
    - XADD timeline events      → `stream:twin_timeline`
  - Reconstruct twin at any historical timestamp
"""

from __future__ import annotations

import json
import os
import logging
from datetime import datetime
from typing import Optional

import redis.asyncio as aioredis
from pydantic import ValidationError

from src.twin.twin_model import DigitalTwin

_TWIN_KEY = "twin:{uid}"
_HIST_KEY = "twin:{uid}:history"
_HIST_MAX = int(os.getenv("TWIN_HISTORY_MAX", "0"))  # 0 = unbounded history
_TIMELINE_STREAM_KEY = os.getenv("TWIN_TIMELINE_STREAM_KEY", "stream:twin_timeline")
_TIMELINE_STREAM_MAXLEN = int(os.getenv("TWIN_TIMELINE_STREAM_MAXLEN", "200000"))


class TwinStore:
    def __init__(self, redis: aioredis.Redis) -> None:
        self._r = redis

    async def _append_timeline_event(self, twin: DigitalTwin, payload: str) -> None:
        """Best-effort append of snapshot metadata to a Redis stream timeline."""
        fields = {
            "entity": "digital_twin",
            "user_id": twin.user_id,
            "version": str(twin.version),
            "risk_score": f"{twin.risk_score:.6f}",
            "liquidity_health": str(twin.liquidity_health),
            "ts": twin.last_updated.isoformat(),
            "snapshot": payload,
        }
        try:
            if _TIMELINE_STREAM_MAXLEN > 0:
                await self._r.xadd(
                    _TIMELINE_STREAM_KEY,
                    fields,
                    maxlen=_TIMELINE_STREAM_MAXLEN,
                    approximate=True,
                )
            else:
                await self._r.xadd(_TIMELINE_STREAM_KEY, fields)
        except Exception:
            # Timeline stream is supplementary; primary twin persistence must not fail.
            pass

    # ── read ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _coerce_hash_payload(payload: dict[str, str]) -> dict:
        parsed: dict = {}
        for key, value in payload.items():
            raw = (value or "").strip()
            if raw == "":
                parsed[key] = ""
                continue
            if raw.lower() in {"true", "false"}:
                parsed[key] = raw.lower() == "true"
                continue
            try:
                parsed[key] = json.loads(raw)
                continue
            except json.JSONDecodeError:
                pass
            try:
                if raw.isdigit() or (raw.startswith("-") and raw[1:].isdigit()):
                    parsed[key] = int(raw)
                else:
                    parsed[key] = float(raw)
            except (TypeError, ValueError):
                parsed[key] = value
        return parsed

    async def _recover_from_hash(self, user_id: str) -> Optional[DigitalTwin]:
        key = _TWIN_KEY.format(uid=user_id)
        try:
            hash_payload = await self._r.hgetall(key)
        except Exception:
            hash_payload = {}
        if not hash_payload:
            return None

        payload = self._coerce_hash_payload(hash_payload)
        payload.setdefault("user_id", user_id)
        try:
            twin = DigitalTwin.model_validate(payload)
        except ValidationError:
            return None

        # Normalize recovered shape into canonical JSON twin record.
        await self._r.set(key, twin.model_dump_json())
        return twin

    async def get(self, user_id: str) -> Optional[DigitalTwin]:
        key = _TWIN_KEY.format(uid=user_id)
        try:
            raw = await self._r.get(key)
        except Exception as exc:
            if "WRONGTYPE" in str(exc):
                logging.getLogger(__name__).warning(
                    "[twin-store] WRONGTYPE on twin:%s — attempting hash recovery", user_id
                )
                recovered = await self._recover_from_hash(user_id)
                if recovered is not None:
                    return recovered
                # Unrecoverable stale key.
                try:
                    await self._r.delete(key)
                except Exception:
                    pass
                return None
            raise
        if not raw:
            return None

        try:
            return DigitalTwin.model_validate_json(raw)
        except ValidationError:
            # Legacy records may miss required fields like user_id.
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                return None
            if not isinstance(payload, dict):
                return None

            payload.setdefault("user_id", user_id)
            try:
                twin = DigitalTwin.model_validate(payload)
            except ValidationError:
                return None

            # Heal storage in-place to avoid repeated recovery path.
            await self._r.set(key, twin.model_dump_json())
            return twin

    async def get_history(self, user_id: str, limit: int = 20) -> list[dict]:
        """Return up to `limit` historical snapshots (newest first)."""
        raws = await self._r.lrange(_HIST_KEY.format(uid=user_id), 0, limit - 1)
        results = []
        for r in raws:
            try:
                results.append(json.loads(r))
            except json.JSONDecodeError:
                pass
        return results

    async def reconstruct_at(
        self, user_id: str, target_ts: datetime
    ) -> Optional[dict]:
        """
        Return the twin snapshot whose timestamp is closest to (and ≤) target_ts.
        Returns raw dict (not DigitalTwin) to avoid stale model mismatches.
        """
        all_snaps = await self._r.lrange(_HIST_KEY.format(uid=user_id), 0, -1)
        best: Optional[dict] = None
        best_dt: Optional[datetime] = None
        for raw in all_snaps:
            try:
                snap = json.loads(raw)
            except json.JSONDecodeError:
                continue
            try:
                snap_ts = datetime.fromisoformat(snap.get("last_updated", ""))
            except ValueError:
                continue
            if snap_ts <= target_ts:
                if best_dt is None or snap_ts > best_dt:
                    best = snap
                    best_dt = snap_ts
        return best

    # ── write ─────────────────────────────────────────────────────────────────

    async def save(self, twin: DigitalTwin, *, append_history: bool = True) -> None:
        """Persist current state and optionally push snapshot to history."""
        payload = twin.model_dump_json()
        pipe = self._r.pipeline()
        pipe.set(_TWIN_KEY.format(uid=twin.user_id), payload)
        if append_history:
            pipe.lpush(_HIST_KEY.format(uid=twin.user_id), payload)
            if _HIST_MAX > 0:
                pipe.ltrim(_HIST_KEY.format(uid=twin.user_id), 0, _HIST_MAX - 1)
        await pipe.execute()
        if append_history:
            await self._append_timeline_event(twin, payload)

    async def delete(self, user_id: str) -> None:
        pipe = self._r.pipeline()
        pipe.delete(_TWIN_KEY.format(uid=user_id))
        pipe.delete(_HIST_KEY.format(uid=user_id))
        await pipe.execute()

    # ── bulk helpers (offline bootstrap) ─────────────────────────────────────

    async def bulk_save(self, twins: list[DigitalTwin]) -> int:
        """
        Write many twins in pipelined batches. Returns count saved.
        """
        BATCH = 100
        saved = 0
        for i in range(0, len(twins), BATCH):
            batch = twins[i : i + BATCH]
            pipe = self._r.pipeline()
            payloads: list[tuple[DigitalTwin, str]] = []
            for twin in batch:
                payload = twin.model_dump_json()
                pipe.set(_TWIN_KEY.format(uid=twin.user_id), payload)
                pipe.lpush(_HIST_KEY.format(uid=twin.user_id), payload)
                if _HIST_MAX > 0:
                    pipe.ltrim(_HIST_KEY.format(uid=twin.user_id), 0, _HIST_MAX - 1)
                payloads.append((twin, payload))
            await pipe.execute()
            for twin, payload in payloads:
                await self._append_timeline_event(twin, payload)
            saved += len(batch)
        return saved
