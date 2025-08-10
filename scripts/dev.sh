#!/usr/bin/env bash
set -euo pipefail

# Load .env from project root if present (export all variables)
if [ -f ".env" ]; then
  echo "[env] Loading .env from project root"
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

# Defaults (override by exporting before running)
export APP_BASE_URL=${APP_BASE_URL:-http://localhost:8000}
export FRONTEND_ORIGIN=${FRONTEND_ORIGIN:-http://localhost:3000}
export JWT_SECRET=${JWT_SECRET:-devsecret}
export JWT_TTL_MINUTES=${JWT_TTL_MINUTES:-10}
export REDIS_URL=${REDIS_URL:-redis://localhost:6379/0}
export ADMIN_API_KEY=${ADMIN_API_KEY:-opkey}

export MAGICLINK_API_BASE=${MAGICLINK_API_BASE:-http://localhost:8000}
export MAGICLINK_APP_URL=${MAGICLINK_APP_URL:-http://localhost:3000/location}
export MAGICLINK_ADMIN_API_KEY=${MAGICLINK_ADMIN_API_KEY:-$ADMIN_API_KEY}
# Optional Twilio SMS envs
export TWILIO_ACCOUNT_SID=${TWILIO_ACCOUNT_SID:-}
export TWILIO_AUTH_TOKEN=${TWILIO_AUTH_TOKEN:-}
export TWILIO_SMS_FROM=${TWILIO_SMS_FROM:-}
# Dispatcher phone number for human transfer
export DISPATCH_NUMBER=${DISPATCH_NUMBER:-+14693096560}

# Frontend public env
export NEXT_PUBLIC_MAGICLINK_API_URL=${NEXT_PUBLIC_MAGICLINK_API_URL:-http://localhost:8000}
export NEXT_PUBLIC_PHONE_API_URL=${NEXT_PUBLIC_PHONE_API_URL:-http://localhost:5001}

# Pretty log helper
log() { echo -e "\033[1;36m[$(date +%H:%M:%S)]\033[0m $*"; }

# Free up commonly used dev ports to avoid EADDRINUSE
free_port() {
  local port="$1"
  # Find PIDs listening on the port; ignore errors if none
  local pids
  pids=$(lsof -ti tcp:"${port}" 2>/dev/null || true)
  if [ -n "${pids}" ]; then
    log "Freeing port :${port} (PIDs: ${pids})"
    # Try graceful then forceful kill
    kill -TERM ${pids} 2>/dev/null || true
    sleep 0.5
    # If still alive, force kill
    kill -KILL ${pids} 2>/dev/null || true
  fi
}

free_port 8000
free_port 5001
free_port 3000

# Start services
log "Starting Magiclink API on :8000"
uvicorn Magiclink.magic:app --host 0.0.0.0 --port 8000 --reload &
PID_MAGIC=$!

log "Starting Phone API on :5001"
python3 -m uvicorn ops_integrations.adapters.phone:app --host 0.0.0.0 --port 5001 --reload &
PID_PHONE=$!

log "Starting Next.js dev on :3000"
(
  cd frontend
  npm run dev
) &
PID_WEB=$!

# Graceful shutdown
cleanup() {
  log "Shutting down..."
  kill ${PID_MAGIC} ${PID_PHONE} ${PID_WEB} 2>/dev/null || true
  wait ${PID_MAGIC} ${PID_PHONE} ${PID_WEB} 2>/dev/null || true
}
trap cleanup INT TERM

# Keep running until all exit
wait 