#!/usr/bin/env bash
# Run tests and check differential coverage (90% threshold).
#   bash eng/test.sh              # run all + diff coverage
#   bash eng/test.sh -k backlight # filter by name + diff coverage
#   bash eng/test.sh tests/test_config_store.py -v  # specific file
#   bash eng/test.sh --skip-diff  # run tests without diff coverage check
set -euo pipefail
cd "$(dirname "$0")/.."
COVERAGE_FILE=".coverage.xml"
if [[ "$*" == *"--skip-diff"* ]]; then
    uv run pytest "${@/--skip-diff/}"
else
    uv run pytest --cov=. --cov-report=xml:"$COVERAGE_FILE" "$@"
    diff-cover "$COVERAGE_FILE" --fail-under=90 --exclude "test_*.py" "conftest.py"
fi
