#!/usr/bin/env bash
# Online pipeline: start Redis → generate → ingest → features → train → tests → API
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Cleaning Up Ports (8001, 3000) ==="
lsof -ti :8001,3000 | xargs kill -9 2>/dev/null || true

echo "=== Starting Redis ==="
redis-server --daemonize yes --logfile /tmp/airavat-redis.log

echo "=== Phase 1: Generate synthetic data ==="
bash "$SCRIPT_DIR/phase1_generate.sh" "$@"

echo "=== Phase 2: Ingest to Redis Streams ==="
bash "$SCRIPT_DIR/phase2_redis_ingest.sh" "$@"

echo "=== Phase 3: Compute behavioural features ==="
bash "$SCRIPT_DIR/phase3_features.sh"

echo "=== Phase 4: Train XGBoost digital-twin scorer ==="
bash "$SCRIPT_DIR/phase4_train.sh"

echo "=== Phase 5: Run tests ==="
bash "$SCRIPT_DIR/phase5_tests.sh"

echo "=== Phase 6: Start API server (Background) ==="
bash "$SCRIPT_DIR/phase6_api.sh" &
API_PID=$!
echo "API Server started with PID: $API_PID"

echo "=== Phase 7: Start Frontend ==="
bash "$SCRIPT_DIR/phase7_frontend.sh"

# Wait for background processes
wait $API_PID
