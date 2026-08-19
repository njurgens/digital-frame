#!/usr/bin/env bash
#
# update-issue.sh — Update an existing GitHub issue's title and/or body.
#
# Usage:
#   update-issue.sh ISSUE_NUMBER [--title "NEW TITLE"] [--body-file FILE]
#
# Options:
#   --title TITLE       New title (optional)
#   --body-file FILE    Path to markdown file with the new body (optional)
#   --repo REPO         Override repo (default: njurgens/digital-frame)
#   --help              Show this help text
#
# At least one of --title / --body-file is required.
#
set -euo pipefail

REPO="${PIFRAME_GH_REPO:-njurgens/digital-frame}"
NUM=""
TITLE=""
BODY_FILE=""

usage() {
    sed -n '2,15p' "$0" | sed 's/^# \?//'
    exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help)      usage ;;
        --title)     TITLE="$2"; shift 2 ;;
        --body-file) BODY_FILE="$2"; shift 2 ;;
        --repo)      REPO="$2"; shift 2 ;;
        -*)          echo "Unknown option: $1" >&2; usage 1 ;;
        *)
            if [[ -z "$NUM" ]]; then
                NUM="$1"; shift
            else
                echo "Unexpected argument: $1" >&2; usage 1
            fi
            ;;
    esac
done

if [[ -z "$NUM" ]]; then
    echo "Error: issue number is required (first positional argument)" >&2
    usage 1
fi

if [[ -z "$TITLE" && -z "$BODY_FILE" ]]; then
    echo "Error: at least one of --title / --body-file is required" >&2
    usage 1
fi

if [[ -n "$BODY_FILE" && ! -f "$BODY_FILE" ]]; then
    echo "Error: body file not found: $BODY_FILE" >&2
    exit 1
fi

# Pre-flight: the 'gh' CLI must be installed and logged in
if ! command -v gh >/dev/null 2>&1; then
    echo "Error: the 'gh' CLI is not installed (see https://cli.github.com/)." >&2
    exit 1
fi
if ! gh auth status >/dev/null 2>&1; then
    echo "Error: 'gh' is not logged in. Run 'gh auth login' first." >&2
    exit 1
fi

ARGS=()
if [[ -n "$TITLE" ]]; then ARGS+=(--title "$TITLE"); fi
if [[ -n "$BODY_FILE" ]]; then ARGS+=(--body-file "$BODY_FILE"); fi

echo "Updating issue #$NUM in $REPO" >&2
gh issue edit "$NUM" --repo "$REPO" "${ARGS[@]}"
echo "https://github.com/$REPO/issues/$NUM"
