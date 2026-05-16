#!/usr/bin/env bash
# eng/install.sh — Deploy the Pi Frame app to the Raspberry Pi.
# Run from the repo root on your development machine:
#   bash eng/install.sh
#
# Assumptions:
#   - Pi is reachable at frame@10.1.7.58 (SSH with default key)
#   - This script is idempotent — safe to re-run at any stage

set -euo pipefail

PI="frame@10.1.7.58"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_DIR="/home/frame/digital-frame"

echo "==> Syncing app to Pi at ${REMOTE_DIR} ..."
# Sync the whole repo minus git history, caches, and secrets
rsync -av --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='.git' --exclude='config.toml' \
  "${REPO_DIR}/" "frame@10.1.7.58:${REMOTE_DIR}/"

echo "==> Installing system packages on Pi..."
ssh "$PI" 'sudo apt-get update -qq && sudo apt-get install -y \
  python3-pygame \
  python3-pil \
  python3-requests \
  python3-numpy \
  fonts-noto-core \
  network-manager \
  curl \
  socat \
  python3-pytest \
  python3-paramiko'

echo "==> Ensuring config.toml exists (will not overwrite)..."
ssh "$PI" "
  if [ ! -f ${REMOTE_DIR}/config.toml ]; then
    cp ${REMOTE_DIR}/config.toml.example ${REMOTE_DIR}/config.toml
    echo 'IMPORTANT: Edit ${REMOTE_DIR}/config.toml with your OneDrive credentials.'
  else
    echo 'config.toml already exists — skipping.'
  fi
"

echo "==> Ensuring photo and cache directories exist..."
ssh "$PI" 'mkdir -p /home/frame/Pictures/slideshow /home/frame/.cache/framesync'

echo "==> Installing sudoers entry for Wi-Fi..."
ssh "$PI" "
  sudo install -o root -g root -m 440 \
    ${REMOTE_DIR}/framesync/framesync-wifi.sudoers \
    /etc/sudoers.d/framesync-wifi
  sudo visudo -c -f /etc/sudoers.d/framesync-wifi && echo 'sudoers OK'
"

echo "==> Patching /etc/xdg/labwc/autostart..."
ssh "$PI" "
  AUTOSTART=/etc/xdg/labwc/autostart
  sudo cp -n \"\$AUTOSTART\" \"\${AUTOSTART}.bak\" 2>/dev/null && echo 'Backed up autostart' || true

  sudo python3 - <<'PYEOF'
import pathlib

path = pathlib.Path('/etc/xdg/labwc/autostart')
content = path.read_text()

lines = []
for line in content.splitlines():
    stripped = line.strip()
    if any(x in stripped for x in [
        'pcmanfm', 'wf-panel-pi', 'lxsession-xdg-autostart',
        'wvkbd-mobintl', 'kiosk-start.sh', 'chromium',
    ]):
        if not stripped.startswith('#'):
            lines.append('# ' + line)
        else:
            lines.append(line)
    elif stripped.startswith('mpv') and 'mpv-socket' in stripped:
        if not stripped.startswith('#'):
            lines.append('# ' + line)
        else:
            lines.append(line)
    else:
        lines.append(line)

out = '\n'.join(lines)
new_line = 'python3 /home/frame/digital-frame/slideshow.py &'

# Remove any previous slideshow line (old or new path)
replaced = []
for l in out.splitlines():
    if ('slideshow.py' in l and not l.strip().startswith('#')):
        replaced.append(new_line)
        new_line = None  # only insert once
    else:
        replaced.append(l)
if new_line is not None:
    replaced.append(new_line)

out = '\n'.join(replaced) + '\n'
path.write_text(out)
print('autostart updated')
PYEOF
"

echo ""
echo "==> Installation complete."
echo ""
echo "Next steps:"
echo "  1. Edit credentials if needed: ssh $PI 'nano ${REMOTE_DIR}/config.toml'"
echo "  2. Reboot to apply autostart: ssh $PI 'sudo reboot now'"
echo ""
echo "Manual test start (without reboot):"
echo "  ssh $PI 'kill -9 \$(cat /tmp/slideshow.pid 2>/dev/null) 2>/dev/null; sleep 1; XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 python3 ${REMOTE_DIR}/slideshow.py > /tmp/slideshow.log 2>&1 &'"
echo ""
echo "Debug commands:"
echo "  ssh $PI 'cat /tmp/slideshow.log'           # slideshow logs"
echo "  ssh $PI 'cat /tmp/slideshow.pid'           # slideshow PID"
echo "  ssh $PI 'cat /etc/xdg/labwc/autostart'    # autostart config"