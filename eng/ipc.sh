#!/usr/bin/env bash
# Drive the running app over its IPC command API.
#
#   bash eng/ipc.sh state
#   bash eng/ipc.sh screenshot --path /tmp/view.png
#   bash eng/ipc.sh swipe 100 200 0 500 --ms 1500
#   bash eng/ipc.sh set_config display interval 12
#   bash eng/ipc.sh quit
#
# The client resolves the socket the same way the app does and probes the
# app's two candidate locations for an existing socket; pass --socket to
# override. See docs/ipc.md for the full command set.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
exec uv run piframe-ipc "$@"
