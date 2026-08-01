#!/usr/bin/env bash
# Run the slideshow locally (devcontainer only — needs a display).
# Accepts arguments pass-through to the slideshow.
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run slideshow "$@"