#!/usr/bin/env bash
# Sync the project environment. Creates .venv and installs dependencies
# from the committed uv.lock. Run after cloning or pulling.
set -euo pipefail
cd "$(dirname "$0")/.."
uv sync --frozen