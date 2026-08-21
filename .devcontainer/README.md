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

### 2. Git email

Copy the example env file and set your email:

```bash
cp .devcontainer/.env.example .devcontainer/.env
```

Then edit `.devcontainer/.env` and set `DEVCONTAINER_GIT_EMAIL` to your GitHub
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

## Running against a OneDrive share

To play a OneDrive shared folder, set the provider and share in
`.devcontainer/.env` (the template is `.devcontainer/.env.example`):

```bash
PIFRAME_SYNC__PROVIDER=onedrive
PIFRAME_SYNC__ONEDRIVE__SHARE_URL=https://1drv.ms/f/...
# Only for password-protected shares:
# PIFRAME_SYNC__ONEDRIVE__PASSWORD=...
```

Then start the app:

```bash
bash eng/run.sh
```

Photos are downloaded to `~/.cache/piframe/onedrive` (the devcontainer
default in `config.devcontainer.toml`). A missing or empty share URL fails
the first sync with a clear "No OneDrive share URL configured" error — check
the run log if the slideshow starts empty.