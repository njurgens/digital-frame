# Pi Frame — Agent Instructions

## Code Review Gauntlet

**All code changes must pass a five-round sequential review before merge.** Each round is handled by a dedicated sub-agent in `.claude/agents/`. The top-level agent resolves all critical, high, and medium findings between rounds and re-runs the reviewer until it signs off.

### Round order (must not be skipped or reordered)

| # | Agent | Focus |
|---|-------|-------|
| 1 | `review-architecture` | Adherence to UX requirements spec, HLD, and LLD — run first because it has the largest leverage on system correctness |
| 2 | `review-correctness` | Implementation correctness — logic errors, edge cases, concurrency, resource leaks |
| 3 | `review-security` | Credentials, TLS, subprocess injection, path traversal, secure defaults |
| 4 | `review-docs` | Accuracy and completeness of design docs, READMEs, comments, config examples |
| 5 | `review-testing` | Requirement-to-test mapping, test quality, coverage gaps |

### How to run the gauntlet

For each round in order:

1. Spawn the reviewer sub-agent with the diff or changed file list as context.
2. Read the report. Fix every **Critical** and **High** finding. Fix **Medium** findings unless there is a documented reason not to.
3. Re-run the same reviewer. Repeat until it signs off with `APPROVED` (no Critical/High/Medium findings) or `APPROVED WITH NOTES` (only Low findings remain).
4. Proceed to the next round.

A round is complete only when the reviewer signs off. Do not advance to the next round while the current reviewer is still `BLOCKED`.

### Gauntlet invocation example

```
# Round 1 — architecture (always first)
Agent(subagent_type="review-architecture", prompt="Review the changes on branch X against docs/pi-frame-ux-requirements.md, docs/pi-frame-hld.md, and docs/pi-frame-lld.md. Changed files: [list]. Produce the structured report.")

# Round 2 — correctness (after architecture signs off)
Agent(subagent_type="review-correctness", prompt="Review the changes on branch X for implementation correctness. Changed files: [list]. Produce the structured Correctness Review report.")

# Round 3 — security (after correctness signs off)
Agent(subagent_type="review-security", prompt="Review the changes on branch X for security issues. Changed files: [list]. Produce the structured Security Review report.")

# Round 4 — docs (after security signs off)
Agent(subagent_type="review-docs", prompt="Review the changes on branch X for documentation accuracy and completeness. Changed files: [list]. Produce the structured Documentation Review report.")

# Round 5 — testing (after docs signs off)
Agent(subagent_type="review-testing", prompt="Review the changes on branch X for test coverage and requirement mapping. Changed files: [list]. Produce the structured Testing Review report.")
```

---

# Copilot Instructions

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

## Python Dependencies — apt only, no pip/venv

All Python packages must be installed via `apt` (system packages), never pip or a virtualenv. The apt versions are pre-built for aarch64 and link against the correct system libraries (SDL2, libjpeg, etc.).

Current apt packages used by slideshow.py:
- `python3-pygame` — display, surfaces, blitting, event loop
- `python3-pil` — EXIF orientation correction on JPEG load

## Killing / Restarting the Slideshow

slideshow.py writes its PID to `/tmp/slideshow.pid` on startup.

```bash
# Kill (returns immediately — do NOT use pgrep -f, it matches the SSH command itself)
ssh frame@10.1.7.58 'kill -9 $(cat /tmp/slideshow.pid)'

# Restart manually (for testing without a reboot)
ssh frame@10.1.7.58 'XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 python3 /home/frame/digital-frame/slideshow.py > /tmp/slideshow.log 2>&1 &'

# Kill + restart in one line
ssh frame@10.1.7.58 'kill -9 $(cat /tmp/slideshow.pid); sleep 1; XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 python3 /home/frame/digital-frame/slideshow.py > /tmp/slideshow.log 2>&1 &'
```

**Do NOT use `pkill -f slideshow.py` or `pgrep -f slideshow.py`** — the `-f` flag matches against the full command line, which includes the SSH command string itself, causing the SSH session to kill itself and hang.

## Key Conventions

- **No venv, no pip.** Python scripts use system Python 3 (`/usr/bin/python3`). All packages installed via `apt`.
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
