#!/usr/bin/env bash
#
# create-issue.sh — Create a GitHub issue from a markdown file.
#
# Usage:
#   eng/create-issue.sh --title "TITLE" --body-file FILE [--label L1] [--label L2] ...
#
# Options:
#   --title TITLE       Issue title (required)
#   --body-file FILE    Path to markdown file with issue body (required)
#   --label LABEL       Add a label (may be repeated; optional).
#                       Labels that don't exist on the repo are skipped with a warning.
#   --repo REPO         Override repo (default: njurgens/digital-frame)
#   --help              Show this help text
#
# Example:
#   eng/create-issue.sh \
#     --title "feat: add dependency injection framework" \
#     --body-file docs/proposed-issues.md \
#     --label enhancement
#
set -euo pipefail

REPO="${PIFRAME_GH_REPO:-njurgens/digital-frame}"
TITLE=""
BODY_FILE=""
LABELS=()

usage() {
    sed -n '2,12p' "$0" | sed 's/^# \?//'
    exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help)      usage ;;
        --title)     TITLE="$2"; shift 2 ;;
        --body-file) BODY_FILE="$2"; shift 2 ;;
        --label)     LABELS+=("$2"); shift 2 ;;
        --repo)      REPO="$2"; shift 2 ;;
        *)           echo "Unknown option: $1" >&2; usage 1 ;;
    esac
done

if [[ -z "$TITLE" ]]; then
    echo "Error: --title is required" >&2
    usage 1
fi

if [[ -z "$BODY_FILE" ]]; then
    echo "Error: --body-file is required" >&2
    usage 1
fi

if [[ ! -f "$BODY_FILE" ]]; then
    echo "Error: body file not found: $BODY_FILE" >&2
    exit 1
fi

# Create the issue first (no labels yet)
echo "Creating issue in $REPO: $TITLE" >&2
ISSUE_URL=$(gh issue create --repo "$REPO" --title "$TITLE" --body-file "$BODY_FILE")
ISSUE_NUM=$(echo "$ISSUE_URL" | grep -oP '\d+$')

# Add labels one by one, skipping any that don't exist
if [[ ${#LABELS[@]} -gt 0 ]]; then
    AVAILABLE=$(gh label list --repo "$REPO" --json name --jq '.[].name' 2>/dev/null || true)
    for lbl in "${LABELS[@]}"; do
        if echo "$AVAILABLE" | grep -qx "$lbl"; then
            gh issue edit "$ISSUE_NUM" --repo "$REPO" --add-label "$lbl" >&2
        else
            echo "Warning: label '$lbl' not found on $REPO, skipping" >&2
        fi
    done
fi

echo "$ISSUE_URL"