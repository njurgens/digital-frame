# Pi Frame — Agent Instructions

Pi Frame is a self-contained digital photo frame app: it syncs photos from
an **album provider** (OneDrive, a local directory, or a Google Photos stub),
caches them, and plays a fullscreen slideshow on a Raspberry Pi 3A+ under
Wayland/labwc. The device is described in [docs/hardware.md](docs/hardware.md)
(including SSH access); the authoritative design docs are
[docs/pi-frame-lld.md](docs/pi-frame-lld.md) (LLD),
[docs/pi-frame-hld.md](docs/pi-frame-hld.md) (HLD), and
[docs/album-providers.md](docs/album-providers.md) (provider guide).

## Commands

```bash
bash eng/sync.sh            # one-time: create .venv, install deps
bash eng/format.sh          # auto-format code (ruff)
bash eng/check.sh           # lint + format check + type check
bash eng/test.sh            # run tests (90% diff-coverage gate)
bash eng/test.sh -k foo     # filter tests
bash eng/run.sh             # run the app in the devcontainer: background (default),
                            #   -f for foreground, --kill to stop
bash eng/install.sh         # deploy to the Pi (idempotent, safe to re-run)
```

Agents should always use the `eng/` scripts rather than invoking uv directly.

### Deploying and restarting on the Pi

The app runs as the `frame` user, launched from `/etc/xdg/labwc/autostart`
(not systemd). After a deploy, reboot for autostart changes to take effect:

```bash
ssh frame@10.1.7.58 'sudo reboot now'
```

Kill or restart without a reboot (the app writes its PID to
`/tmp/slideshow.pid`):

```bash
# Kill (returns immediately)
ssh frame@10.1.7.58 'kill -9 $(cat /tmp/slideshow.pid)'

# Restart manually (for testing)
ssh frame@10.1.7.58 'XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 /home/frame/digital-frame/.venv/bin/slideshow > /tmp/slideshow.log 2>&1 &'
```

**Do NOT use `pkill -f` or `pgrep -f` with "slideshow"** — the `-f` flag
matches the full command line, which includes the SSH command string itself,
so the SSH session kills itself and hangs.

### Debugging

```bash
ssh frame@10.1.7.58 'cat /tmp/slideshow.log'                 # app log (when manually launched)
ssh frame@10.1.7.58 'cat /tmp/slideshow.pid'                 # app PID
ssh frame@10.1.7.58 'ls /home/frame/.cache/piframe/surfaces/'  # surface cache
ssh frame@10.1.7.58 'cat /etc/xdg/labwc/autostart'           # autostart config
```

## Project structure

- `src/piframe/` — the app: `app.py` (entry point), `slideshow_player.py`,
  `photo_cache.py`, `config_store.py`, and `providers/` (the album
  providers — see docs/album-providers.md)
- `tests/` — pytest suite; `eng/` — the scripts above; `eng/fixtures/` —
  one-off tools that build the test image set (see docs/stock-images.md)
- `docs/` — public documentation: LLD (authoritative design), HLD, UX
  requirements, album-providers guide, hardware target
- `.agents/` — agent config: `skills/`, `agents/`, and `prompts/` (prompt
  templates, e.g. `/create-issue` and `/dev-loop`; not auto-discovered by Pi —
  loaded via the `prompts` entry in `.pi/settings.json`)
- `.pi/` — `settings.json` (points prompt discovery at `.agents/prompts/`)
  and `tmp/` (scratch working directory for issue drafts and review artifacts)

## Conventions

- **uv-managed Python 3.13.** `.python-version` pins 3.13 (pygame has cp313
  aarch64 wheels but not cp314). Scripts run from `.venv/bin/`; no apt
  Python packages.
- **`config.toml` holds secrets and is never committed.** Only
  `src/config.toml` is gitignored; the tracked
  root `config.toml` and `config.toml.example` must never contain real
  credentials.
- **The surface cache is `~/.cache/piframe/surfaces`** (not configurable).
  Its key includes `_CACHE_VERSION` (photo_cache.py) — bump it whenever the
  rendering pipeline changes so stale entries are ignored.
- **The OneDrive provider does destructive cleanup** — it deletes cached
  files that no longer exist on the remote. Never point its `cache_dir` at a
  user-managed directory.
- **Wayland env vars for SSH launches:** prefix with
  `XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0`.
- **`eng/install.sh` patches system files as root** (sudoers, labwc
  autostart) — read the script before changing it.
- **`.pi/tmp/` is the scratch working directory** for agent artifacts (issue
  drafts, review outputs). Its contents are gitignored; the folder is kept by
  `.gitkeep`.
- **AI attribution.** Add a `Co-authored-by:` line to every commit message,
  PR, and GitHub issue you create, attributing the AI that did the work
  (e.g. `Co-authored-by: Pi (<model>) <email>`), so it is transparent
  that the work was AI-generated.

## Git & PR workflow

All issue work happens in a dedicated git worktree:

```bash
bash eng/create-worktree.sh <feature-slug>     # create
git worktree list                                # list
git worktree remove ../features/<feature-slug>  # remove after merge (--force if the branch is gone)
```

Remove the worktree only after the PR is merged.

Issues go through the `github-issues` skill; PRs go through the `eng/`
scripts (see each script's `--help`):

| Task | How |
|------|-----|
| Create, get, or list issues | Load the `github-issues` skill |
| Create PR | `eng/create-pr.sh --title "..." --body-file FILE [--reviewer U]` |
| Get PR | `eng/get-pr.sh PR_NUMBER` |
| Update PR | `eng/update-pr.sh PR_NUMBER --body-file FILE` |

The repo also ships a `code-review` skill (`.agents/skills/code-review/`)
for multi-domain peer review of a finished change.

To file an issue from a conversation, use the `github-issues` skill
(`.agents/skills/github-issues/`) — or just type `/create-issue`. It drafts
the issue in `.pi/tmp/`, peer-reviews the draft (technical-communication
domain), and files it with the skill's bundled `scripts/create-issue.sh`.

> If `gh` or git operations fail inside the dev container, see
> [`.devcontainer/README.md`](.devcontainer/README.md) for setup (SSH agent,
> `.env`, `gh auth login`).

## Documentation

For questions about specific libraries, frameworks, SDKs, or cloud
services, load the `context7-docs` skill (when available) rather than
trusting training data — APIs change.
