#!/usr/bin/env bash
# Offline pipeline: generate → features → train → tests
# Each phase skips automatically if outputs already exist.
# Pass --force to each phase script to override.
#
# Usage:
#   bash scripts/run_offline.sh           # uses cache where possible
#   bash scripts/run_offline.sh --force   # wipe all caches and rerun
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FORCE="${1:-}"

echo "=== Phase 1: Generate synthetic data ==="
bash "$SCRIPT_DIR/phase1_generate.sh" $FORCE

echo "=== Phase 3: Compute behavioural features ==="
bash "$SCRIPT_DIR/phase3_features.sh" $FORCE

echo "=== Phase 4: Train XGBoost digital-twin scorer ==="
bash "$SCRIPT_DIR/phase4_train.sh" $FORCE

echo "=== Phase 5: Run tests ==="
bash "$SCRIPT_DIR/phase5_tests.sh"

echo "=== Offline pipeline complete ==="
