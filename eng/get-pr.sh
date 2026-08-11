#!/usr/bin/env bash
#
# get-pr.sh — Fetch a GitHub PR by number and print it as markdown.
#
# Usage:
#   eng/get-pr.sh PR_NUMBER [--repo REPO]
#
# Options:
#   --repo REPO   Override repo (default: njurgens/digital-frame)
#   --help       Show this help text
#
# Example:
#   eng/get-pr.sh 1
#   eng/get-pr.sh 1 --repo other/repo
#
set -euo pipefail

REPO="${PIFRAME_GH_REPO:-njurgens/digital-frame}"
PR_NUM=""

usage() {
    sed -n '2,11p' "$0" | sed 's/^# \?//'
    exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help)  usage ;;
        --repo)  REPO="$2"; shift 2 ;;
        *)
            if [[ -z "$PR_NUM" ]]; then
                PR_NUM="$1"
            else
                echo "Unknown option: $1" >&2
                usage 1
            fi
            shift
            ;;
    esac
done

if [[ -z "$PR_NUM" ]]; then
    echo "Error: PR number is required" >&2
    usage 1
fi

# Fetch PR data as JSON
DATA=$(gh pr view "$PR_NUM" --repo "$REPO" --json title,state,body,labels,headRefName,baseRefName,createdAt,closedAt,mergedAt,reviewComments,comments)

# Extract fields
TITLE=$(echo "$DATA" | jq -r '.title')
STATE=$(echo "$DATA" | jq -r '.state')
HEAD=$(echo "$DATA" | jq -r '.headRefName')
BASE=$(echo "$DATA" | jq -r '.baseRefName')
BODY=$(echo "$DATA" | jq -r '.body')
CREATED=$(echo "$DATA" | jq -r '.createdAt')
CLOSED=$(echo "$DATA" | jq -r '.closedAt // empty')
MERGED=$(echo "$DATA" | jq -r '.mergedAt // empty')
LABELS=$(echo "$DATA" | jq -r '.labels[].name' | paste -sd ', ' -)
COMMENT_COUNT=$(echo "$DATA" | jq '.reviewComments | length')
ISSUE_COMMENTS=$(echo "$DATA" | jq '.comments | length')

# Print as markdown
echo "# $TITLE"
echo ""
echo "| Field | Value |"
echo "|-------|-------|"
echo "| State | $STATE |"
if [[ -n "$LABELS" ]]; then
    echo "| Labels | $LABELS |"
fi
echo "| Branch | $HEAD -> $BASE |"
echo "| Created | $CREATED |"
if [[ -n "$CLOSED" ]]; then
    echo "| Closed | $CLOSED |"
fi
if [[ -n "$MERGED" ]]; then
    echo "| Merged | $MERGED |"
fi
echo "| Review comments | $COMMENT_COUNT |"
echo "| Issue comments | $ISSUE_COMMENTS |"
echo "| Repo | $REPO |"
echo ""
echo "---"
echo ""
echo "$BODY"