# Dev Container Setup

This dev container provides a Python 3.14 + Node.js environment with the
[pi.dev](https://pi.dev) coding agent and [GitHub CLI](https://cli.github.com/).

## First-time setup

### 1. SSH agent forwarding

The container forwards your host's SSH agent for git auth and commit signing.
Make sure an agent is running on the host with your key loaded:

```bash
eval "$(ssh-agent -s)"
ssh-add          # adds default keys (~/.ssh/id_*)
ssh-add -l       # verify your key is listed
```

On macOS the agent typically runs by default. On Linux start it as shown above
and add the `ssh-agent` / `ssh-add` lines to `~/.bash_profile` or `~/.zprofile`.

> **Security key (ED25519-SK) users:** FIDO security keys require physical
> presence and do not work through forwarded agents. Use a regular ED25519 or
> RSA key for container git operations.

### 2. Git email

Copy the example env file and set your email:

```bash
cp .env.example .env
```

Then edit `.env` and set `DEVCONTAINER_GIT_EMAIL` to your GitHub
noreply address (e.g. `1845727+username@users.noreply.github.com`). This avoids
GitHub's email-privacy push rejection.

### 3. GitHub CLI authentication

After the container starts, authenticate `gh` with a fine-grained PAT:

```bash
gh auth login --with-token <<< your_pat_token
```

Generate a token at <https://github.com/settings/personal-access-tokens>:
**Fine-grained** → scope to this repo → **Contents: Read**, **Pull requests:
Read and write**.

The token is stored in a named volume (`gh-config`) and survives rebuilds.

## How it works

| Piece | Purpose |
|---|---|
| `.devcontainer/.env` | Your git email (gitignored, loaded via `runArgs`) |
| `setup-volume-mounts.sh` | Fixes root ownership on named volumes |
| `setup-git-signing.sh` | Seeds `~/.config/git/config` with SSH signing |
| `gh-config` volume | Persists `gh` auth across rebuilds |
| `git-config` volume | Persists signing config across rebuilds |

The `postCreateCommand` runs `setup-volume-mounts.sh` then
`setup-git-signing.sh` on every container create. Both are idempotent — they
skip work if the target is already correct.