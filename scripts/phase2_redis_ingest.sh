#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
/Users/rayanjain/miniconda3/envs/credit-scoring/bin/python -m src.ingestion.redis_producer "$@"
