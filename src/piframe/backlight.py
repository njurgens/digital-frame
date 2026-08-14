"""Sysfs backlight brightness control."""

import logging

BACKLIGHT_PATH = "/sys/class/backlight/10-0045/brightness"
MAX_VALUE = 255


class BacklightController:
    """Sysfs-based backlight brightness controller."""

    def __init__(self) -> None:
        """Create a backlight controller with no cached brightness value."""
        self._last_percent: int | None = None

    def set_brightness(self, percent: int) -> None:
        """Set the backlight brightness to the given percentage (0-100).

        Args:
            percent: Brightness percentage to set.

        """
        percent = max(0, min(100, percent))
        if percent == self._last_percent:
            return
        sysfs_val = max(0, min(MAX_VALUE, round(percent / 100 * MAX_VALUE)))
        try:
            with open(BACKLIGHT_PATH, "w") as f:
                f.write(f"{sysfs_val}\n")
            self._last_percent = percent
        except OSError as e:
            logging.warning("backlight write failed: %s", e)

    def get_brightness(self) -> int:
        """Read the current backlight brightness as a percentage (0-100).

        Returns:
        -------
            The current brightness percentage, or 50 if the sysfs path is
            unreadable.

        """
        try:
            with open(BACKLIGHT_PATH) as f:
                raw = int(f.read().strip())
            return round(raw / MAX_VALUE * 100)
        except OSError:
            return 50
