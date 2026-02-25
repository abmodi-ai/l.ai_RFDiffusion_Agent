#!/usr/bin/env bash
# Start ngrok tunnel to expose the backend API on port 8000.
#
# Usage:
#   ./scripts/start-ngrok.sh              # ephemeral URL (changes each time)
#   ./scripts/start-ngrok.sh --domain my-subdomain.ngrok-free.app  # stable URL (requires ngrok plan)
#
# Prerequisites:
#   1. Install ngrok:  downloaded to ~/.local/bin/ngrok
#   2. Set auth token: ~/.local/bin/ngrok config add-authtoken YOUR_TOKEN
#
# The tunnel URL will be printed to stdout. Use it as VITE_API_BASE for the
# GCP-hosted frontend, e.g.:
#   VITE_API_BASE=https://abc123.ngrok-free.app/api npm run build

set -euo pipefail

NGROK="${HOME}/.local/bin/ngrok"
BACKEND_PORT="${BACKEND_PORT:-8000}"

if [[ ! -x "$NGROK" ]]; then
  echo "ERROR: ngrok not found at $NGROK"
  echo "Install with: curl -s https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm64.tgz | tar -xz -C ~/.local/bin/"
  exit 1
fi

echo "Starting ngrok tunnel to localhost:${BACKEND_PORT}..."
echo ""

# Pass any extra flags (e.g., --domain) to ngrok
exec "$NGROK" http "$BACKEND_PORT" "$@"
