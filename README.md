# Raspberry Pi Picture Frame — Setup & Debug Guide

## Architecture

```
[Photo source] ──sync──> album provider (OneDrive | local | Google stub)
                              |
                              v
                     Album (in-memory snapshot)
                              |
                              v
        slideshow.py (pygame, fullscreen, Wayland/labwc)
        launched by /etc/xdg/labwc/autostart
```

- **slideshow.py** is a self-contained pygame app. It runs fullscreen under labwc via `/etc/xdg/labwc/autostart` and writes its PID to `/tmp/slideshow.pid`. It is not managed by systemd.
- **Album providers** own the photo lifecycle. The active provider is selected by `sync.provider` in the config:
  - `onedrive` — syncs a shared OneDrive folder (Badger token API) into its own cache directory, with destructive cleanup of files no longer present remotely.
  - `local` — exposes a user-managed directory directly: no copying, no cleanup.
  - `google` — a stub for the future Google Photos source; returns an empty album.
- The player rescans the provider's album at the start of each cycle, so newly synced photos appear without a restart.
- **labwc autostart** suppresses the desktop and launches the slideshow directly.

---

## Prerequisites

- Raspberry Pi running Raspberry Pi OS Bookworm with a labwc Wayland session
- SSH access: `frame@10.1.7.58`
- Python 3.13 managed by uv (installed by `install.sh`)

---

## Installation

```bash
# From repo root on your dev machine:
bash eng/install.sh
```

`install.sh` rsyncs the repo to the Pi, installs apt packages, runs `uv sync`, writes the Wi-Fi sudoers entry, removes the retired sync-service install, and patches `/etc/xdg/labwc/autostart`. It is idempotent — safe to re-run.

If the config was just created, edit it:
```bash
ssh frame@10.1.7.58 'nano /home/frame/digital-frame/config.toml'
```

Reboot the Pi to apply autostart changes:
```bash
ssh frame@10.1.7.58 'sudo reboot now'
```

---

## Configuration

The app reads **`src/config.toml`** (gitignored). `install.sh` seeds the root `config.toml` from `config.toml.example` as a starting template — copy it to `src/config.toml` (or edit that file directly) to activate your settings. See `config.toml.example` for the full annotated template.

The sync section selects the album provider:

```toml
[sync]
provider         = "onedrive"   # "onedrive" | "local" | "google"
interval_minutes = 60

[sync.onedrive]
share_url = "https://1drv.ms/f/YOUR_SHARE_URL"
password  = "your-password"
cache_dir   = "/home/frame/.cache/piframe/onedrive"

[sync.local]
source_dir = "/home/frame/Pictures/slideshow"
```

- `sync.provider` selects the album provider; unknown values fail startup with a clear error.
- Provider-specific keys live in the provider's sub-section (`[sync.onedrive]`, `[sync.local]`, `[sync.google]`).
- Any key can be overridden at startup (when the config is loaded) with a `PIFRAME__`-prefixed environment variable: the remainder of the name is the config path, upper-cased and joined with `__` (e.g. `PIFRAME__SYNC__ONEDRIVE__SHARE_URL`). Protected keys (provider selection, OneDrive credentials) are never written back to the file.
- **Rendered-surface cache:** the composited-surface cache location is not configurable; it is fixed at `~/.cache/piframe/surfaces`.

> ⚠️ The tracked root `config.toml` must never contain real credentials — only the app's `src/config.toml` copy is gitignored.

---

## Debugging

```bash
# Slideshow log (when manually launched)
cat /tmp/slideshow.log

# Slideshow PID
cat /tmp/slideshow.pid

# Composited-surface cache
ls /home/frame/.cache/piframe/surfaces/

# OneDrive provider cache
ls /home/frame/.cache/piframe/onedrive/

# Check labwc autostart
cat /etc/xdg/labwc/autostart

# Kill the slideshow (do NOT use pkill -f slideshow.py — it matches the SSH command itself)
ssh frame@10.1.7.58 'kill -9 $(cat /tmp/slideshow.pid)'

# Manual restart (for testing without a reboot)
ssh frame@10.1.7.58 'XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 /home/frame/digital-frame/.venv/bin/slideshow > /tmp/slideshow.log 2>&1 &'
```

---

## Retired components

The first-generation mpv-based slideshow and the external OneDrive sync service predate the current app and are no longer in the repo; `install.sh` removes any leftover install of the sync service from the Pi. The old mpv IPC controls (`append/next/prev/...` against `/tmp/mpv-socket`) no longer apply.

---

## Rollback

To restore the original desktop:
```bash
sudo cp /etc/xdg/labwc/autostart.bak /etc/xdg/labwc/autostart
sudo reboot
```

---

## Security Notes

- OneDrive credentials live in the app's `src/config.toml` (gitignored); the tracked root `config.toml` must never contain real credentials.
- WiFi passphrases are never logged.
- `nmcli connect` runs via a targeted sudoers entry (`/etc/sudoers.d/piframe-wifi`); no process runs as root directly.
- The slideshow runs as the `frame` user under the Wayland session.
