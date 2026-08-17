#!/usr/bin/env bash
#
# make-review-diff.sh — produce the review artifacts that peer reviewers read.
#
# Reviewers have no shell. Everything they need must exist as a file they can
# open with the `read` tool. This script writes those files.
#
# Usage:
#   .agents/skills/code-review/scripts/make-review-diff.sh [options]
#
# Options:
#   --base <ref>      Parent branch to diff against. Default: first of
#                     main, origin/main, master, origin/master that exists.
#   --out-dir <dir>   Where to write artifacts. Default: .pi/tmp/peer-review
#   --committed       Diff only committed work (MERGE_BASE..HEAD). Default is
#                     to include staged and unstaged working-tree changes.
#   --no-untracked    Do not append new untracked files to the diff.
#   -h, --help        Show this help.
#
# Writes:
#   <out-dir>/review.diff          unified diff vs the merge base
#   <out-dir>/changed-files.txt    one path per line
#   <out-dir>/commits.txt          commit subjects and bodies since merge base
#   <out-dir>/diffstat.txt         summary of insertions/deletions per file
#
# Prints a KEY=VALUE block to stdout for the orchestrator to read.
#
# Exit codes:
#   0  artifacts written, there is something to review
#   1  error (not a git repo, base ref not found, etc.)
#   2  no changes found vs the merge base — nothing to review

set -euo pipefail

BASE_REF=""
OUT_DIR=""
COMMITTED_ONLY=0
INCLUDE_UNTRACKED=1
MAX_UNTRACKED_BYTES=$((1024 * 1024))

die() { printf 'make-review-diff: %s\n' "$1" >&2; exit 1; }

usage() { sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

while [ $# -gt 0 ]; do
  case "$1" in
    --base)         [ $# -ge 2 ] || die "--base needs a value"; BASE_REF="$2"; shift 2 ;;
    --out-dir)      [ $# -ge 2 ] || die "--out-dir needs a value"; OUT_DIR="$2"; shift 2 ;;
    --committed)    COMMITTED_ONLY=1; shift ;;
    --no-untracked) INCLUDE_UNTRACKED=0; shift ;;
    -h|--help)      usage ;;
    *)              die "unknown option: $1 (try --help)" ;;
  esac
done

command -v git >/dev/null 2>&1 || die "git not found on PATH"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || die "not inside a git work tree"

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

git rev-parse --verify -q HEAD >/dev/null \
  || die "HEAD does not resolve — the repository has no commits yet"

# --- resolve the base ref -----------------------------------------------------
if [ -n "$BASE_REF" ]; then
  git rev-parse --verify -q "$BASE_REF" >/dev/null \
    || die "base ref '$BASE_REF' not found"
else
  for candidate in main origin/main master origin/master; do
    if git rev-parse --verify -q "$candidate" >/dev/null; then
      BASE_REF="$candidate"
      break
    fi
  done
  [ -n "$BASE_REF" ] \
    || die "no default base branch found (looked for main, origin/main, master, origin/master); pass --base <ref>"
fi

MERGE_BASE="$(git merge-base "$BASE_REF" HEAD 2>/dev/null)" \
  || die "no common ancestor between '$BASE_REF' and HEAD"

# --- prepare the output directory --------------------------------------------
[ -n "$OUT_DIR" ] || OUT_DIR=".pi/tmp/peer-review"
mkdir -p "$OUT_DIR"

# Reviewers are given absolute paths, so resolve OUT_DIR now. An out-dir that is
# already absolute must not be re-rooted under the repo.
ABS_OUT_DIR="$(cd "$OUT_DIR" && pwd)"

# Keep review artifacts out of the next round's diff. Without this, round 2
# reviews round 1's diff file as if it were part of the change.
PARENT_DIR="$(dirname "$OUT_DIR")"
if [ "$PARENT_DIR" != "." ] && [ ! -e "$PARENT_DIR/.gitignore" ]; then
  printf '*\n' > "$PARENT_DIR/.gitignore"
fi
[ -e "$OUT_DIR/.gitignore" ] || printf '*\n' > "$OUT_DIR/.gitignore"

DIFF_FILE="$OUT_DIR/review.diff"
FILES_FILE="$OUT_DIR/changed-files.txt"
COMMITS_FILE="$OUT_DIR/commits.txt"
STAT_FILE="$OUT_DIR/diffstat.txt"

# --- build the diff -----------------------------------------------------------
# `git diff <merge-base>` compares the working tree to the merge base, so it
# picks up committed, staged, and unstaged changes together. `--committed`
# narrows it to what is actually committed.
if [ "$COMMITTED_ONLY" -eq 1 ]; then
  DIFF_RANGE=("$MERGE_BASE" "HEAD")
else
  DIFF_RANGE=("$MERGE_BASE")
fi

git --no-pager diff --no-color --no-ext-diff -M "${DIFF_RANGE[@]}" > "$DIFF_FILE"
git --no-pager diff --no-color --no-ext-diff -M --stat "${DIFF_RANGE[@]}" > "$STAT_FILE"
git --no-pager diff --no-color --no-ext-diff -M --name-only "${DIFF_RANGE[@]}" > "$FILES_FILE"

# --- append untracked files ---------------------------------------------------
# A brand-new file the author never staged is invisible to `git diff`. Left out,
# every reviewer silently reviews a change with its most important file missing.
UNTRACKED_COUNT=0
UNTRACKED_SKIPPED=0
if [ "$INCLUDE_UNTRACKED" -eq 1 ] && [ "$COMMITTED_ONLY" -eq 0 ]; then
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    [ -f "$f" ] || continue
    size=$(wc -c < "$f" | tr -d ' ')
    if [ "$size" -gt "$MAX_UNTRACKED_BYTES" ]; then
      UNTRACKED_SKIPPED=$((UNTRACKED_SKIPPED + 1))
      printf '%s\t[SKIPPED: untracked file larger than 1 MB]\n' "$f" >> "$FILES_FILE"
      continue
    fi
    git --no-pager diff --no-color --no-ext-diff --no-index -- /dev/null "$f" >> "$DIFF_FILE" || true
    printf '%s\n' "$f" >> "$FILES_FILE"
    UNTRACKED_COUNT=$((UNTRACKED_COUNT + 1))
  done < <(git ls-files --others --exclude-standard)
fi

# --- commit log ---------------------------------------------------------------
# The technical-communication reviewer needs the commit messages, and cannot
# run `git log` to get them.
git --no-pager log --no-color --no-merges \
    --format='commit %h%nauthor %an%ndate   %ad%n%n%s%n%n%b%n----------------------------------------' \
    --date=short "$MERGE_BASE..HEAD" > "$COMMITS_FILE"

# --- report -------------------------------------------------------------------
DIFF_LINES=$(wc -l < "$DIFF_FILE" | tr -d ' ')
FILES_CHANGED=$(grep -c . "$FILES_FILE" || true)
COMMIT_COUNT=$(git rev-list --no-merges --count "$MERGE_BASE..HEAD")

printf 'REPO_ROOT=%s\n'            "$REPO_ROOT"
printf 'BASE_REF=%s\n'             "$BASE_REF"
printf 'MERGE_BASE=%s\n'           "$MERGE_BASE"
printf 'DIFF_FILE=%s\n'            "$ABS_OUT_DIR/review.diff"
printf 'CHANGED_FILES_FILE=%s\n'   "$ABS_OUT_DIR/changed-files.txt"
printf 'COMMITS_FILE=%s\n'         "$ABS_OUT_DIR/commits.txt"
printf 'DIFFSTAT_FILE=%s\n'        "$ABS_OUT_DIR/diffstat.txt"
printf 'FILES_CHANGED=%s\n'        "$FILES_CHANGED"
printf 'DIFF_LINES=%s\n'           "$DIFF_LINES"
printf 'COMMIT_COUNT=%s\n'         "$COMMIT_COUNT"
printf 'UNTRACKED_INCLUDED=%s\n'   "$UNTRACKED_COUNT"
printf 'UNTRACKED_SKIPPED=%s\n'    "$UNTRACKED_SKIPPED"

if [ "$DIFF_LINES" -eq 0 ]; then
  printf 'STATUS=EMPTY\n'
  exit 2
fi

printf 'STATUS=OK\n'
exit 0
