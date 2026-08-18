#!/usr/bin/env bash
#
# get-issue.sh — Fetch a GitHub issue by number and print it as markdown.
#
# Usage:
#   get-issue.sh ISSUE_NUMBER [--repo REPO]
#
# Options:
#   --repo REPO   Override repo (default: njurgens/digital-frame)
#   --help       Show this help text
#
# Example:
#   get-issue.sh 42
#   get-issue.sh 42 --repo other/repo
#
set -euo pipefail

REPO="${PIFRAME_GH_REPO:-njurgens/digital-frame}"
ISSUE_NUM=""

usage() {
    sed -n '2,11p' "$0" | sed 's/^# \?//'
    exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help)  usage ;;
        --repo)  REPO="$2"; shift 2 ;;
        *)
            if [[ -z "$ISSUE_NUM" ]]; then
                ISSUE_NUM="$1"
            else
                echo "Unknown option: $1" >&2
                usage 1
            fi
            shift
            ;;
    esac
done

if [[ -z "$ISSUE_NUM" ]]; then
    echo "Error: issue number is required" >&2
    usage 1
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

# Fetch issue data as JSON
DATA=$(gh issue view "$ISSUE_NUM" --repo "$REPO" --json title,state,labels,body,comments,createdAt,closedAt)

# Extract fields
TITLE=$(echo "$DATA" | jq -r '.title')
STATE=$(echo "$DATA" | jq -r '.state')
BODY=$(echo "$DATA" | jq -r '.body')
CREATED=$(echo "$DATA" | jq -r '.createdAt')
CLOSED=$(echo "$DATA" | jq -r '.closedAt // empty')
LABELS=$(echo "$DATA" | jq -r '.labels[].name' | paste -sd ', ' -)
COMMENT_COUNT=$(echo "$DATA" | jq '.comments | length')

# Print as markdown
echo "# $TITLE"
echo ""
echo "| Field | Value |"
echo "|-------|-------|"
echo "| State | $STATE |"
if [[ -n "$LABELS" ]]; then
    echo "| Labels | $LABELS |"
fi
echo "| Created | $CREATED |"
if [[ -n "$CLOSED" ]]; then
    echo "| Closed | $CLOSED |"
fi
echo "| Comments | $COMMENT_COUNT |"
echo "| Repo | $REPO |"
echo ""
echo "---"
echo ""
echo "$BODY"