#!/usr/bin/env bash
set -euo pipefail

# Load .env from project root if present
if [ -f ".env" ]; then
  echo "[env] Loading .env from project root"
  set -a
  . ./.env
  set +a
fi

# Salon-specific environment defaults
export SALON_ANALYTICS_PORT=${SALON_ANALYTICS_PORT:-5002}
export SALON_PHONE_PORT=${SALON_PHONE_PORT:-5001}
export SALON_FRONTEND_PORT=${SALON_FRONTEND_PORT:-3000}

# Frontend public env
export NEXT_PUBLIC_SALON_API_URL=${NEXT_PUBLIC_SALON_API_URL:-http://localhost:5002}
export NEXT_PUBLIC_PHONE_API_URL=${NEXT_PUBLIC_PHONE_API_URL:-http://localhost:5001}
export SALON_SERVICE_URL=${SALON_SERVICE_URL:-http://localhost:5002}

# ConversationRelay + CI environment variables (required for new service)
export CI_SERVICE_SID=${CI_SERVICE_SID:-""}
export PUBLIC_BASE_URL=${PUBLIC_BASE_URL:-"https://your-ngrok-url.ngrok.io"}
export WSS_PUBLIC_URL=${WSS_PUBLIC_URL:-"wss://your-ngrok-url.ngrok.io"}
export ELEVENLABS_VOICE_ID=${ELEVENLABS_VOICE_ID:-"kdmDKE6EkgrWrrykO9Qt"}

# Pretty log helper
log() { echo -e "\033[1;36m[$(date +%H:%M:%S)]\033[0m $*"; }

# Free up ports
free_port() {
  local port="$1"
  local pids
  pids=$(lsof -ti tcp:"${port}" 2>/dev/null || true)
  if [ -n "${pids}" ]; then
    log "Freeing port :${port} (PIDs: ${pids})"
    kill -TERM ${pids} 2>/dev/null || true
    sleep 0.5
    kill -KILL ${pids} 2>/dev/null || true
  fi
}

free_port ${SALON_ANALYTICS_PORT}
free_port ${SALON_PHONE_PORT}
free_port ${SALON_FRONTEND_PORT}

# Check virtual environment
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  log "Activating virtual environment..."
  source .venv/bin/activate
fi

# Start Salon Analytics Service
log "Starting Salon Analytics Service on :${SALON_ANALYTICS_PORT}"
python3 scripts/start_salon_analytics.py --port ${SALON_ANALYTICS_PORT} --reload &
PID_ANALYTICS=$!

# Start Salon Phone Service
log "Starting Salon Phone Service on :${SALON_PHONE_PORT}"
python3 scripts/start_salon_phone.py --port ${SALON_PHONE_PORT} --reload &
PID_PHONE=$!

# Start Next.js Frontend
log "Starting Next.js Salon Frontend on :${SALON_FRONTEND_PORT}"
(
  cd frontend
  npm run dev -- -p ${SALON_FRONTEND_PORT}
) &
PID_FRONTEND=$!

# Wait for services to start
sleep 2

# Show service status
log "Salon Services Status:"
log "  🖥️  Next.js Dashboard: http://localhost:${SALON_FRONTEND_PORT}/dashboard"
log "  💇‍♀️ Salon Dashboard API: http://localhost:${SALON_FRONTEND_PORT}/api/salon-dashboard"
log "  📊 Analytics Service: http://localhost:${SALON_ANALYTICS_PORT}/salon/dashboard"
log "  📞 Phone API: http://localhost:${SALON_PHONE_PORT}/health"
log "  🔄 ConversationRelay: wss://localhost:${SALON_PHONE_PORT}/cr"
log "  📝 CI Transcripts: http://localhost:${SALON_PHONE_PORT}/intelligence/transcripts"
log "  💇‍♀️ Services: http://localhost:${SALON_PHONE_PORT}/salon/services"

# Graceful shutdown
cleanup() {
  log "Shutting down salon services..."
  kill ${PID_ANALYTICS} ${PID_PHONE} ${PID_FRONTEND} 2>/dev/null || true
  wait ${PID_ANALYTICS} ${PID_PHONE} ${PID_FRONTEND} 2>/dev/null || true
  log "Salon services stopped"
}
trap cleanup INT TERM

# Keep running until all exit
wait
