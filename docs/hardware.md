# Hardware Target

Pi Frame targets a single, fixed hardware platform. All performance and
memory decisions in the design docs assume these constraints.

## Device

- **SBC:** Raspberry Pi 3A+ (aarch64)
- **RAM:** 512 MB
- **GPU:** Broadcom VideoCore IV (vc4) — OpenGL ES 2.0 / GL 2.1 only

## Display

- **Panel:** Waveshare 10.1inch DSI LCD (C) — 10.1" IPS, 1280×800
- **Interface:** 15-pin FPC DSI cable, plugged straight into the Pi 3A+ DSI port
- **Touch:** 10-point capacitive
- **Driver:** Bookworm `dtoverlay=vc4-kms-dsi-waveshare-panel,10_1_inch` (KMS via vc4)
- **Power:** 5 V input ≥ 0.88 A — under-powered supplies cause boot failures or display glitches
- **Reference:** <https://www.waveshare.com/wiki/10.1inch_DSI_LCD_(C)>

The app renders fullscreen at 1280×800 (see `SCREEN_W`/`SCREEN_H` in the LLD).

## Operating system

- **Raspberry Pi OS Bookworm** (Debian 12), aarch64
- Wayland with the **labwc** compositor (no X11)

## Access and runtime

- **SSH:** `frame@10.1.7.58` — all commands that touch the Pi run over SSH
- **User:** `frame` (uid 1000); the app runs as this user
- **App home:** `/home/frame/digital-frame`
- **Launch:** the app is started from `/etc/xdg/labwc/autostart` (not
  systemd) and writes its PID to `$XDG_RUNTIME_DIR/slideshow.pid` (the
  per-user runtime dir; `~/.local/piframe` when that is unavailable)
