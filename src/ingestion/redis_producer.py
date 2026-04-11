"""
Tier 1 — Redis Streams Producer

Reads CanonicalEvents from the synthetic generator and publishes them
to the raw ingestion stream (stream:bank_transactions / upi / sms / etc.)

Each event is published to its source-specific stream AND to a unified
stream:raw_ingestion consumed by the Tier 2 classifier.

Idempotency: event_id is stored as the Redis field; XADD uses MAXLEN ~
to cap stream size while preserving recent history.

Late-arrival handling: events older than the stream's latest entry are
still published (Redis XADD "*" uses server-assigned IDs so ordering
is ingestion-time, not event-time — Tier 2 handles event-time windows).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

import redis.asyncio as aioredis

from config.settings import settings
from src.ingestion.generator import event_stream
from src.ingestion.schemas import CanonicalEvent

logger = logging.getLogger("airavat.producer")

STREAM_RAW = "stream:raw_ingestion"

PROVENANCE_TO_STREAM = {
    "bank_api": settings.stream_bank,
    "upi_api": settings.stream_upi,
    "sms_parser": settings.stream_sms,
    "emi_statement": settings.stream_emi,
    "open_banking_aa": settings.stream_ob,
    "voice_stt_parser": settings.stream_voice,
}

BATCH_SIZE = 50_000


def _serialise(ev: CanonicalEvent) -> dict[str, str]:
    """Convert CanonicalEvent to Redis-compatible flat string dict."""
    raw: dict[str, Any] = ev.model_dump()
    result: dict[str, str] = {}
    for k, v in raw.items():
        if v is None:
            result[k] = ""
        elif isinstance(v, datetime):
            result[k] = v.isoformat()
        elif isinstance(v, bool):
            result[k] = "1" if v else "0"
        elif isinstance(v, float):
            result[k] = str(round(v, 4))
        else:
            result[k] = str(v)
    return result


async def _ensure_groups(client: aioredis.Redis) -> None:
    streams = [STREAM_RAW] + list(PROVENANCE_TO_STREAM.values())
    for stream in streams:
        for group in [settings.cg_classifier, settings.cg_feature_engine]:
            try:
                await client.xgroup_create(stream, group, id="$", mkstream=True)
            except aioredis.ResponseError as exc:
                if "BUSYGROUP" not in str(exc):
                    raise


async def produce(
    n_profiles: int = 100,
    history_months: int = 12,
    verbose: bool = True,
    clear_existing: bool = False,
) -> int:
    """
    Generate synthetic events and publish to Redis Streams.
    Returns total events published.
    """
    client = aioredis.from_url(settings.redis_url, decode_responses=True)

    if clear_existing:
        logger.info(f"[producer] clearing stream {STREAM_RAW}")
        await client.delete(STREAM_RAW)
        for s in PROVENANCE_TO_STREAM.values():
            await client.delete(s)

    try:
        await client.ping()
    except Exception as exc:
        raise RuntimeError(f"Cannot connect to Redis at {settings.redis_url}: {exc}") from exc

    await _ensure_groups(client)

    total = 0
    batch_raw: list[dict[str, str]] = []
    batch_source: list[tuple[str, dict[str, str]]] = []

    for ev in event_stream(n_profiles, history_months):
        fields = _serialise(ev)
        batch_raw.append(fields)
        source_stream = PROVENANCE_TO_STREAM.get(ev.source_provenance, STREAM_RAW)
        batch_source.append((source_stream, fields))

        if len(batch_raw) >= BATCH_SIZE:
            pipe = client.pipeline(transaction=False)
            for f in batch_raw:
                pipe.xadd(STREAM_RAW, f, maxlen=settings.stream_maxlen, approximate=True)
            for stream, f in batch_source:
                pipe.xadd(stream, f, maxlen=settings.stream_maxlen, approximate=True)
            await pipe.execute()
            total += len(batch_raw)
            batch_raw.clear()
            batch_source.clear()
            if verbose:
                print(f"[producer] published {total:,} events")

    # flush remainder
    if batch_raw:
        pipe = client.pipeline(transaction=False)
        for f in batch_raw:
            pipe.xadd(STREAM_RAW, f, maxlen=settings.stream_maxlen, approximate=True)
        for stream, f in batch_source:
            pipe.xadd(stream, f, maxlen=settings.stream_maxlen, approximate=True)
        await pipe.execute()
        total += len(batch_raw)

    if verbose:
        print(f"[producer] done — {total:,} total events across {n_profiles} profiles")

    await client.aclose()
    return total


if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    asyncio.run(produce(clear_existing=force))
