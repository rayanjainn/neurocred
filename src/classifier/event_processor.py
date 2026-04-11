"""
Tier 2 — Financial Event Stream Processor

Consumes from stream:raw_ingestion (written by Tier 1 producer),
enriches each event with:
  - merchant_category (via MiniLM semantic classifier)
  - transaction_type  (INCOME / EXPENSE_ESSENTIAL / EMI_PAYMENT / etc.)
  - recurrence_flag   (from source_provenance == emi_statement)
  - anomaly_flag      (rule-based: failed status + amount > 2σ)

Sliding-window aggregator: maintains per-user in-memory windows
(7d / 30d / 90d) updated on every event.  Aggregates are stored in
Redis as JSON hashes under key  twin:windows:<user_id>.

Output: enriched CanonicalEvent pushed to stream:typed_events (→ Tier 3).

Worker runs as a Redis Stream consumer group member.
"""

from __future__ import annotations

import asyncio
import json
import statistics
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any

import redis.asyncio as aioredis

from config.settings import settings
from src.classifier.merchant_classifier import classify_merchant, warmup
from src.ingestion.schemas import CanonicalEvent

STREAM_IN = "stream:raw_ingestion"
STREAM_OUT = settings.stream_typed
GROUP = settings.cg_classifier
CONSUMER = "classifier-worker-0"
BLOCK_MS = 2000
BATCH_SIZE = 100


# ── sliding-window state ──────────────────────────────────────────────────────

class WindowBuffer:
    """
    Per-user deque of (timestamp, amount, category) tuples for 7/30/90d windows.
    Updated on every event; stale entries beyond 90d are pruned.
    """

    def __init__(self) -> None:
        self._buf: deque[tuple[datetime, float, str, str]] = deque()

    def push(self, ts: datetime, amount: float, category: str, txn_type: str) -> None:
        self._buf.append((ts, amount, category, txn_type))

    def _prune(self, ref: datetime, days: int = 90) -> None:
        cutoff = ref - timedelta(days=days)
        while self._buf and self._buf[0][0] < cutoff:
            self._buf.popleft()

    def aggregate(self, ref: datetime) -> dict[str, Any]:
        """
        Compute 7d / 30d / 90d summaries per math.md §B.
        Returns a dict pushed to Redis as twin:windows:<user_id>.
        """
        self._prune(ref, days=91)
        windows = {7: [], 30: [], 90: []}
        for ts, amt, cat, ttype in self._buf:
            age = (ref - ts).days
            for w in [7, 30, 90]:
                if age <= w:
                    windows[w].append((amt, cat, ttype))

        result: dict[str, Any] = {}
        for w, rows in windows.items():
            income = sum(a for a, c, t in rows if t == "INCOME")
            essential = sum(abs(a) for a, c, t in rows if t == "EXPENSE_ESSENTIAL")
            discretionary = sum(abs(a) for a, c, t in rows if t == "EXPENSE_DISCRETIONARY")
            emi = sum(abs(a) for a, c, t in rows if t == "EMI_PAYMENT")
            subscription = sum(abs(a) for a, c, t in rows if t == "SUBSCRIPTION")
            net = income - essential - discretionary - emi - subscription

            cat_totals: dict[str, float] = defaultdict(float)
            for amt, cat, _ in rows:
                cat_totals[cat] += abs(amt)

            result[f"{w}d_total_income"] = round(income, 2)
            result[f"{w}d_total_essential"] = round(essential, 2)
            result[f"{w}d_total_discretionary"] = round(discretionary, 2)
            result[f"{w}d_emi"] = round(emi, 2)
            result[f"{w}d_subscription"] = round(subscription, 2)
            result[f"{w}d_net_cashflow"] = round(net, 2)
            result[f"{w}d_event_count"] = len(rows)
            result[f"{w}d_category_breakdown"] = dict(cat_totals)

        return result


# ── anomaly flag ──────────────────────────────────────────────────────────────

class AnomalyDetector:
    """
    Lightweight rule-based anomaly detection per math.md §5.
    Flags an event if:
      - status == FAILED
      - amount > 3σ above recent mean (z-score)
      - velocity burst: >5 events in 60 minutes for same user
    """

    def __init__(self) -> None:
        self._recent_amounts: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=200))
        self._recent_times: dict[str, deque[datetime]] = defaultdict(lambda: deque(maxlen=50))

    def check(self, ev: CanonicalEvent) -> bool:
        uid = ev.user_id
        amt = abs(ev.amount)
        ts = ev.timestamp

        # rule 1: failed transaction
        if ev.status == "FAILED":
            return True

        # rule 2: z-score on amount
        amounts = list(self._recent_amounts[uid])
        if len(amounts) >= 10:
            mu = statistics.mean(amounts)
            sigma = statistics.stdev(amounts) or 1.0
            if (amt - mu) / sigma > 3.0:
                return True

        # rule 3: velocity burst (>5 events in 60 min)
        times = list(self._recent_times[uid])
        if times:
            one_hour_ago = ts - timedelta(hours=1)
            recent_count = sum(1 for t in times if t >= one_hour_ago)
            if recent_count > 5:
                return True

        self._recent_amounts[uid].append(amt)
        self._recent_times[uid].append(ts)
        return False


# ── event processor ───────────────────────────────────────────────────────────

class EventProcessor:
    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client
        self._windows: dict[str, WindowBuffer] = defaultdict(WindowBuffer)
        self._anomaly = AnomalyDetector()
        warmup()

    def _enrich(self, ev: CanonicalEvent) -> CanonicalEvent:
        """Classify merchant, set transaction_type, recurrence_flag, anomaly_flag."""
        category, txn_type, confidence = classify_merchant(
            ev.merchant_name, ev.amount
        )
        ev.merchant_category = category
        ev.transaction_type = txn_type
        ev.classifier_confidence = confidence
        ev.recurrence_flag = ev.source_provenance == "emi_statement"
        ev.anomaly_flag = self._anomaly.check(ev)

        # update window buffer
        self._windows[ev.user_id].push(ev.timestamp, ev.amount, category, txn_type)
        return ev

    async def _publish_typed(self, ev: CanonicalEvent) -> None:
        fields: dict[str, str] = {}
        for k, v in ev.model_dump().items():
            if v is None:
                fields[k] = ""
            elif isinstance(v, datetime):
                fields[k] = v.isoformat()
            elif isinstance(v, bool):
                fields[k] = "1" if v else "0"
            elif isinstance(v, float):
                fields[k] = str(round(v, 4))
            else:
                fields[k] = str(v)
        await self.redis.xadd(
            STREAM_OUT, fields,
            maxlen=settings.stream_maxlen, approximate=True
        )

    async def _store_windows(self, user_id: str, ts: datetime) -> None:
        agg = self._windows[user_id].aggregate(ts)
        # store as JSON under twin:windows:<user_id>
        await self.redis.set(
            f"twin:windows:{user_id}",
            json.dumps(agg),
        )

    async def process_batch(self, messages: list[tuple[str, dict[str, str]]]) -> int:
        """Enrich and re-publish a batch of raw messages."""
        count = 0
        for _msg_id, fields in messages:
            try:
                # reconstruct CanonicalEvent from Redis fields
                ev_data: dict[str, Any] = {}
                for k, v in fields.items():
                    if v == "":
                        ev_data[k] = None
                    elif k in ("timestamp",):
                        try:
                            ev_data[k] = datetime.fromisoformat(v)
                        except Exception:
                            ev_data[k] = v
                    elif k in ("amount", "balance_after", "classifier_confidence"):
                        try:
                            ev_data[k] = float(v) if v else None
                        except Exception:
                            ev_data[k] = None
                    elif k in ("recurrence_flag", "anomaly_flag"):
                        ev_data[k] = v == "1"
                    else:
                        ev_data[k] = v

                ev = CanonicalEvent.model_validate(ev_data)
                ev = self._enrich(ev)
                await self._publish_typed(ev)
                await self._store_windows(ev.user_id, ev.timestamp)
                count += 1
            except Exception as exc:
                print(f"[classifier] skip malformed message: {exc}")
        return count


async def run_classifier() -> None:
    """
    Long-running consumer that reads stream:raw_ingestion and
    publishes to stream:typed_events.
    """
    client = aioredis.from_url(settings.redis_url, decode_responses=True)

    # ensure group exists
    try:
        await client.xgroup_create(STREAM_IN, GROUP, id="0", mkstream=True)
    except aioredis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise

    processor = EventProcessor(client)
    total = 0
    print(f"[classifier] listening on {STREAM_IN} group={GROUP}")

    while True:
        result = await client.xreadgroup(
            GROUP, CONSUMER,
            {STREAM_IN: ">"},
            count=BATCH_SIZE,
            block=BLOCK_MS,
        )
        if not result:
            continue

        for _stream, messages in result:
            n = await processor.process_batch(messages)
            total += n
            if total % 1000 == 0:
                print(f"[classifier] processed {total:,} events")

            # acknowledge
            ids = [msg[0] for msg in messages]
            if ids:
                await client.xack(STREAM_IN, GROUP, *ids)


if __name__ == "__main__":
    asyncio.run(run_classifier())
