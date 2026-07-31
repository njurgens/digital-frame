#!/usr/bin/env bash
# Sets up git commit signing using SSH agent forwarding.
# Usage: ./eng/setup-git-signing.sh <email>
#
# Discovers the SSH key from the agent and writes signing config to
# ~/.config/git/config so it persists across container rebuilds and
# doesn't conflict with the extension's ~/.gitconfig copy.
set -euo pipefail

EMAIL="${1:?Usage: $0 <email>}"

# Discover the first SSH key from the agent (key type + public key)
SSH_KEY=$(ssh-add -L | head -1) || { echo "error: no SSH keys in agent" >&2; exit 1; }

GITRC_DIR="$HOME/.config/git"
GITRC="$GITRC_DIR/config"

mkdir -p "$GITRC_DIR"

# Write config only if file doesn't exist (idempotent across rebuilds)
if [ ! -f "$GITRC" ]; then
  cat > "$GITRC" <<EOF
[user]
  email = ${EMAIL}
[gpg]
  format = ssh
[commit]
  gpgsign = true
[user]
  signingkey = ${SSH_KEY}
EOF
  echo "wrote $GITRC"
else
  echo "$GITRC already exists, skipping"
fi