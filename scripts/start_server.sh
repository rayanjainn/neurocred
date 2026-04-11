#!/usr/bin/env bash
# Start the Airavat FastAPI server (port 8001)
set -euo pipefail
cd "$(dirname "$0")/.."
uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload
