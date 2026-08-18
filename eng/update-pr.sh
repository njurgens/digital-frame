#!/usr/bin/env bash
#
# update-pr.sh — Edit a GitHub PR description.
#
# Usage:
#   eng/update-pr.sh PR_NUMBER --body-file FILE [--add-label L] [--remove-label L] ...
#
# Options:
#   --body-file FILE     Replace PR body with contents of file (optional)
#   --title TITLE        Replace PR title (optional)
#   --add-label LABEL    Add a label (may be repeated; optional)
#   --remove-label LABEL Remove a label (may be repeated; optional)
#   --repo REPO          Override repo (default: njurgens/digital-frame)
#   --help               Show this help text
#
# Example:
#   eng/update-pr.sh 1 --body-file updated-body.md --add-label enhancement
#
set -euo pipefail

REPO="${PIFRAME_GH_REPO:-njurgens/digital-frame}"
PR_NUM=""
BODY_FILE=""
TITLE=""
ADD_LABELS=()
REMOVE_LABELS=()

usage() {
    sed -n '2,14p' "$0" | sed 's/^# \?//'
    exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help)         usage ;;
        --body-file)    BODY_FILE="$2"; shift 2 ;;
        --title)        TITLE="$2"; shift 2 ;;
        --add-label)    ADD_LABELS+=("$2"); shift 2 ;;
        --remove-label) REMOVE_LABELS+=("$2"); shift 2 ;;
        --repo)         REPO="$2"; shift 2 ;;
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

# Build the gh command
CMD=(gh pr edit "$PR_NUM" --repo "$REPO")

if [[ -n "$TITLE" ]]; then
    CMD+=(--title "$TITLE")
fi

if [[ -n "$BODY_FILE" ]]; then
    if [[ ! -f "$BODY_FILE" ]]; then
        echo "Error: body file not found: $BODY_FILE" >&2
        exit 1
    fi
    # A body replacement must keep the AI-attribution trailer (AGENTS.md).
    if ! grep -qiE '^[[:space:]]*co-authored-by:' "$BODY_FILE"; then
        echo "Error: $BODY_FILE must include a 'Co-Authored-By:' trailer line" >&2
        echo "       (AI attribution, see AGENTS.md), e.g.:" >&2
        echo "       Co-Authored-By: <model> (<agent>) <email>" >&2
        exit 1
    fi
    CMD+=(--body-file "$BODY_FILE")
fi

for lbl in "${ADD_LABELS[@]+"${ADD_LABELS[@]}"}"; do
    CMD+=(--add-label "$lbl")
done

for lbl in "${REMOVE_LABELS[@]+"${REMOVE_LABELS[@]}"}"; do
    CMD+=(--remove-label "$lbl")
done

# Require at least one edit option
if [[ -z "$TITLE" && -z "$BODY_FILE" && ${#ADD_LABELS[@]} -eq 0 && ${#REMOVE_LABELS[@]} -eq 0 ]]; then
    echo "Error: at least one of --title, --body-file, --add-label, or --remove-label is required" >&2
    usage 1
fi

echo "Editing PR #$PR_NUM in $REPO" >&2
"${CMD[@]}"