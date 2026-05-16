# Raspberry Pi Picture Frame — Setup & Debug Guide

## Architecture

```
[OneDrive] ──sync──> framesync.service (oneshot, hourly timer)
                          |
                          v
               /home/frame/Pictures/slideshow/
                          |
              framesync.py calls slideshow.py IPC
                          |
                          v
              mpv (fullscreen, Wayland/labwc) <── /tmp/mpv-socket
              launched by /etc/xdg/labwc/autostart
```

- **mpv** runs fullscreen under Wayland/labwc. No browser, no Flask, no frontend.
- **framesync** syncs photos from OneDrive on a timer, then injects new files into the running mpv playlist via IPC.
- **slideshow.py** is both a Python library (imported by framesync.py) and a CLI tool for manual control.
- **labwc autostart** suppresses the desktop and launches mpv directly.

---

## Prerequisites

- Raspberry Pi running Raspberry Pi OS Bookworm with labwc Wayland session
- SSH access: `frame@10.1.7.58`
- `mpv` (installed by `install.sh`)

---

## Installation

```bash
# From repo root on your dev machine:
bash install.sh
```

Then SSH in and edit config.toml if it was just created:
```bash
ssh frame@10.1.7.58 'nano /home/frame/framesync/config.toml'
```

Run an initial sync to populate the slideshow directory:
```bash
ssh frame@10.1.7.58 'python3 /home/frame/framesync/framesync.py'
```

Reboot the Pi:
```bash
ssh frame@10.1.7.58 'sudo reboot'
```

---

## Configuration

### `/home/frame/framesync/config.toml`
```toml
share_url      = "https://1drv.ms/f/YOUR_SHARE_URL"
password       = "your-password"
output_dir     = "/home/frame/Pictures/slideshow"
image_duration = 8
mpv_socket     = "/tmp/mpv-socket"
```

> ⚠️ `config.toml` is excluded from version control. Copy `config.toml.example` and fill in your values.

---

## mpv Slideshow Control

`slideshow.py` is a CLI tool and Python library for controlling the running mpv instance via its IPC socket.

```bash
# Append new files to the playlist (hot-reload without restart)
python3 /home/frame/framesync/slideshow.py append /home/frame/Pictures/slideshow/*.jpg

# Navigation
python3 /home/frame/framesync/slideshow.py next
python3 /home/frame/framesync/slideshow.py prev

# Pause / resume
python3 /home/frame/framesync/slideshow.py pause
python3 /home/frame/framesync/slideshow.py resume

# Show current playlist
python3 /home/frame/framesync/slideshow.py playlist
```

### mpv IPC Reference

The IPC socket lives at `/tmp/mpv-socket`. Commands are newline-terminated JSON:

```bash
# Get current playlist
echo '{"command":["get_property","playlist"]}' | socat - /tmp/mpv-socket

# Append a file
echo '{"command":["loadfile","/path/to/photo.jpg","append-play"]}' | socat - /tmp/mpv-socket

# Skip to next
echo '{"command":["playlist-next"]}' | socat - /tmp/mpv-socket

# Pause / resume
echo '{"command":["set_property","pause",true]}' | socat - /tmp/mpv-socket
echo '{"command":["set_property","pause",false]}' | socat - /tmp/mpv-socket
```

### Crossfade Notes

The Pi 3A+ VideoCore IV supports OpenGL ES 2.0 only. GLSL crossfade shaders (e.g., gl-transitions) require ES 3.0+ and are not used. The slideshow uses hard cuts with `--image-display-duration=8`. A software fade can be added later via `--vf=lavfi=[fade=...]` if desired.

---

## Systemd Services

| Service | Purpose |
|---------|---------|
| `framesync` | OneDrive sync (oneshot, run by timer) |
| `framesync.timer` | Triggers `framesync` hourly |

> `framesync-server` (Flask) has been removed. mpv is started by labwc autostart, not systemd.

---

## Debugging

```bash
# OneDrive sync logs
journalctl -u framesync -f

# Timer logs
journalctl -u framesync.timer

# Check synced photos
ls /home/frame/Pictures/slideshow/

# Verify mpv is running
pgrep -a mpv

# Query mpv playlist via IPC
echo '{"command":["get_property","playlist"]}' | socat - /tmp/mpv-socket

# Check labwc autostart
cat /etc/xdg/labwc/autostart

# Manual slideshow controls
python3 /home/frame/framesync/slideshow.py playlist
python3 /home/frame/framesync/slideshow.py next
```

---

## Rollback

To restore the original desktop:
```bash
sudo cp /etc/xdg/labwc/autostart.bak /etc/xdg/labwc/autostart
sudo reboot
```

---

## Security Notes

- `config.toml` (OneDrive credentials) is excluded from version control.
- WiFi passphrases are never logged.
- `nmcli connect` runs via a targeted sudoers entry (`/etc/sudoers.d/framesync-wifi`); no process runs as root directly.
- mpv runs as the `frame` user under the Wayland session.