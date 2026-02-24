#!/usr/bin/env bash
set -euo pipefail
if [ -z "${NGROK_AUTH_TOKEN:-}" ]; then
    echo "Error: NGROK_AUTH_TOKEN not set"
    exit 1
fi
ngrok http 8000 --authtoken "$NGROK_AUTH_TOKEN"
