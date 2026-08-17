# Hardware Target

Pi Frame targets a single, fixed hardware platform. All performance and
memory decisions in the design docs assume these constraints.

## Device

- **SBC:** Raspberry Pi 3A+ (aarch64)
- **RAM:** 512 MB
- **GPU:** Broadcom VideoCore IV (vc4) — OpenGL ES 2.0 / GL 2.1 only

## Operating system

- **Raspberry Pi OS Bookworm** (Debian 12), aarch64
- Wayland with the **labwc** compositor (no X11)

## Access and runtime

- **SSH:** `frame@10.1.7.58` — all commands that touch the Pi run over SSH
- **User:** `frame` (uid 1000); the app runs as this user
- **App home:** `/home/frame/digital-frame` — the repo is rsynced here by
  `eng/install.sh`
- **Launch:** the app is started from `/etc/xdg/labwc/autostart` (not
  systemd) and writes its PID to `/tmp/slideshow.pid`
