#!/usr/bin/env bash
# Run tests and check differential coverage (90% threshold).
#   bash eng/test.sh              # run all (except integration) + diff coverage
#   bash eng/test.sh -k backlight # filter by name + diff coverage
#   bash eng/test.sh tests/test_config_store.py -v  # specific file
#   bash eng/test.sh --integration # run integration tests (requires Pi SSH)
#   bash eng/test.sh --skip-diff  # run tests without diff coverage check
set -euo pipefail
cd "$(dirname "$0")/.."
COVERAGE_FILE=".coverage.xml"
if [[ "$*" == *"--integration"* ]]; then
    uv run pytest tests/test_integration.py -v
elif [[ "$*" == *"--skip-diff"* ]]; then
    uv run pytest --ignore=tests/test_integration.py "${@/--skip-diff/}"
else
    uv run pytest --ignore=tests/test_integration.py --cov=. --cov-report=xml:"$COVERAGE_FILE" "$@"
    diff-cover "$COVERAGE_FILE" --fail-under=90 --exclude "test_*.py" "conftest.py"
fi