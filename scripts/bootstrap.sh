#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────────────
# airavat — full bootstrap (Tiers 1 → 3)
#
# Usage:
#   cd airavat
#   bash scripts/bootstrap.sh
#
# Requirements:
#   - Python 3.11+
#   - Redis server running on localhost:6379
#   - pip / uv available
# ────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
cd "$ROOT"

echo "═══════════════════════════════════════════════"
echo " Airavat Digital Twin Bootstrap"
echo "═══════════════════════════════════════════════"

# ── 1. Install dependencies ───────────────────────────────────────────────────
echo ""
echo "► Step 1: Installing Python dependencies"
if command -v uv &>/dev/null; then
    uv pip install -e ".[dev]"
else
    pip install -e ".[dev]"
fi

# ── 2. Check Redis ────────────────────────────────────────────────────────────
echo ""
echo "► Step 2: Checking Redis connection"
python - <<'EOF'
import redis
r = redis.Redis()
r.ping()
print("  Redis OK")
EOF

# ── 3. Download MiniLM model (sentence-transformers caches automatically) ─────
echo ""
echo "► Step 3: Warming up MiniLM model (downloads if not cached)"
python - <<'EOF'
import sys
sys.path.insert(0, ".")
from src.classifier.merchant_classifier import warmup
warmup()
print("  MiniLM ready")
EOF

# ── 4. Create data directories ────────────────────────────────────────────────
echo ""
echo "► Step 4: Creating data directories"
mkdir -p data/raw data/features data/models

# ── 5. Tier 1 — Generate synthetic data + push to Redis ───────────────────────
echo ""
echo "► Step 5: Tier 1 — Generating synthetic data (50 profiles × 12 months)"
python - <<'EOF'
import asyncio, sys
sys.path.insert(0, ".")
from src.ingestion.redis_producer import produce
asyncio.run(produce(n_profiles=50, history_months=12))
EOF

# ── 6. Tier 2 — Process typed events (offline batch mode) ─────────────────────
echo ""
echo "► Step 6: Tier 2 — Classifying events from raw ingestion stream"
python - <<'EOF'
import asyncio, sys
sys.path.insert(0, ".")
from src.classifier.event_processor import EventProcessor, STREAM_IN, GROUP
import redis.asyncio as aioredis
from config.settings import settings

async def run_once():
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await client.xgroup_create(STREAM_IN, GROUP, id="0", mkstream=True)
    except Exception:
        pass
    processor = EventProcessor(client)
    total = 0
    while True:
        result = await client.xreadgroup(
            GROUP, "bootstrap-worker",
            {STREAM_IN: ">"},
            count=500, block=1000,
        )
        if not result:
            break
        for _stream, messages in result:
            n = await processor.process_batch(messages)
            total += n
            ids = [m[0] for m in messages]
            if ids:
                await client.xack(STREAM_IN, GROUP, *ids)
    print(f"  Classified {total} events")
    await client.aclose()

asyncio.run(run_once())
EOF

# ── 7. Tier 3 — Extract behavioural features ──────────────────────────────────
echo ""
echo "► Step 7: Tier 3 — Computing behavioural features"
python - <<'EOF'
import asyncio, sys
sys.path.insert(0, ".")
from src.features.engine import FeatureEngine, STREAM_IN as FE_STREAM, GROUP as FE_GROUP, cohort_registry
import redis.asyncio as aioredis
from config.settings import settings

async def run_once():
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await client.xgroup_create(FE_STREAM, FE_GROUP, id="0", mkstream=True)
    except Exception:
        pass
    cohort_registry.load()
    engine = FeatureEngine(client)
    total = 0
    while True:
        result = await client.xreadgroup(
            FE_GROUP, "bootstrap-worker",
            {FE_STREAM: ">"},
            count=500, block=1000,
        )
        if not result:
            break
        for _stream, messages in result:
            n = await engine.process_batch(messages)
            total += n
            ids = [m[0] for m in messages]
            if ids:
                await client.xack(FE_STREAM, FE_GROUP, *ids)
    print(f"  Computed features from {total} typed events")
    await client.aclose()

asyncio.run(run_once())
EOF

# ── 8. Build peer cohorts ─────────────────────────────────────────────────────
echo ""
echo "► Step 8: Building peer cohort benchmarks"
python -m src.features.peer_cohort

# ── 9. Start API ──────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════"
echo " Bootstrap complete!"
echo ""
echo " Start the API server:"
echo "   uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload"
echo ""
echo " Or run long-lived workers in separate terminals:"
echo "   python -m src.ingestion.redis_producer   # Tier 1"
echo "   python -m src.classifier.event_processor # Tier 2"
echo "   python -m src.features.engine            # Tier 3"
echo "═══════════════════════════════════════════════"
