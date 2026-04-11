#!/usr/bin/env bash
# Tier 5 — Liquid Glass Frontend
set -euo pipefail

cd "$(dirname "$0")/../frontend"

echo "=== Phase 7: Starting Frontend (Next.js) ==="

# Check if node_modules exists, otherwise install
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    pnpm install
fi

# Start Next.js in dev mode in the background
pnpm dev &
FRONTEND_PID=$!

echo "Frontend started on http://localhost:3000 (PID: $FRONTEND_PID)"

# Wait a bit to ensure it doesn't crash immediately
sleep 5
