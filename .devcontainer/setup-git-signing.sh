#!/usr/bin/env bash
# Sets up git commit signing using SSH agent forwarding.
# Usage: ./setup-git-signing.sh <email>
#
# Discovers the SSH key from the agent and writes signing config to
# ~/.config/git/config so it persists across container rebuilds and
# doesn't conflict with the extension's ~/.gitconfig copy.
set -euo pipefail

EMAIL="${1:?Usage: $0 <email>}"

# Discover the first SSH key from the agent (key type + public key)
SSH_KEY=$(ssh-add -L | head -1) || { echo "error: no SSH keys in agent" >&2; exit 1; }

GITRC="$HOME/.config/git/config"

# Set config only if file doesn't exist (idempotent across rebuilds)
if [ ! -f "$GITRC" ]; then
  mkdir -p "$HOME/.config/git"
  git -c config.file="$GITRC" config --local user.email "$EMAIL"
  git -c config.file="$GITRC" config --local gpg.format ssh
  git -c config.file="$GITRC" config --local commit.gpgsign true
  git -c config.file="$GITRC" config --local user.signingkey "$SSH_KEY"
  echo "wrote $GITRC"
else
  echo "$GITRC already exists, skipping"
fi