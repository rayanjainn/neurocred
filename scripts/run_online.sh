#!/usr/bin/env bash
# Online pipeline: start Redis → generate → ingest → features → train → tests → API
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Starting Redis ==="
redis-server --daemonize yes --logfile /tmp/airavat-redis.log

echo "=== Phase 1: Generate synthetic data ==="
bash "$SCRIPT_DIR/phase1_generate.sh"

echo "=== Phase 2: Ingest to Redis Streams ==="
bash "$SCRIPT_DIR/phase2_redis_ingest.sh"

echo "=== Phase 3: Compute behavioural features ==="
bash "$SCRIPT_DIR/phase3_features.sh"

echo "=== Phase 4: Train XGBoost digital-twin scorer ==="
bash "$SCRIPT_DIR/phase4_train.sh"

echo "=== Phase 5: Run tests ==="
bash "$SCRIPT_DIR/phase5_tests.sh"

echo "=== Phase 6: Start API server ==="
bash "$SCRIPT_DIR/phase6_api.sh"
