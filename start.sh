#!/usr/bin/env bash
# Start Redis, Backend API, Celery worker, and Frontend from one terminal.
# Stop everything with Ctrl+C or Ctrl+Z.

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
VENV="$BACKEND/venv"
LOG_DIR="$ROOT/.run-logs"
PID_FILE="$LOG_DIR/pids"
REDIS_MODE=""          # docker | docker-sudo | local | existing
REDIS_LOCAL_PID=""
UVICORN_PID=""
CELERY_PID=""
FRONTEND_PID=""
CLEANED=0
STARTED_OK=0
STOP_REASON=""         # user | error

mkdir -p "$LOG_DIR"

red() { printf '\033[0;31m%s\033[0m\n' "$*"; }
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
blue() { printf '\033[0;34m%s\033[0m\n' "$*"; }

kill_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids="$(lsof -ti:"$port" 2>/dev/null || true)"
    if [[ -n "$pids" ]]; then
      # shellcheck disable=SC2086
      kill $pids 2>/dev/null || true
      sleep 0.3
      # shellcheck disable=SC2086
      kill -9 $pids 2>/dev/null || true
    fi
  elif command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" >/dev/null 2>&1 || true
  fi
}

kill_matching() {
  local pattern="$1"
  if command -v pkill >/dev/null 2>&1; then
    pkill -f "$pattern" 2>/dev/null || true
  fi
}

redis_ping() {
  if command -v redis-cli >/dev/null 2>&1; then
    redis-cli -h 127.0.0.1 -p 6379 ping 2>/dev/null | grep -qi PONG
    return $?
  fi
  # Fall back to TCP check
  if (echo >/dev/tcp/127.0.0.1/6379) >/dev/null 2>&1; then
    return 0
  fi
  if command -v nc >/dev/null 2>&1 && nc -z 127.0.0.1 6379 >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

docker_compose() {
  # Prefer docker compose; fall back to docker-compose binary
  if docker compose version >/dev/null 2>&1; then
    (cd "$BACKEND" && docker compose "$@")
    return $?
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    (cd "$BACKEND" && docker-compose "$@")
    return $?
  fi
  return 127
}

sudo_docker_compose() {
  if sudo -n true 2>/dev/null; then
    (cd "$BACKEND" && sudo docker compose "$@")
    return $?
  fi
  yellow "  Docker needs elevated access — you may be prompted for your password."
  (cd "$BACKEND" && sudo docker compose "$@")
  return $?
}

stop_existing() {
  yellow "Stopping any existing ForInsighter processes..."

  # Kill tracked PIDs from a previous run
  if [[ -f "$PID_FILE" ]]; then
    while read -r pid; do
      [[ -n "${pid:-}" ]] || continue
      kill "$pid" 2>/dev/null || true
      kill -9 "$pid" 2>/dev/null || true
    done <"$PID_FILE"
    rm -f "$PID_FILE"
  fi

  # Kill by process pattern (covers orphaned workers)
  kill_matching "uvicorn main:app"
  kill_matching "celery -A tasks.celery_tasks"
  kill_matching "vite"
  kill_matching "npm run dev"

  # Free app ports
  kill_port 8000
  kill_port 8080

  # Stop docker redis only if docker is usable without sudo
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    docker_compose stop >/dev/null 2>&1 || true
  fi

  # Stop local redis only if we started it previously (pid file)
  if [[ -f "$LOG_DIR/redis-local.pid" ]]; then
    local rpid
    rpid="$(cat "$LOG_DIR/redis-local.pid" 2>/dev/null || true)"
    if [[ -n "${rpid:-}" ]]; then
      kill "$rpid" 2>/dev/null || true
      kill -9 "$rpid" 2>/dev/null || true
    fi
    rm -f "$LOG_DIR/redis-local.pid"
  fi

  sleep 0.5
  green "  ✓ Previous processes cleared"
}

cleanup() {
  if [[ "$CLEANED" -eq 1 ]]; then
    return
  fi
  CLEANED=1
  echo

  for pid in "${FRONTEND_PID:-}" "${CELERY_PID:-}" "${UVICORN_PID:-}" "${REDIS_LOCAL_PID:-}"; do
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      kill -9 "$pid" 2>/dev/null || true
    fi
  done

  kill_matching "uvicorn main:app"
  kill_matching "celery -A tasks.celery_tasks"
  kill_matching "vite"
  kill_port 8000
  kill_port 8080

  case "${REDIS_MODE:-}" in
    docker)
      docker_compose stop >/dev/null 2>&1 || true
      ;;
    docker-sudo)
      sudo_docker_compose stop >/dev/null 2>&1 || true
      ;;
    local)
      if [[ -n "${REDIS_LOCAL_PID:-}" ]]; then
        kill "$REDIS_LOCAL_PID" 2>/dev/null || true
        kill -9 "$REDIS_LOCAL_PID" 2>/dev/null || true
      fi
      rm -f "$LOG_DIR/redis-local.pid"
      ;;
  esac

  rm -f "$PID_FILE"

  if [[ "$STOP_REASON" == "user" ]] || [[ "$STARTED_OK" -eq 1 ]]; then
    green "The website is stopped and all the processes"
  fi
}

on_user_stop() {
  STOP_REASON="user"
  cleanup
  exit 0
}

trap 'on_user_stop' INT TERM TSTP
trap 'cleanup' EXIT

wait_for_http() {
  local url="$1"
  local name="$2"
  local attempts="${3:-60}"
  local i=1
  while (( i <= attempts )); do
    if curl -sf "$url" >/dev/null 2>&1; then
      green "  ✓ $name is up"
      return 0
    fi
    sleep 1
    ((i++)) || true
  done
  red "  ✗ $name did not become ready ($url)"
  return 1
}

wait_for_redis() {
  local attempts="${1:-40}"
  local i=1
  while (( i <= attempts )); do
    if redis_ping; then
      green "  ✓ Redis is up"
      return 0
    fi
    sleep 1
    ((i++)) || true
  done
  red "  ✗ Redis did not become ready on 127.0.0.1:6379"
  return 1
}

start_redis() {
  yellow "[1/4] Starting Redis..."

  if redis_ping; then
    REDIS_MODE="existing"
    green "  ✓ Redis already running on port 6379"
    return 0
  fi

  # Try Docker without sudo
  if command -v docker >/dev/null 2>&1; then
    if docker_compose up -d >"$LOG_DIR/redis-docker.log" 2>&1; then
      REDIS_MODE="docker"
      wait_for_redis 40
      return $?
    fi

    # Permission denied / daemon issues — try sudo docker
    if grep -qiE "permission denied|cannot connect|connect to the docker" "$LOG_DIR/redis-docker.log" 2>/dev/null; then
      yellow "  Docker socket permission denied — trying with sudo..."
      if sudo_docker_compose up -d >"$LOG_DIR/redis-docker.log" 2>&1; then
        REDIS_MODE="docker-sudo"
        wait_for_redis 40
        return $?
      fi
    fi
  fi

  # Fall back to local redis-server
  if command -v redis-server >/dev/null 2>&1; then
    yellow "  Starting local redis-server..."
    redis-server --daemonize yes --port 6379 --dir "$LOG_DIR" --dbfilename redis-dump.rdb --pidfile "$LOG_DIR/redis-local.pid" >"$LOG_DIR/redis-local.log" 2>&1 || true
    if [[ -f "$LOG_DIR/redis-local.pid" ]]; then
      REDIS_LOCAL_PID="$(cat "$LOG_DIR/redis-local.pid")"
    fi
    REDIS_MODE="local"
    wait_for_redis 20
    return $?
  fi

  red "  ✗ Could not start Redis."
  echo
  yellow "Fix one of these options:"
  yellow "  1) Add your user to the docker group (recommended), then log out/in:"
  yellow "       sudo usermod -aG docker \"\$USER\""
  yellow "  2) Install Redis locally:"
  yellow "       sudo apt-get install -y redis-server"
  yellow "  3) Re-run this script and enter your password when sudo is requested."
  echo
  return 1
}

blue "========================================"
blue "  ForInsighter — starting all services"
blue "========================================"
echo

# Always clear leftovers from a previous run first
stop_existing
echo

# Preconditions
if [[ ! -d "$VENV" ]]; then
  red "Python venv not found at $VENV"
  yellow "Create it first:"
  yellow "  python3 -m venv backend/venv && source backend/venv/bin/activate && pip install -r requirements.txt"
  STOP_REASON="error"
  exit 1
fi

if [[ ! -f "$BACKEND/.env" ]]; then
  yellow "No backend/.env found — copying from .env.example"
  cp "$BACKEND/.env.example" "$BACKEND/.env"
fi

if [[ ! -d "$ROOT/node_modules" ]]; then
  yellow "node_modules missing — running npm install..."
  (cd "$ROOT" && npm install) || {
    red "npm install failed"
    STOP_REASON="error"
    exit 1
  }
fi

# 1) Redis
if ! start_redis; then
  STOP_REASON="error"
  exit 1
fi

# 2) Backend API
echo
yellow "[2/4] Starting Backend API (port 8000)..."
# shellcheck disable=SC1091
source "$VENV/bin/activate"
(
  cd "$BACKEND"
  exec uvicorn main:app --reload --port 8000 --host 127.0.0.1
) >"$LOG_DIR/backend.log" 2>&1 &
UVICORN_PID=$!
if ! wait_for_http "http://127.0.0.1:8000/api/health" "Backend API" 60; then
  red "  Backend log: $LOG_DIR/backend.log"
  STOP_REASON="error"
  exit 1
fi

# 3) Celery
echo
yellow "[3/4] Starting Celery worker..."
(
  cd "$BACKEND"
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  exec celery -A tasks.celery_tasks.celery_app worker --loglevel=info
) >"$LOG_DIR/celery.log" 2>&1 &
CELERY_PID=$!
sleep 2
if ! kill -0 "$CELERY_PID" 2>/dev/null; then
  red "  ✗ Celery failed to start — see $LOG_DIR/celery.log"
  STOP_REASON="error"
  exit 1
fi
# Confirm it can talk to Redis (celery process still alive after a few seconds)
sleep 1
if ! kill -0 "$CELERY_PID" 2>/dev/null; then
  red "  ✗ Celery exited early — see $LOG_DIR/celery.log"
  STOP_REASON="error"
  exit 1
fi
green "  ✓ Celery worker is up"

# 4) Frontend
echo
yellow "[4/4] Starting Frontend (port 8080)..."
(
  cd "$ROOT"
  exec npm run dev -- --host 127.0.0.1 --port 8080
) >"$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
if ! wait_for_http "http://127.0.0.1:8080" "Frontend" 60; then
  red "  Frontend log: $LOG_DIR/frontend.log"
  STOP_REASON="error"
  exit 1
fi

# Final verification
echo
yellow "Verifying all services..."
ALL_OK=1
redis_ping || { red "  ✗ Redis check failed"; ALL_OK=0; }
curl -sf "http://127.0.0.1:8000/api/health" >/dev/null || { red "  ✗ Backend check failed"; ALL_OK=0; }
kill -0 "$CELERY_PID" 2>/dev/null || { red "  ✗ Celery check failed"; ALL_OK=0; }
curl -sf "http://127.0.0.1:8080" >/dev/null || { red "  ✗ Frontend check failed"; ALL_OK=0; }

if [[ "$ALL_OK" -ne 1 ]]; then
  red "Not all services are healthy. Check logs in $LOG_DIR/"
  STOP_REASON="error"
  exit 1
fi
green "  ✓ All services verified"

printf '%s\n' "$UVICORN_PID" "$CELERY_PID" "$FRONTEND_PID" >"$PID_FILE"
STARTED_OK=1

echo
green "========================================"
green "  Ready to Dive in"
green "========================================"
echo
echo "  Website:  http://localhost:8080"
echo "  API:      http://localhost:8000/api/health"
echo
echo "  Logs:     $LOG_DIR/"
echo "  Stop:     Ctrl+C  or  Ctrl+Z"
echo
yellow "Leave this terminal open while you use the site."
echo

while true; do
  for pid in "$UVICORN_PID" "$CELERY_PID" "$FRONTEND_PID"; do
    if ! kill -0 "$pid" 2>/dev/null; then
      red "A service exited unexpectedly. Check logs in $LOG_DIR/"
      STOP_REASON="error"
      exit 1
    fi
  done
  sleep 2
done
