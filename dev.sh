#!/usr/bin/env bash
# Gifty dev runner: sets up and launches backend (FastAPI) and frontend (Vite)
# together. Both run in the foreground; Ctrl-C stops both cleanly.
#
# Usage:
#   ./dev.sh           install deps if needed, then run backend + frontend
#   ./dev.sh setup     install deps only (uv sync, bun install), then exit
#   ./dev.sh backend   run backend only
#   ./dev.sh frontend  run frontend only
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

# Fail early with a clear message if a required tool is missing.
need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "error: '$1' not found. $2" >&2
    exit 1
  }
}

setup_backend() {
  need uv "Install: https://docs.astral.sh/uv/getting-started/installation/"
  echo "==> backend: uv sync"
  (cd "$BACKEND" && uv sync)
  # Copy the env template on first run so the keys are obvious to fill in.
  if [ ! -f "$BACKEND/.env" ]; then
    cp "$BACKEND/.env.example" "$BACKEND/.env"
    echo "==> backend: created backend/.env, add your API keys before running"
  fi
}

setup_frontend() {
  need bun "Install: https://bun.sh/docs/installation"
  echo "==> frontend: bun install"
  (cd "$FRONTEND" && bun install)
}

# Kill any stale listener on a port so a previous crashed run doesn't block the
# bind with "address already in use".
free_port() {
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "$1/tcp" >/dev/null 2>&1 || true
  elif command -v lsof >/dev/null 2>&1; then
    lsof -ti "tcp:$1" 2>/dev/null | xargs -r kill 2>/dev/null || true
  fi
}

run_backend() {
  free_port 8000
  echo "==> backend: http://localhost:8000 (docs at /docs)"
  (cd "$BACKEND" && exec uv run uvicorn app:app --port 8000)
}

run_frontend() {
  free_port 5173
  echo "==> frontend: http://localhost:5173"
  (cd "$FRONTEND" && exec bun run dev)
}

case "${1:-all}" in
setup)
  setup_backend
  setup_frontend
  echo "==> setup done"
  ;;
backend)
  setup_backend
  run_backend
  ;;
frontend)
  setup_frontend
  run_frontend
  ;;
all)
  setup_backend
  setup_frontend
  # Launch both in the background, then kill the whole process group on exit so
  # neither server is left running after Ctrl-C.
  trap 'kill 0' EXIT INT TERM
  run_backend &
  run_frontend &
  wait
  ;;
*)
  echo "usage: ./dev.sh [setup|backend|frontend]" >&2
  exit 1
  ;;
esac
