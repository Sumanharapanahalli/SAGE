#!/usr/bin/env bash
# ==============================================================================
# SAGE Framework — Single-click launcher
# Starts the FastAPI backend + React UI in separate terminal tabs.
# Usage:
#   ./launch.sh                     # uses auto-discovered solution
#   ./launch.sh reflect             # specific solution
#   ./launch.sh reflect 8080        # specific solution + port
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="${1:-}"
PORT="${2:-8000}"
UI_PORT="5173"

cd "$SCRIPT_DIR"

# ── Resolve project ──────────────────────────────────────────────────────────
if [ -z "$PROJECT" ]; then
  # Auto-discover first project.yaml in solutions/
  PROJECT=$(ls -1 solutions/ | while read d; do
    [ -f "solutions/$d/project.yaml" ] && echo "$d" && break
  done)
fi

if [ -z "$PROJECT" ]; then
  echo "ERROR: No solution found in solutions/. Pass a project name: ./launch.sh reflect"
  exit 1
fi

echo ""
echo "  ╔══════════════════════════════════════════════════╗"
echo "  ║           SAGE Framework — Launching             ║"
echo "  ║  Solution : $PROJECT"
echo "  ║  Backend  : http://localhost:$PORT"
echo "  ║  Frontend : http://localhost:$UI_PORT"
echo "  ╚══════════════════════════════════════════════════╝"
echo ""

# ── Check venv ───────────────────────────────────────────────────────────────
if [ ! -f ".venv/bin/python" ]; then
  echo "ERROR: .venv not found. Run:  make venv"
  exit 1
fi

# ── Check node_modules ───────────────────────────────────────────────────────
if [ ! -d "web/node_modules" ]; then
  echo "Installing frontend dependencies..."
  cd web && npm install --silent && cd ..
fi

# ── Launch in gnome-terminal tabs ────────────────────────────────────────────
gnome-terminal \
  --title="SAGE — Backend ($PROJECT)" \
  -- bash -c "
    cd '$SCRIPT_DIR'
    echo '=== SAGE Backend — project: $PROJECT ==='
    SAGE_PROJECT=$PROJECT SAGE_SOLUTIONS_DIR=solutions .venv/bin/python src/main.py api --host 0.0.0.0 --port $PORT
    echo 'Backend stopped. Press Enter to close.'
    read
  " &

sleep 1

gnome-terminal \
  --title="SAGE — Frontend" \
  -- bash -c "
    cd '$SCRIPT_DIR/web'
    echo '=== SAGE Frontend — http://localhost:$UI_PORT ==='
    npm run dev
    echo 'Frontend stopped. Press Enter to close.'
    read
  " &

# ── Wait then open browser ───────────────────────────────────────────────────
echo "Waiting for services to start..."
sleep 4

# Try to open browser
if command -v xdg-open &>/dev/null; then
  xdg-open "http://localhost:$UI_PORT" &>/dev/null &
elif command -v google-chrome &>/dev/null; then
  google-chrome "http://localhost:$UI_PORT" &>/dev/null &
fi

echo ""
echo "  SAGE is running."
echo "  → UI:  http://localhost:$UI_PORT"
echo "  → API: http://localhost:$PORT/docs"
echo ""
echo "  Close the terminal windows to stop the services."
