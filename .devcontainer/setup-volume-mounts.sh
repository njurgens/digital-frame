#!/usr/bin/env bash
# Fixes ownership of named volumes that come up root-owned on first create.
# Usage: setup-volume-mounts.sh <dir1> [dir2] ...
set -euo pipefail

USER_NAME="$(id -un)"
for dir in "$@"; do
  if [ -d "$dir" ] && [ "$(stat -c '%U' "$dir")" != "$USER_NAME" ]; then
    sudo chown -R "$USER_NAME:$USER_NAME" "$dir"
  fi
done