#!/usr/bin/env bash
# qBittorrent completion hook — converts Windows paths and invokes jellyshift.

# Bootstrap log first — survives failures before main logging is set up.
_BOOT_LOG="/tmp/jellyshift-hook.log"
{
  echo "$(date '+%Y-%m-%d %H:%M:%S') ── invoked pid=$$ uid=$(id -u 2>/dev/null || echo ?) user=$(id -un 2>/dev/null || echo ?)"
  printf '%s\n' "$(date '+%Y-%m-%d %H:%M:%S')    argv:" "$@"
} >> "$_BOOT_LOG" 2>/dev/null || true

set -uo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$APP_DIR/logs"
FALLBACK_LOG="/tmp/jellyshift-hook.log"
WSL_USER="${JELLYSHIFT_USER:-sharath}"

# qBittorrent often launches wsl.exe as root; root cannot create dirs on /mnt/* (drvfs).
if [[ "$(id -u)" -eq 0 && "$(id -un 2>/dev/null)" != "$WSL_USER" ]]; then
  {
    echo "$(date '+%Y-%m-%d %H:%M:%S') re-exec as $WSL_USER (was root)"
  } >> "$_BOOT_LOG" 2>/dev/null || true
  if command -v runuser >/dev/null 2>&1; then
    exec runuser -u "$WSL_USER" -- "$0" "$@"
  elif command -v sudo >/dev/null 2>&1; then
    exec sudo -u "$WSL_USER" -- "$0" "$@"
  fi
fi

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
  # Never abort the hook if logging fails (e.g. root-owned logs/ directory).
  echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$HOOK_LOG" 2>/dev/null || \
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$FALLBACK_LOG" 2>/dev/null || true
}

log_hook "─── hook started ───"
log_hook "hook log: $HOOK_LOG"
log_hook "bootstrap log: $_BOOT_LOG"
log_hook "user: $(id -un 2>/dev/null || echo unknown) uid=$(id -u 2>/dev/null || echo ?)"
log_hook "arg1 (win path): ${1:-<missing>}"
log_hook "arg2 (torrent):  ${2:-<missing>}"
log_hook "arg3 (category): ${3:-<empty>}"

if [[ $# -lt 2 ]]; then
  log_hook "ERROR: expected at least 2 arguments (path, torrent name)"
  exit 1
fi

if ! LINUX_PATH="$(wslpath -u "$1" 2>>"$HOOK_LOG")"; then
  log_hook "ERROR: wslpath failed for: $1"
  exit 1
fi
log_hook "linux path: $LINUX_PATH"

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
    "$LINUX_PATH" \
    --torrent-name "$2" \
    "${CATEGORY_ARGS[@]}"
else
  "$JELLYSHIFT" \
    --config "$APP_DIR/config.yaml" \
    "$LINUX_PATH" \
    --torrent-name "$2"
fi
status=$?
set -e

if [[ $status -ne 0 ]]; then
  log_hook "ERROR: jellyshift exited with status $status (see logs/jellyshift.log or $FALLBACK_LOG)"
  exit "$status"
fi

log_hook "hook finished ok"
