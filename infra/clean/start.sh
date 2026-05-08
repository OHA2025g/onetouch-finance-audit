#!/bin/sh
set -eu

# Default envs for local/demo usage
export MONGO_URL="${MONGO_URL:-mongodb://mongo:27017}"
export DB_NAME="${DB_NAME:-onetouch_audit}"
export CORS_ORIGINS="${CORS_ORIGINS:-*}"
export ENABLE_PHASE2="${ENABLE_PHASE2:-true}"

# Start API (loopback only; nginx proxies it)
uvicorn server:app --host 127.0.0.1 --port 8000 &

# Start nginx in foreground
nginx -g 'daemon off;'

