#!/usr/bin/env bash
# Start the Airavat FastAPI server (port 8001)
set -euo pipefail
cd "$(dirname "$0")/.."

# Export .env so runtime os.getenv picks up Twilio/Groq config.
if [ -f .env ]; then
	set -a
	. ./.env
	set +a
fi

uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload
