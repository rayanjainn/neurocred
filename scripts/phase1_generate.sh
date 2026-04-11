#!/usr/bin/env bash
# Phase 1 — generate synthetic data to data/raw/
# Skips automatically if data/raw/user_profiles.parquet already exists.
# Pass --force to wipe and regenerate.
set -euo pipefail
cd "$(dirname "$0")/.."
/Users/rayanjain/miniconda3/envs/credit-scoring/bin/python -m src.ingestion.generator "$@"
