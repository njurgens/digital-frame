#!/usr/bin/env bash
#
# create-worktree.sh — Create a new feature worktree under features/.
#
# Usage:
#   create-worktree.sh <feature-slag>
#
# What it does:
#   1. Pulls the latest main branch from origin
#   2. Creates a git worktree at features/<feature-slug> from main
#   3. Symlinks .devcontainer/.env -> ../../../.env (repo root .env)
#
# Run from the main/ directory (the git repo root).
#
set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <feature-slug>" >&2
    echo "  Example: $0 my-new-feature" >&2
    exit 1
fi

SLUG="$1"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKTREE_DIR="${REPO_ROOT}/../features/${SLUG}"

# Validate slug doesn't already exist
if [[ -e "$WORKTREE_DIR" ]]; then
    echo "Error: '${WORKTREE_DIR}' already exists." >&2
    exit 1
fi

# Check for worktree with same name
if git worktree list | grep -q "${SLUG}"; then
    echo "Error: a worktree named '${SLUG}' already exists." >&2
    exit 1
fi

# Ensure we're on main
git checkout main

# Pull latest main
echo "==> Pulling latest main ..."
git pull origin main

# Create the worktree on a new branch from main
echo "==> Creating worktree at ${WORKTREE_DIR} ..."
git worktree add -b "${SLUG}" "${WORKTREE_DIR}" main

# Create .devcontainer/.env symlink -> repo root .env
ENV_TARGET="${WORKTREE_DIR}/.devcontainer/.env"
echo "==> Symlinking ${ENV_TARGET} -> ../../../.env ..."
ln -s ../../../.env "${ENV_TARGET}"

echo ""
echo "==> Worktree ready at: ${WORKTREE_DIR}"
echo "==> Run: cd ${WORKTREE_DIR}"