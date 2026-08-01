#!/usr/bin/env bash
# Run linter, formatter, and type checker. Use before committing.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run ruff check .
uv run ruff format --check .
uv run basedpyright