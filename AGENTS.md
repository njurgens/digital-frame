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
# Deploy from repo root (dev machine → Pi via bash/scp/ssh — no rsync on Windows):
bash install.sh
```

`install.sh` does everything: scp files, apt packages, sudoers, systemd units, and patches `/etc/xdg/labwc/autostart`. It is idempotent — safe to re-run.

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
ssh frame@10.1.7.58 'XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 python3 /home/frame/framesync/slideshow.py > /tmp/slideshow.log 2>&1 &'

# Kill + restart in one line
ssh frame@10.1.7.58 'kill -9 $(cat /tmp/slideshow.pid); sleep 1; XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 python3 /home/frame/framesync/slideshow.py > /tmp/slideshow.log 2>&1 &'
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
