# Pi Frame — Agent Instructions

## Working in Git Worktrees

All issue work must be done in a dedicated git worktree.

### Create a worktree for an issue

```bash
bash eng/create-worktree.sh <feature-slug>
```

### List and remove worktrees

```bash
git worktree list                                    # see all active worktrees
git worktree remove ../features/<feature-slug>      # clean up after merge
```

Remove the worktree only after the PR is merged. If the branch was deleted remotely, pass `--force`.

> If `gh` or git operations fail inside the dev container, see [`.devcontainer/README.md`](.devcontainer/README.md) for setup (SSH agent, `.env`, `gh auth login`).

---

## Issue & PR Management

| Task | Script |
|------|--------|
| Create issue | `eng/create-issue.sh --title "..." --body-file FILE [--label L]` |
| Get issue | `eng/get-issue.sh ISSUE_NUMBER` |
| Create PR | `eng/create-pr.sh --title "..." --body-file FILE [--reviewer U]` |
| Get PR | `eng/get-pr.sh PR_NUMBER` |
| Update PR | `eng/update-pr.sh PR_NUMBER --body-file FILE` |

See each script's `--help` for full usage.

---

# Copilot Instructions

## Documentation Lookup

Load the `context7-docs` skill whenever a question involves a specific library, framework, SDK, CLI tool, or cloud service. Use it even when you think you know the answer — training data may not reflect recent API changes.

## Target Environment

- **Hardware:** Raspberry Pi 3A+, 512MB RAM, VideoCore IV GPU (vc4, OpenGL ES 2.0 / GL 2.1 only)
- **OS:** Raspberry Pi OS Bookworm (Debian trixie), aarch64, Wayland/labwc compositor
- **Pi SSH:** `frame@10.1.7.58` — all commands that touch the Pi run over SSH
- **Pi user:** `frame` (uid 1000); slideshow.py and framesync both run as this user

## Architecture

```
[OneDrive] ──sync──> framesync.service (oneshot, hourly timer)
                          │
                          ▼
               /home/frame/Pictures/slideshow/
                          │
                          ▼
               slideshow.py (pygame, fullscreen, Wayland)
               launched by /etc/xdg/labwc/autostart
               PID written to /tmp/slideshow.pid
```

- **slideshow.py** is a self-contained pygame app. It runs fullscreen under labwc via `/etc/xdg/labwc/autostart`. Not managed by systemd. Rescans the image directory at the start of each cycle — new synced images appear automatically without restarting.
- **framesync.py** syncs from a password-protected OneDrive shared folder using Microsoft's "Badger" token API (not OAuth). No IPC to the slideshow — sync is fire-and-forget.
- **config.toml** holds secrets and is never committed. `config.toml.example` is the template.

## Deployment

```bash
# Deploy from repo root:
bash eng/install.sh
```

`eng/install.sh` does everything: rsyncs the repo to the Pi, installs apt packages, writes sudoers rules, disables retired systemd units, and patches `/etc/xdg/labwc/autostart`. It is idempotent — safe to re-run.

After deploy, reboot for autostart changes to take effect:
```bash
ssh frame@10.1.7.58 'sudo reboot now'
```

Manually trigger a sync (without waiting for the timer):
```bash
ssh frame@10.1.7.58 'sudo systemctl start framesync.service'
```

## Python Dependencies — uv managed

All Python packages are managed by uv via `pyproject.toml` and `uv.lock`.
`eng/install.sh` runs `uv sync --frozen` on the Pi, which installs a managed
Python 3.13 (from python-build-standalone) and creates `.venv`.

- `.python-version` pins 3.13 — matches on both Pi and devcontainer
- `uv.lock` is committed — deterministic deployments
- No apt Python packages needed — all have aarch64 wheels
- `pygame` has cp313 aarch64 wheels but not cp314 — hence the 3.13 pin

## Dev workflow

```bash
bash eng/sync.sh            # one-time: create .venv, install deps
bash eng/format.sh          # auto-format code (ruff)
bash eng/check.sh           # lint + format check
bash eng/test.sh            # run tests
bash eng/test.sh -k foo     # filter tests
bash eng/run.sh             # run slideshow locally (needs display)
bash eng/install.sh         # deploy to Pi
```

Agents should always use the `eng/` scripts rather than invoking uv directly.

## Killing / Restarting the Slideshow

slideshow.py writes its PID to `/tmp/slideshow.pid` on startup.

```bash
# Kill (returns immediately — do NOT use pgrep -f, it matches the SSH command itself)
ssh frame@10.1.7.58 'kill -9 $(cat /tmp/slideshow.pid)'

# Restart manually (for testing without a reboot)
ssh frame@10.1.7.58 'XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 /home/frame/digital-frame/.venv/bin/slideshow > /tmp/slideshow.log 2>&1 &'

# Kill + restart in one line
ssh frame@10.1.7.58 'kill -9 $(cat /tmp/slideshow.pid); sleep 1; XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 /home/frame/digital-frame/.venv/bin/slideshow > /tmp/slideshow.log 2>&1 &'
```

**Do NOT use `pkill -f slideshow.py` or `pgrep -f slideshow.py`** — the `-f` flag matches against the full command line, which includes the SSH command string itself, causing the SSH session to kill itself and hang.

## Key Conventions

- **uv-managed Python 3.13.** Python scripts run from `.venv/bin/`. The venv is created by `uv sync` on deploy. No apt Python packages.
- **framesync.py logs to stdout/stderr** — captured by journald via `StandardOutput=journal`. Keep log lines concise; they show up in `journalctl -u framesync`.
- **sync_folder() is destructive** — it deletes local files not present in the remote folder.
- **install.sh uses a bash heredoc to run Python as root on the Pi.** The heredoc is unquoted (`<<EOF`), so Python raw strings (`r'...'`) and backslash sequences are mangled by bash. Avoid them inside the heredoc — use plain string logic instead.
- **Wayland env vars for slideshow:** When launching slideshow.py over SSH (e.g. for testing), prefix with `XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0`.
- **Cache versioning:** `slideshow.py` caches composited surfaces to `/home/frame/.cache/framesync/`. Cache key includes `_CACHE_VERSION`. Bump this constant whenever the rendering pipeline changes so stale entries are ignored.

## Debugging

```bash
ssh frame@10.1.7.58 'journalctl -u framesync -n 30 --no-pager'  # sync logs
ssh frame@10.1.7.58 'cat /tmp/slideshow.log'                     # slideshow logs (if manually launched)
ssh frame@10.1.7.58 'cat /tmp/slideshow.pid'                     # slideshow PID
ssh frame@10.1.7.58 'ls /home/frame/.cache/framesync/'           # surface cache
ssh frame@10.1.7.58 'cat /etc/xdg/labwc/autostart'              # autostart config
```
