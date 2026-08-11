#!/usr/bin/env bash
#
# create-pr.sh — Create a GitHub pull request from the current branch.
#
# Usage:
#   eng/create-pr.sh --title "TITLE" --body-file FILE [--label L1] [--label L2] [--reviewer USER] ...
#
# Options:
#   --title TITLE       PR title (required)
#   --body-file FILE    Path to markdown file with PR body (required)
#   --label LABEL       Add a label (may be repeated; optional)
#   --reviewer USER     Request a reviewer (may be repeated; optional)
#   --repo REPO         Override repo (default: njurgens/digital-frame)
#   --base BRANCH       Override base branch (default: main)
#   --help              Show this help text
#
# Example:
#   eng/create-pr.sh \
#     --title "feat: add dependency injection framework" \
#     --body-file docs/pr-body.md \
#     --label enhancement \
#     --reviewer njurgens
#
set -euo pipefail

REPO="${PIFRAME_GH_REPO:-njurgens/digital-frame}"
BASE="${PIFRAME_BASE_BRANCH:-main}"
TITLE=""
BODY_FILE=""
LABELS=()
REVIEWERS=()

usage() {
    sed -n '2,16p' "$0" | sed 's/^# \?//'
    exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help)      usage ;;
        --title)     TITLE="$2"; shift 2 ;;
        --body-file) BODY_FILE="$2"; shift 2 ;;
        --label)     LABELS+=("$2"); shift 2 ;;
        --reviewer)  REVIEWERS+=("$2"); shift 2 ;;
        --repo)      REPO="$2"; shift 2 ;;
        --base)      BASE="$2"; shift 2 ;;
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

# Detect current branch
BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo "")
if [[ -z "$BRANCH" ]]; then
    echo "Error: could not detect current branch" >&2
    exit 1
fi

# Build the gh command
CMD=(gh pr create --repo "$REPO" --base "$BASE" --title "$TITLE" --body-file "$BODY_FILE")
for lbl in "${LABELS[@]+"${LABELS[@]}"}"; do
    CMD+=(--label "$lbl")
done
for rev in "${REVIEWERS[@]+"${REVIEWERS[@]}"}"; do
    CMD+=(--reviewer "$rev")
done

echo "Creating PR in $REPO: $TITLE ($BRANCH -> $BASE)" >&2
"${CMD[@]}"