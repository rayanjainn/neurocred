#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Export variables from .env for API/worker runtime (Twilio, Groq, Redis, etc.).
if [ -f .env ]; then
	set -a
	. ./.env
	set +a
fi

uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload &
API_PID=$!

echo "Starting async scoring worker..."
python -m src.credit.scoring_worker &
WORKER_PID=$!

sleep 3 # wait for server to start
curl -s -X POST http://127.0.0.1:8001/twin/bootstrap > /dev/null

wait $API_PID $WORKER_PID
