#!/usr/bin/env bash
# Run the slideshow locally in windowed mode (devcontainer only).
# Accepts additional arguments pass-through to the slideshow.
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run slideshow --windowed "$@"