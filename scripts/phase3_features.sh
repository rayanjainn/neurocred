#!/usr/bin/env bash
# Phase 3 — compute behavioural features to data/features/
# Skips automatically if feature partitions already exist.
# Pass --force to recompute.
set -euo pipefail
cd "$(dirname "$0")/.."
/Users/rayanjain/miniconda3/envs/credit-scoring/bin/python -m src.features.engine batch "$@"
