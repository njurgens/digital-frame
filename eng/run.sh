#!/usr/bin/env bash
# Run the slideshow in the devcontainer (windowed, X11).
#
#   eng/run.sh               start detached in the background (default);
#                           prints the PID; output goes to $PIFRAME_LOG
#   eng/run.sh -f            run in the foreground (Ctrl-C to stop);
#                           also accepted: --foreground, --fg
#   eng/run.sh --kill        stop the background instance (via the PID file in the runtime dir)
#   eng/run.sh --kill <PID>  stop a specific PID
#
# Extra arguments are passed through to the slideshow.
#
# Environment overrides:
#   PIFRAME_SYNC__PROVIDER            (default: local)
#   PIFRAME_SYNC__LOCAL__SOURCE_DIR   (default: tests/fixtures/stock)
#   PIFRAME_LOG                       (default: /tmp/piframe-run.log)
set -euo pipefail
cd "$(dirname "$0")/.."

# Resolve the PID file the same way the app does: the per-user runtime dir
# if it exists, else the user-creatable fallback dir (created 0700 if absent).
if [[ -n "${XDG_RUNTIME_DIR:-}" && -d "$XDG_RUNTIME_DIR" ]]; then
  PIFRAME_RUNTIME_DIR="$XDG_RUNTIME_DIR"
else
  PIFRAME_RUNTIME_DIR="${HOME}/.local/piframe"
  if [[ ! -d "$PIFRAME_RUNTIME_DIR" ]]; then
    mkdir -p "$PIFRAME_RUNTIME_DIR"
    chmod 700 "$PIFRAME_RUNTIME_DIR"
  fi
fi
PIDFILE="$PIFRAME_RUNTIME_DIR/slideshow.pid"
LOG="${PIFRAME_LOG:-/tmp/piframe-run.log}"

# --- stop mode ---------------------------------------------------------------
if [[ ${1:-} == "--kill" ]]; then
  pid="${2:-}"
  if [[ -z "$pid" ]]; then
    [[ -f $PIDFILE ]] || { echo "no $PIDFILE — nothing to kill" >&2; exit 1; }
    if flock -n "$PIDFILE" -c true 2>/dev/null; then
      # No live holder (the app holds the lock for its lifetime): the file
      # is stale — remove it rather than risk killing a recycled PID.
      rm -f "$PIDFILE"
      echo "removed stale $PIDFILE (no live slideshow)"
      exit 0
    fi
    pid=$(cat "$PIDFILE")
  fi
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    echo "sent SIGTERM to $pid"
  else
    echo "process $pid is not running"
  fi
  exit 0
fi

# --- parse flags -------------------------------------------------------------
fg=0
args=()
for a in "$@"; do
  case $a in
    -f|--foreground|--fg) fg=1 ;;
    *) args+=("$a") ;;
  esac
done

# The app reads src/config.toml (gitignored); bootstrap it from the
# devcontainer template on first run (see config.devcontainer.toml).
if [[ ! -f src/config.toml ]]; then
  cp config.devcontainer.toml src/config.toml
  echo "created src/config.toml from config.devcontainer.toml"
fi

export PIFRAME_SYNC__PROVIDER="${PIFRAME_SYNC__PROVIDER:-local}"
export PIFRAME_SYNC__LOCAL__SOURCE_DIR="${PIFRAME_SYNC__LOCAL__SOURCE_DIR:-$PWD/tests/fixtures/stock}"

# --- foreground mode ----------------------------------------------------------
if [[ $fg -eq 1 ]]; then
  exec uv run slideshow --windowed "${args[@]}"
fi

# --- background mode (default) -------------------------------------------------
# Refuse to start a second instance: the app holds an exclusive flock on the
# PID file for its lifetime, so a held lock means a live instance (the
# kernel releases the lock on death, so a free one means the file is stale).
if [[ -f $PIDFILE ]] && ! flock -n "$PIDFILE" -c true 2>/dev/null; then
  echo "slideshow already running (pid $(cat "$PIDFILE")) — stop it first: $0 --kill" >&2
  exit 1
fi
rm -f "$PIDFILE"
# Launch in a new session with stdio redirected to the log so the process
# survives this shell exiting.
setsid uv run slideshow --windowed "${args[@]}" </dev/null >>"$LOG" 2>&1 &
disown || true

# The app writes its own PID file shortly after startup; wait for it so we
# report the authoritative PID (and detect a failed start).
for _ in 1 2 3 4 5 6 7 8 9 10; do
  [[ -f $PIDFILE ]] && break
  sleep 0.5
done

if [[ -f $PIDFILE ]]; then
  # The file is written before the app is fully up (right after
  # pygame.init), so a crash during startup can still follow: give it a
  # moment, then confirm the process is alive before reporting success.
  sleep 1
  pid=$(cat "$PIDFILE")
  if kill -0 "$pid" 2>/dev/null; then
    echo "slideshow running (pid $pid) — log: $LOG"
    echo "stop with: $0 --kill"
  else
    echo "slideshow failed to start — last log lines:" >&2
    tail -n 5 "$LOG" >&2
    exit 1
  fi
else
  echo "slideshow failed to start — last log lines:" >&2
  tail -n 5 "$LOG" >&2
  exit 1
fi
