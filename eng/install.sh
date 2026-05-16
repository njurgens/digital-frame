#!/usr/bin/env bash
# install.sh — Deploy the rpi-picture-frame slideshow stack to the Raspberry Pi
# Run this from your development machine:
#   bash install.sh
# Or run on the Pi directly after cloning the repo.
#
# Assumptions:
#   - Pi is reachable at frame@10.1.7.58 (SSH with default key)
#   - This script is run from the repo root
#   - Pi runs Raspberry Pi OS Bookworm with labwc Wayland session

set -euo pipefail

PI="frame@10.1.7.58"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Syncing framesync directory to Pi..."
rsync -av --exclude='__pycache__' --exclude='*.pyc' \
  "${REPO_DIR}/framesync/" "frame@10.1.7.58:/home/frame/framesync/"

echo "==> Installing system packages on Pi..."
ssh "$PI" 'sudo apt-get update -qq && sudo apt-get install -y \
  python3-pygame \
  python3-pil \
  python3-pip \
  network-manager \
  curl'

echo "==> Making slideshow.py executable..."
ssh "$PI" 'chmod +x /home/frame/framesync/slideshow.py'

echo "==> Ensuring config.toml exists (will not overwrite)..."
ssh "$PI" '
  if [ ! -f /home/frame/framesync/config.toml ]; then
    cp /home/frame/framesync/config.toml.example /home/frame/framesync/config.toml
    echo "IMPORTANT: Edit /home/frame/framesync/config.toml with your OneDrive credentials."
  else
    echo "config.toml already exists — skipping."
  fi
'

echo "==> Ensuring Pictures/slideshow directory exists..."
ssh "$PI" 'mkdir -p /home/frame/Pictures/slideshow'

echo "==> Installing sudoers entry for WiFi..."
ssh "$PI" '
  sudo install -o root -g root -m 440 \
    /home/frame/framesync/framesync-wifi.sudoers \
    /etc/sudoers.d/framesync-wifi
  sudo visudo -c -f /etc/sudoers.d/framesync-wifi && echo "sudoers OK"
'

echo "==> Installing framesync.service and timer..."
ssh "$PI" '
  sudo cp /home/frame/framesync/framesync.service /etc/systemd/system/
  sudo cp /home/frame/framesync/framesync.timer /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable framesync.timer
  sudo systemctl start framesync.timer
'

echo "==> Patching /etc/xdg/labwc/autostart for pygame slideshow..."
ssh "$PI" '
  AUTOSTART=/etc/xdg/labwc/autostart
  sudo cp -n "$AUTOSTART" "${AUTOSTART}.bak" && echo "Backed up autostart"

  sudo python3 - <<EOF
import pathlib

path = pathlib.Path("/etc/xdg/labwc/autostart")
content = path.read_text()

lines = []
for line in content.splitlines():
    stripped = line.strip()
    # Comment out desktop/panel/keyboard components we no longer want
    if any(x in stripped for x in [
        "pcmanfm", "wf-panel-pi", "lxsession-xdg-autostart",
        "wvkbd-mobintl", "kiosk-start.sh", "chromium",
    ]):
        if not stripped.startswith("#"):
            lines.append("# " + line)
        else:
            lines.append(line)
    # Comment out any old mpv-based slideshow line
    elif stripped.startswith("mpv") and "mpv-socket" in stripped:
        if not stripped.startswith("#"):
            lines.append("# " + line + "  # replaced by slideshow.py")
        else:
            lines.append(line)
    else:
        lines.append(line)

out = "\n".join(lines)

slideshow_line = "python3 /home/frame/framesync/slideshow.py &"

if "framesync/slideshow.py" in out:
    replaced = []
    for l in out.splitlines():
        if "framesync/slideshow.py" in l and not l.strip().startswith("#"):
            replaced.append(slideshow_line)
        else:
            replaced.append(l)
    out = "\n".join(replaced)
else:
    out += "\n" + slideshow_line

out += "\n"
path.write_text(out)
print("autostart updated")
EOF
'

echo ""
echo "==> Installation complete."
echo ""
echo "Next steps:"
echo "  1. If config.toml was just created, edit it: ssh $PI 'nano /home/frame/framesync/config.toml'"
echo "  2. Run an initial sync: ssh $PI 'python3 /home/frame/framesync/framesync.py'"
echo "  3. Reboot the Pi: ssh $PI 'sudo reboot'"
echo ""
echo "Useful debug commands:"
echo "  ssh $PI 'journalctl -u framesync -f'                        # OneDrive sync logs"
echo "  ssh $PI 'journalctl -u framesync.timer -f'                  # Timer logs"
echo "  ssh $PI 'ls /home/frame/Pictures/slideshow/'                # Check synced photos"
echo "  ssh $PI 'ls /home/frame/.cache/framesync/'                  # Check surface cache"
echo "  ssh $PI 'cat /etc/xdg/labwc/autostart'                      # Check autostart config"