#!/usr/bin/env bash
# Phase 4 — train XGBoost scorer to data/models/
# Skips automatically if model already exists.
# Pass --force to retrain.
set -euo pipefail
cd "$(dirname "$0")/.."
/Users/rayanjain/miniconda3/envs/credit-scoring/bin/python -m src.scoring.trainer "$@"
