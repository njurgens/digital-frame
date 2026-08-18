#!/usr/bin/env bash
#
# list-issues.sh — List GitHub issues as a markdown table.
#
# Usage:
#   list-issues.sh [--state open|closed|all] [--limit N] [--label L] [--search TEXT] [--repo REPO]
#
# Options:
#   --state STATE   Issue state: open, closed, or all (default: open)
#   --limit N       Maximum number of issues to list (default: 50)
#   --label L       Only issues with this label
#   --search TEXT   Search in issue titles and bodies
#   --repo REPO     Override repo (default: njurgens/digital-frame)
#   --help          Show this help text
#
# Example:
#   list-issues.sh --limit 20
#   list-issues.sh --label bug --search "cache"
#
set -euo pipefail

REPO="${PIFRAME_GH_REPO:-njurgens/digital-frame}"
STATE="open"
LIMIT=50
LABEL=""
SEARCH=""

usage() {
    sed -n '2,14p' "$0" | sed 's/^# \?//'
    exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help)    usage ;;
        --state)   STATE="$2"; shift 2 ;;
        --limit)   LIMIT="$2"; shift 2 ;;
        --label)   LABEL="$2"; shift 2 ;;
        --search)  SEARCH="$2"; shift 2 ;;
        --repo)    REPO="$2"; shift 2 ;;
        *)         echo "Unknown option: $1" >&2; usage 1 ;;
    esac
done

case "$STATE" in
    open|closed|all) ;;
    *) echo "Error: --state must be open, closed, or all (got: $STATE)" >&2; exit 1 ;;
esac
case "$LIMIT" in
    ''|*[!0-9]*) echo "Error: --limit must be a positive integer (got: $LIMIT)" >&2; exit 1 ;;
esac
if [[ "$LIMIT" -lt 1 ]]; then
    echo "Error: --limit must be at least 1 (got: $LIMIT)" >&2
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

ARGS=(--repo "$REPO" --state "$STATE" --limit "$LIMIT" --json number,title,labels,createdAt)
if [[ -n "$LABEL" ]]; then ARGS+=(--label "$LABEL"); fi
if [[ -n "$SEARCH" ]]; then ARGS+=(--search "$SEARCH"); fi

DATA=$(gh issue list "${ARGS[@]}")
COUNT=$(echo "$DATA" | jq 'length')

echo "# Issues in $REPO (state: $STATE, max: $LIMIT)"
echo
if [[ "$COUNT" -eq 0 ]]; then
    echo "No issues found."
    exit 0
fi
echo "| # | Title | Labels | Created |"
echo "|---|-------|--------|---------|"
echo "$DATA" | jq -r '.[] | "| " + (.number|tostring) + " | " + (.title|gsub("\\|";"\\|")) + " | " + ([.labels[].name]|join(", ")) + " | " + .createdAt[:10] + " |"'
