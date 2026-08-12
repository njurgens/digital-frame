#!/usr/bin/env bash
# Run tests. Accepts pytest arguments pass-through.
#   bash eng/test.sh              # run all (except integration)
#   bash eng/test.sh -k backlight # filter by name
#   bash eng/test.sh tests/test_config_store.py -v  # specific file
#   bash eng/test.sh --integration # run integration tests (requires Pi SSH)
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$*" == *"--integration"* ]]; then
    uv run pytest tests/test_integration.py -v
else
    uv run pytest --ignore=tests/test_integration.py "$@"
fi