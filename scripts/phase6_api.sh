#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload
