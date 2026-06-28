#!/usr/bin/env bash
# qBittorrent completion hook for native Linux / macOS.
set -uo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$APP_DIR/logs"
FALLBACK_LOG="/tmp/jellyshift-hook.log"

_ensure_hook_log() {
  mkdir -p "$LOG_DIR" 2>/dev/null || true
  if [[ -w "$LOG_DIR" ]] && touch "$LOG_DIR/.write-test" 2>/dev/null; then
    rm -f "$LOG_DIR/.write-test"
    echo "$LOG_DIR/hook.log"
    return 0
  fi
  touch "$FALLBACK_LOG" 2>/dev/null || true
  echo "$FALLBACK_LOG"
  return 1
}

HOOK_LOG="$(_ensure_hook_log)" || true

log_hook() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$HOOK_LOG" 2>/dev/null || \
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$FALLBACK_LOG" 2>/dev/null || true
}

log_hook "─── hook started ───"
log_hook "user: $(id -un 2>/dev/null || echo unknown)"
log_hook "content path: ${1:-<missing>}"
log_hook "torrent:      ${2:-<missing>}"
log_hook "category:     ${3:-<empty>}"

if [[ $# -lt 2 ]]; then
  log_hook "ERROR: expected at least 2 arguments (path, torrent name)"
  exit 1
fi

CATEGORY_ARGS=()
if [[ -n "${3:-}" ]]; then
  CATEGORY_ARGS=(--category "$3")
fi

JELLYSHIFT="$APP_DIR/.venv/bin/jellyshift"
if [[ ! -x "$JELLYSHIFT" ]]; then
  log_hook "ERROR: jellyshift not found at $JELLYSHIFT"
  exit 1
fi

log_hook "running jellyshift..."
set +e
if ((${#CATEGORY_ARGS[@]})); then
  "$JELLYSHIFT" \
    --config "$APP_DIR/config.yaml" \
    "$1" \
    --torrent-name "$2" \
    "${CATEGORY_ARGS[@]}"
else
  "$JELLYSHIFT" \
    --config "$APP_DIR/config.yaml" \
    "$1" \
    --torrent-name "$2"
fi
status=$?
set -e

if [[ $status -ne 0 ]]; then
  log_hook "ERROR: jellyshift exited with status $status"
  exit "$status"
fi

log_hook "hook finished ok"
