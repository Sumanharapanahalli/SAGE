#!/usr/bin/env bash
#
# One-click launcher for the SAGE web interface.
#
# The web UI is two processes — a FastAPI backend and a Vite dev server —
# and `make run` / `make ui` each start only one, in a foreground terminal
# you then can't close. This script starts both, waits until the backend is
# actually answering before bringing up the UI, opens a browser, and shuts
# both down together on Ctrl+C or when the window closes.
#
# Usage:
#   ./start-web.sh                  pick a solution interactively (or use the
#                                   only one, if there is only one)
#   ./start-web.sh medtech_sample   skip the prompt
#   SAGE_PROJECT=starter ./start-web.sh
#
# Env overrides: SAGE_API_PORT (default 8000), SAGE_UI_PORT (default 5173),
# SAGE_SOLUTIONS_DIR, SAGE_NO_BROWSER=1 to skip opening a browser.

set -uo pipefail

# Resolve the repo root from this script's own location, so the launcher
# works from a desktop icon, a file manager, or any cwd.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT" || exit 1

BOLD=$'\033[1m'; RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; DIM=$'\033[2m'; OFF=$'\033[0m'
say()  { printf '%s\n' "$*"; }
ok()   { printf '%s✓%s %s\n' "$GREEN" "$OFF" "$*"; }
warn() { printf '%s!%s %s\n' "$YELLOW" "$OFF" "$*"; }
die()  { printf '\n%s✗ %s%s\n' "$RED" "$*" "$OFF" >&2; hold; exit 1; }

# A launcher opened by double-click gets its own window, which vanishes on
# exit and takes the error message with it. Keep it up if we're on a TTY.
hold() {
  if [ -t 0 ]; then
    printf '\n%sPress Enter to close.%s ' "$DIM" "$OFF"
    read -r _ || true
  fi
}

# --- desktop shortcut -------------------------------------------------------

# A bare .sh is not clickable in GNOME/KDE file managers without fiddling
# with per-user "allow launching" settings. A .desktop entry is, and it can
# carry Terminal=true so the operator sees progress and errors. Paths inside
# it must be absolute, hence generating it rather than shipping a static file.
install_shortcut() {
  local apps="$HOME/.local/share/applications"
  local desktop_dir; desktop_dir="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
  local file="$apps/sage-web.desktop"
  mkdir -p "$apps"
  cat > "$file" <<EOF
[Desktop Entry]
Type=Application
Name=SAGE Web
Comment=Start the SAGE web interface (API + UI) and open it in a browser
Exec=$ROOT/start-web.sh
Path=$ROOT
Terminal=true
Categories=Development;
EOF
  chmod +x "$file"
  ok "Installed $file"
  if [ -d "$desktop_dir" ]; then
    cp "$file" "$desktop_dir/sage-web.desktop"
    chmod +x "$desktop_dir/sage-web.desktop"
    # GNOME requires the copy on the desktop to be explicitly trusted.
    gio set "$desktop_dir/sage-web.desktop" metadata::trusted true 2>/dev/null || true
    ok "Installed $desktop_dir/sage-web.desktop"
    say "${DIM}If the desktop icon shows as untrusted, right-click it → 'Allow Launching'.${OFF}"
  fi
  say ""
  say "You can now launch SAGE Web from your applications menu."
  exit 0
}

case "${1:-}" in
  --install-shortcut) install_shortcut ;;
  -h|--help)
    # Print the header comment block: from line 3 to the first non-comment
    # line. A fixed line range drifts every time the header is edited.
    awk 'NR<3 {next} !/^#/ {exit} {sub(/^# ?/, ""); print}' "${BASH_SOURCE[0]}"
    exit 0
    ;;
esac

LOG_DIR="$ROOT/.sage-logs"
mkdir -p "$LOG_DIR"
API_LOG="$LOG_DIR/web-api.log"
UI_LOG="$LOG_DIR/web-ui.log"

say "${BOLD}SAGE web interface${OFF}"
say "${DIM}$ROOT${OFF}"
say ""

# --- prerequisites ----------------------------------------------------------

PYTHON="$ROOT/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="$ROOT/.venv/Scripts/python"   # Git Bash on Windows
[ -x "$PYTHON" ] || die "No virtualenv found at .venv — run 'make venv' first (one time, and it is a large install)."

command -v npm >/dev/null 2>&1 || die "npm is not on PATH. Install Node.js, then re-run."

# web/node_modules is NOT checked in and is genuinely absent on a fresh
# clone, so `make ui` fails outright there. Install on demand rather than
# making the operator diagnose a vite-not-found error.
if [ ! -d "$ROOT/web/node_modules" ]; then
  say "Installing web dependencies (first run only)…"
  ( cd "$ROOT/web" && npm install ) || die "npm install failed. See the output above."
  ok "Web dependencies installed"
fi

# --- pick a solution --------------------------------------------------------

SOLUTIONS_DIR="${SAGE_SOLUTIONS_DIR:-$ROOT/solutions}"

# A directory is a solution when it has a project.yaml — the same rule
# project_loader.list_solutions uses. Anything else in solutions/ (docs-only
# dirs like medtech/, __collective__, .archive) is not selectable and must
# not be offered. Plain glob rather than `find -printf`, which is GNU-only.
AVAILABLE=()
for d in "$SOLUTIONS_DIR"/*/; do
  [ -f "$d/project.yaml" ] || continue
  name="$(basename "$d")"
  case "$name" in .*|__*) continue ;; esac
  AVAILABLE+=("$name")
done
[ "${#AVAILABLE[@]}" -gt 0 ] || die "No solutions found in $SOLUTIONS_DIR (looked for */project.yaml)."

PROJECT="${1:-${SAGE_PROJECT:-}}"

if [ -n "$PROJECT" ]; then
  printf '%s\n' "${AVAILABLE[@]}" | grep -qx -- "$PROJECT" \
    || die "'$PROJECT' is not a solution. Available: ${AVAILABLE[*]}"
elif [ "${#AVAILABLE[@]}" -eq 1 ]; then
  PROJECT="${AVAILABLE[0]}"
elif [ -t 0 ]; then
  say "Which solution?"
  for i in "${!AVAILABLE[@]}"; do
    printf '  %s) %s\n' "$((i + 1))" "${AVAILABLE[$i]}"
  done
  printf 'Choice [1]: '
  read -r choice || choice=""
  choice="${choice:-1}"
  case "$choice" in
    ''|*[!0-9]*) die "Not a number: $choice" ;;
  esac
  [ "$choice" -ge 1 ] && [ "$choice" -le "${#AVAILABLE[@]}" ] || die "Choice out of range: $choice"
  PROJECT="${AVAILABLE[$((choice - 1))]}"
else
  # No TTY (launched from a file manager with no terminal): don't guess
  # silently at something the operator may not want touched.
  die "No solution given and no terminal to ask in. Pass one: ./start-web.sh <solution>. Available: ${AVAILABLE[*]}"
fi

ok "Solution: ${BOLD}$PROJECT${OFF}"

# --- ports ------------------------------------------------------------------

port_busy() {
  # Prefer a real bind test over parsing `ss`/`lsof`, which vary by distro
  # and only see sockets this user is allowed to see.
  "$PYTHON" - "$1" <<'PY' 2>/dev/null
import socket, sys
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(("127.0.0.1", int(sys.argv[1])))
except OSError:
    sys.exit(0)   # busy
finally:
    s.close()
sys.exit(1)       # free
PY
}

pick_port() {
  local want="$1" p="$1" limit=$(( $1 + 20 ))
  while [ "$p" -lt "$limit" ]; do
    port_busy "$p" || { printf '%s' "$p"; return 0; }
    p=$((p + 1))
  done
  return 1
}

API_PORT="$(pick_port "${SAGE_API_PORT:-8000}")" || die "No free port near ${SAGE_API_PORT:-8000}."
UI_PORT="$(pick_port "${SAGE_UI_PORT:-5173}")"   || die "No free port near ${SAGE_UI_PORT:-5173}."
[ "$API_PORT" = "${SAGE_API_PORT:-8000}" ] || warn "Port ${SAGE_API_PORT:-8000} was busy — using $API_PORT for the API."
[ "$UI_PORT"  = "${SAGE_UI_PORT:-5173}" ]  || warn "Port ${SAGE_UI_PORT:-5173} was busy — using $UI_PORT for the UI."

# --- shutdown ---------------------------------------------------------------

API_PID=""; UI_PID=""

# Each half runs under `setsid`, so it leads its own process group and we can
# signal the whole tree at once. Read the PGID back from ps rather than
# assuming PGID == PID: setsid forks instead of exec'ing when the caller is
# already a group leader, and whether that is the case depends on job
# control, which differs between `bash start-web.sh` and `./start-web.sh`
# under some shells. Getting this wrong leaves vite's esbuild children alive
# and still holding the port after "shutdown".
pgid_of() { ps -o pgid= -p "$1" 2>/dev/null | tr -d ' '; }

cleanup() {
  trap - EXIT INT TERM
  say ""
  say "Shutting down…"
  local sig
  for sig in TERM KILL; do
    for pid in "$UI_PID" "$API_PID"; do
      [ -n "$pid" ] || continue
      local pgid; pgid="$(pgid_of "$pid")"
      if [ -n "$pgid" ]; then
        kill "-$sig" "-$pgid" 2>/dev/null
      else
        kill "-$sig" "$pid" 2>/dev/null
      fi
    done
    [ "$sig" = TERM ] && sleep 1
  done
  ok "Stopped."
}
trap cleanup EXIT INT TERM

# --- backend ----------------------------------------------------------------

say ""
say "Starting API on :$API_PORT  ${DIM}($API_LOG)${OFF}"
SAGE_PROJECT="$PROJECT" SAGE_SOLUTIONS_DIR="$SOLUTIONS_DIR" \
  setsid "$PYTHON" src/main.py api --host 127.0.0.1 --port "$API_PORT" \
  >"$API_LOG" 2>&1 &
API_PID=$!

# Wait for it to actually answer. The first boot imports the whole framework
# (ChromaDB, embeddings) and can take 30s+ on a cold cache — starting the UI
# before that just shows the operator a wall of failed requests.
say "Waiting for the API to come up…"
for _ in $(seq 1 90); do
  if ! kill -0 "$API_PID" 2>/dev/null; then
    say ""
    tail -n 25 "$API_LOG" >&2
    die "The API exited during startup. Full log: $API_LOG"
  fi
  if curl -fsS --max-time 2 "http://127.0.0.1:$API_PORT/health" >/dev/null 2>&1; then
    API_UP=1; break
  fi
  printf '.'
  sleep 1
done
say ""
[ "${API_UP:-}" = 1 ] || { tail -n 25 "$API_LOG" >&2; die "API did not answer /health within 90s. Full log: $API_LOG"; }
ok "API ready — http://localhost:$API_PORT/docs"

# --- frontend ---------------------------------------------------------------

say "Starting UI on :$UI_PORT  ${DIM}($UI_LOG)${OFF}"
# SAGE_API_PORT is read by web/vite.config.ts to aim the /api proxy. The web
# client calls a relative '/api', so without this the UI would talk to
# whatever is on 8000 — possibly nothing, possibly a different app.
# `exec` replaces the subshell with setsid, so $! is setsid's PID and not a
# short-lived wrapper's — otherwise cleanup would signal a process group
# that never contained npm.
( cd "$ROOT/web" && exec env SAGE_API_PORT="$API_PORT" SAGE_UI_PORT="$UI_PORT" \
    setsid npm run dev >"$UI_LOG" 2>&1 ) &
UI_PID=$!

for _ in $(seq 1 60); do
  curl -fsS --max-time 2 "http://127.0.0.1:$UI_PORT/" >/dev/null 2>&1 && { UI_UP=1; break; }
  printf '.'
  sleep 1
done
say ""
[ "${UI_UP:-}" = 1 ] || { tail -n 25 "$UI_LOG" >&2; die "UI did not come up within 60s. Full log: $UI_LOG"; }

URL="http://localhost:$UI_PORT"
ok "UI ready — $URL"

if [ "${SAGE_NO_BROWSER:-}" != "1" ] && command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" >/dev/null 2>&1 &
fi

say ""
say "${BOLD}${GREEN}SAGE is running.${OFF}  ${BOLD}$URL${OFF}"
say "${DIM}Solution: $PROJECT   API: http://localhost:$API_PORT   Logs: $LOG_DIR${OFF}"
say "${DIM}Press Ctrl+C to stop both.${OFF}"
say ""

# Return control when either half dies, so a crashed backend doesn't leave a
# UI up that only serves errors. `cleanup` (on EXIT) takes the other down.
wait -n "$API_PID" "$UI_PID" 2>/dev/null || wait "$API_PID"
warn "One of the two processes exited."
