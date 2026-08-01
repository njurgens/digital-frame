#!/usr/bin/env bash
# Run tests. Accepts pytest arguments pass-through.
#   bash eng/test.sh              # run all
#   bash eng/test.sh -k backlight # filter by name
#   bash eng/test.sh tests/test_config_store.py -v  # specific file
set -euo pipefail
cd "$(dirname "$0")/.."
uv run pytest "$@"