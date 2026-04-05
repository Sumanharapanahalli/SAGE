#!/usr/bin/env bash
# ============================================================================
# SAGE Framework — One-Click Launcher (Linux / macOS / Git Bash on Windows)
#
# Usage:
#   ./start.sh                    # default project (starter)
#   ./start.sh my_project         # specific project
#   ./start.sh my_project 9000    # custom backend port
# ============================================================================

set -e

PROJECT="${1:-starter}"
PORT="${2:-8000}"
SAGE_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║       SAGE Framework Launcher         ║"
echo "  ╠═══════════════════════════════════════╣"
echo "  ║  Project:  $PROJECT"
echo "  ║  Backend:  http://localhost:$PORT"
echo "  ║  Web UI:   http://localhost:5173"
echo "  ╚═══════════════════════════════════════╝"
echo ""

# --- Detect Python venv ---
if [ -f "$SAGE_DIR/.venv/bin/python" ]; then
    PYTHON="$SAGE_DIR/.venv/bin/python"
elif [ -f "$SAGE_DIR/.venv/Scripts/python.exe" ]; then
    PYTHON="$SAGE_DIR/.venv/Scripts/python.exe"
else
    echo "ERROR: Virtual environment not found. Run 'make venv' first."
    exit 1
fi

# --- Check node_modules ---
if [ ! -d "$SAGE_DIR/web/node_modules" ]; then
    echo "Installing web UI dependencies..."
    cd "$SAGE_DIR/web" && npm install
fi

# --- Start backend in background ---
echo "Starting backend..."
cd "$SAGE_DIR"
SAGE_PROJECT="$PROJECT" SAGE_SOLUTIONS_DIR="${SAGE_SOLUTIONS_DIR:-solutions}" \
    "$PYTHON" src/main.py api --host 0.0.0.0 --port "$PORT" &
BACKEND_PID=$!

# --- Start web UI in background ---
echo "Starting web UI..."
cd "$SAGE_DIR/web"
npm run dev &
UI_PID=$!

# --- Trap Ctrl+C to kill both ---
cleanup() {
    echo ""
    echo "Shutting down SAGE..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $UI_PID 2>/dev/null || true
    wait $BACKEND_PID 2>/dev/null || true
    wait $UI_PID 2>/dev/null || true
    echo "Done."
}
trap cleanup INT TERM

echo ""
echo "SAGE is running. Press Ctrl+C to stop."
echo ""

# Wait for either process to exit
wait
