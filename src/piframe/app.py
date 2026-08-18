"""Main application module for the Pi Frame digital photo frame."""

from __future__ import annotations

import argparse
import fcntl
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pygame
import pygame.freetype

from piframe import types as app_types
from piframe.assets import Assets
from piframe.backlight import BacklightController
from piframe.clock_widget import ClockWidget
from piframe.config_store import ConfigStore
from piframe.ipc import IpcServer, optional_int, require_int, require_scalar, require_str
from piframe.keyboard import Keyboard
from piframe.modules import (
    CacheModule,
    IpcModule,
    PlayerModule,
    ProviderModule,
    SettingsModule,
    SyncModule,
    WifiModule,
)
from piframe.overlay_ui import OverlayUI
from piframe.runtime_paths import pid_file_path, resolve_runtime_dir, socket_path
from piframe.sleep_scheduler import SleepScheduler
from piframe.types import (
    FPS,
    SCREEN_H,
    SCREEN_W,
    SIDEBAR_W,
    WAKE_GRACE,
    AppState,
    init_events,
)
from piframe.widgets.confirm_dialog import ConfirmDialog
from piframe.widgets.text_input import TextInput

_SWIPE_MIN_DX = 60
_SWIPE_MAX_DT = 0.4
_SWIPE_MAX_SLOPE = 0.5
_TAP_MAX_DIST = 20.0

#: The app's config file (gitignored; bootstrapped by eng/run.sh).
CONFIG_PATH = Path(__file__).parent.parent / "config.toml"


def acquire_pid_file(path: str | Path) -> int:
    """Open *path*, take an exclusive flock, and write our PID to it.

    The file is chmod'd 0600 after creation (deterministic regardless of
    umask or a pre-existing file), and the lock is held on the returned fd
    for the process lifetime (the kernel releases it on death), so the lock
    state is a liveness oracle: eng/run.sh probes it to tell a live instance
    from a stale file.

    Returns the fd. Exits if another instance already holds the lock.
    """
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    os.fchmod(fd, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        sys.exit("another slideshow is already running; refusing to start a second instance")
    os.ftruncate(fd, 0)
    os.write(fd, f"{os.getpid()}\n".encode())
    return fd


class App:
    """Main application class for the Pi Frame digital photo frame."""

    def __init__(self) -> None:
        """Initialise all services and enter the main loop."""
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--windowed", action="store_true", help="Run in a window instead of fullscreen"
        )
        self._args = parser.parse_args()

        pygame.init()
        pygame.freetype.init()
        init_events()

        self._runtime_dir = resolve_runtime_dir()
        self._pid_fd = acquire_pid_file(pid_file_path(self._runtime_dir))

        if self._args.windowed:
            # Plain window: the SCALED (high-DPI) flag requires a hardware
            # renderer, and with the devcontainer's software renderer the
            # window is created but never presented.
            self._screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        else:
            self._screen = pygame.display.set_mode(
                (SCREEN_W, SCREEN_H),
                pygame.FULLSCREEN | pygame.NOFRAME,
            )
        pygame.display.set_caption("Pi Frame")
        self._clock = pygame.time.Clock()
        self._state = AppState.SLIDESHOW

        self._swipe_start_pos: tuple[int, int] | None = None
        self._swipe_start_time: float | None = None
        self._suppress_next_tap: bool = False

        self._assets = Assets.load()

        self._config = ConfigStore(CONFIG_PATH)

        # Modules construct services — conditional logic is encapsulated.
        # The provider is created first and shared by the sync and player
        # modules, which both consume the same instance (D-6, D-8).
        self._provider = ProviderModule().create(self._config)
        self._cache = CacheModule().create(self._config)
        self._clock_w = ClockWidget(self._assets)
        self._sync = SyncModule().create(self._config, provider=self._provider)
        self._player = PlayerModule().create(
            self._config, provider=self._provider, cache=self._cache, assets=self._assets
        )
        self._backlight = BacklightController()
        self._overlay = OverlayUI(self._assets, self._config)
        self._wifi = WifiModule().create(self._config)
        self._settings = SettingsModule().create(
            self._config,
            assets=self._assets,
            wifi_manager=self._wifi,
            sync_service=self._sync,
            on_brightness_change=self._on_brightness_change,
            on_focus_text=self._on_focus_text,
            app_ref=self,
        )
        self._sleep = SleepScheduler(self._config)
        self._keyboard = Keyboard(self._assets, on_done=self._on_keyboard_done)
        self._dialog: ConfirmDialog | None = None
        self._overlay.on_brightness_change = self._on_brightness_change
        self._overlay._slider.on_change = self._on_brightness_change
        self._overlay.set_paused(self._player.is_paused)
        self._overlay.set_brightness(self._config.display.brightness)
        self._backlight.set_brightness(self._config.display.brightness)

        self._ipc_executors: dict[str, Callable[[dict], object]] = {
            "state": self._ipc_state,
            "tap": self._ipc_tap,
            "swipe": self._ipc_swipe,
            "play_pause": self._ipc_play_pause,
            "prev": self._ipc_prev,
            "next": self._ipc_next,
            "screenshot": self._ipc_screenshot,
            "quit": self._ipc_quit,
            "set_config": self._ipc_set_config,
            "trigger_sync": self._ipc_trigger_sync,
        }
        self._ipc: IpcServer | None = IpcModule().create(
            self._config,
            socket_path=socket_path(self._runtime_dir),
            executors=self._ipc_executors,
        )

    def _on_brightness_change(self, value: int) -> None:
        self._backlight.set_brightness(value)
        self._config.set("display", "brightness", value)
        self._overlay.set_brightness(value)

    def _on_focus_text(self, field: TextInput) -> None:
        self._keyboard.attach(field)
        self._state = AppState.KEYBOARD

    def _on_keyboard_done(self) -> None:
        self._state = AppState.SETTINGS

    def run(self) -> None:
        """Run the main application loop."""
        prev_time = time.monotonic()
        while True:
            now = time.monotonic()
            dt = min(now - prev_time, 0.1)
            prev_time = now

            self._process_pygame_events()
            self._drain_ipc_queue()  # drain even when sleeping
            if self._state == AppState.SLEEPING:
                time.sleep(0.25)
                continue
            self._update(dt)
            self._draw()
            pygame.display.flip()
            self._clock.tick(FPS)

    def _process_pygame_events(self):
        for event in pygame.event.get():
            if self._dialog is not None and self._dialog.handle_event(event):
                continue
            if event.type == app_types.EVT_SLEEP:
                self._enter_sleep()
                continue
            if event.type == app_types.EVT_WAKE:
                self._exit_sleep()
                continue
            if event.type == app_types.EVT_WIFI_RESULT:
                self._settings.on_wifi_result(event.result)
                continue
            if event.type == app_types.EVT_UPDATE_RESULT:
                self._settings.on_update_result(event.result)
                continue
            if event.type == app_types.EVT_SYNC_COMPLETE:
                self._player.rescan()
                self._settings.refresh_sync_status()
                continue

            if self._state == AppState.KEYBOARD:
                if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                    kb_rect = pygame.Rect(0, 450, SCREEN_W, 350)
                    if event.type == pygame.MOUSEBUTTONDOWN and not kb_rect.collidepoint(
                        event.pos
                    ):
                        self._keyboard.detach()
                        self._state = AppState.SETTINGS
                        continue
                if self._keyboard.handle_event(event):
                    continue

            if self._state == AppState.SETTINGS and event.type in {
                pygame.MOUSEBUTTONDOWN,
                pygame.MOUSEMOTION,
                pygame.MOUSEBUTTONUP,
            }:
                if (
                    event.type == pygame.MOUSEBUTTONDOWN
                    and getattr(event, "button", 0) == 1
                    and pygame.Rect(0, 0, SIDEBAR_W, 58).collidepoint(event.pos)
                ):
                    self._settings.close()
                    self._state = AppState.SLIDESHOW
                    self._suppress_next_tap = True
                else:
                    self._settings.on_tap(event)
                continue

            if event.type == pygame.QUIT:
                self._quit()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._quit()
            elif event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 0) == 1:
                self._swipe_start_pos = event.pos
                self._swipe_start_time = time.monotonic()
                if self._state == AppState.SLEEPING:
                    self._exit_sleep()
                    self._suppress_next_tap = True
            elif (
                event.type == pygame.MOUSEMOTION
                and event.buttons[0]
                and self._state == AppState.OVERLAY
            ):
                self._overlay.on_drag(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP and getattr(event, "button", 0) == 1:
                if self._suppress_next_tap:
                    self._suppress_next_tap = False
                    self._swipe_start_pos = None
                    self._swipe_start_time = None
                    continue
                if self._state == AppState.OVERLAY and self._overlay.is_dragging_slider():
                    self._overlay.stop_drag()
                    self._swipe_start_pos = None
                    self._swipe_start_time = None
                    continue
                if self._state == AppState.OVERLAY:
                    self._overlay.stop_drag()
                self._classify_pointer_up(event.pos)

    def _classify_pointer_up(self, pos: tuple[int, int]) -> None:
        if self._swipe_start_pos is None or self._swipe_start_time is None:
            return

        dx = pos[0] - self._swipe_start_pos[0]
        dy = pos[1] - self._swipe_start_pos[1]
        elapsed = time.monotonic() - self._swipe_start_time

        self._swipe_start_pos = None
        self._swipe_start_time = None

        abs_dx = abs(dx)
        abs_dy = abs(dy)
        if (
            elapsed < _SWIPE_MAX_DT
            and abs_dx > _SWIPE_MIN_DX
            and abs_dy <= abs_dx * _SWIPE_MAX_SLOPE
        ):
            if dx < 0:
                self._player.skip()
            else:
                self._player.go_back()
            return

        if (dx * dx + dy * dy) > (_TAP_MAX_DIST * _TAP_MAX_DIST):
            return

        self._dispatch_tap(pos)

    def _dispatch_tap(self, pos: tuple[int, int]) -> None:
        if self._state == AppState.SLIDESHOW:
            self._overlay.show()
            self._state = AppState.OVERLAY
            return

        if self._state == AppState.OVERLAY:
            action = self._overlay.on_tap(pos)
            if action is None:
                self._overlay.hide()
                self._state = AppState.SLIDESHOW
            elif action == "play_pause":
                self._player.is_paused = not self._player.is_paused
                self._overlay.set_paused(self._player.is_paused)
            elif action == "prev":
                self._player.go_back()
                self._overlay.dismissed = False
                self._overlay._extend_dismiss()
            elif action == "next":
                self._player.skip()
                self._overlay.dismissed = False
                self._overlay._extend_dismiss()
            elif action == "settings":
                self._settings.open()
                self._state = AppState.SETTINGS
            elif action == "dismiss":
                self._overlay.hide()
                self._state = AppState.SLIDESHOW
            return

        if self._state == AppState.SETTINGS:
            return

        if self._state == AppState.KEYBOARD:
            return

    def _update(self, dt: float):
        self._player.update(dt)
        self._clock_w.update(dt)
        self._config.tick(time.monotonic())
        if self._state == AppState.OVERLAY:
            self._overlay.update(dt)
            if self._overlay.dismissed:
                self._state = AppState.SLIDESHOW
        elif self._state == AppState.SETTINGS:
            self._settings.update(dt)

    def _draw(self):
        if self._state not in {AppState.SETTINGS, AppState.KEYBOARD}:
            self._player.draw(self._screen)

            # Draw clock before overlay in SLIDESHOW; it is re-drawn after the
            # overlay scrim in OVERLAY so it appears on top (OV-05).
            if self._config.display.show_clock and self._state == AppState.SLIDESHOW:
                self._clock_w.draw(self._screen)

            if self._player.is_paused and self._state == AppState.SLIDESHOW:
                self._player.draw_pip(self._screen)

        if self._state == AppState.OVERLAY:
            self._overlay.draw(self._screen)
            if self._config.display.show_clock:
                self._clock_w.draw(self._screen)
        if self._state in {AppState.SETTINGS, AppState.KEYBOARD}:
            self._settings.draw(self._screen)
            if self._state == AppState.KEYBOARD:
                self._keyboard.draw(self._screen)
        if self._dialog is not None:
            self._dialog.draw(self._screen)

    def _quit(self):
        self._cleanup()
        pygame.quit()
        sys.exit(0)

    def _cleanup(self):
        sync = getattr(self, "_sync", None)
        if sync is not None:
            sync.stop()  # sole owner of the provider's close (D-9)
        ipc = getattr(self, "_ipc", None)
        if ipc is not None:
            ipc.stop()
        self._sleep.stop()
        self._clock_w.stop()
        self._config.flush_now()

    def restart(self) -> None:
        """Restart the application by re-executing the process."""
        self._cleanup()
        env = os.environ.copy()
        env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
        env["WAYLAND_DISPLAY"] = "wayland-0"
        os.execve(sys.executable, [sys.executable, *sys.argv], env)

    def _shutdown(self) -> None:
        self._cleanup()
        subprocess.run(["sudo", "shutdown", "-h", "now"], check=False)
        pygame.quit()
        sys.exit(0)

    def _reboot(self) -> None:
        self._cleanup()
        subprocess.run(["sudo", "reboot"], check=False)
        pygame.quit()
        sys.exit(0)

    def _enter_sleep(self) -> None:
        self._backlight.set_brightness(0)
        self._state = AppState.SLEEPING

    def _exit_sleep(self) -> None:
        self._backlight.set_brightness(self._config.display.brightness)
        self._state = AppState.OVERLAY
        self._overlay.show()
        self._sleep.set_grace(time.monotonic() + WAKE_GRACE)

    def _drain_ipc_queue(self) -> None:
        """Execute queued IPC requests on the main thread and send their responses.

        The accept thread only reads and parses; this is where commands run
        (the main thread is the sole executor of pygame work) and responses
        go out.  A None response (a notification) just closes the
        connection.
        """
        if self._ipc is None:
            return
        while (item := self._ipc.poll()) is not None:
            parsed, conn = item
            self._ipc.respond(conn, self._ipc.handle(parsed))

    # --- IPC executors: one per JSON-RPC method -----------------------------

    def _ipc_state(self, params: dict) -> dict:
        """Report the current app state."""
        return {"state": self._state.name}

    def _ipc_tap(self, params: dict) -> dict:
        """Post a synthetic tap (down + up) at (x, y)."""
        x = require_int(params, "x")
        y = require_int(params, "y")
        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(x, y), button=1))
        time.sleep(0.05)
        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(x, y), button=1))
        return {}

    def _ipc_swipe(self, params: dict) -> dict:
        """Post a synthetic swipe from (x, y) by (dx, dy) over ms milliseconds."""
        x = require_int(params, "x")
        y = require_int(params, "y")
        dx = require_int(params, "dx")
        dy = require_int(params, "dy")
        ms = optional_int(params, "ms", 300)
        steps = max(5, ms // 16)
        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(x, y), button=1))
        delay_s = max(0.001, (ms / 1000.0) / float(steps))
        for i in range(1, steps + 1):
            mv = pygame.event.Event(
                pygame.MOUSEMOTION,
                pos=(x + dx * i // steps, y + dy * i // steps),
                rel=(dx // steps, dy // steps),
                buttons=(1, 0, 0),
            )
            pygame.event.post(mv)
            time.sleep(delay_s)
        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(x + dx, y + dy), button=1))
        return {}

    def _ipc_play_pause(self, params: dict) -> dict:
        """Toggle playback and report the new paused state."""
        self._player.is_paused = not self._player.is_paused
        self._overlay.set_paused(self._player.is_paused)
        return {"paused": self._player.is_paused}

    def _ipc_prev(self, params: dict) -> dict:
        """Go back one slide."""
        self._player.go_back()
        if self._state == AppState.OVERLAY:
            self._overlay.dismissed = False
            self._overlay._extend_dismiss()
        return {}

    def _ipc_next(self, params: dict) -> dict:
        """Skip to the next slide."""
        self._player.skip()
        if self._state == AppState.OVERLAY:
            self._overlay.dismissed = False
            self._overlay._extend_dismiss()
        return {}

    def _ipc_screenshot(self, params: dict) -> dict:
        """Save the current screen to the given path."""
        path = require_str(params, "path")
        pygame.image.save(self._screen, path)
        return {}

    def _ipc_quit(self, params: dict) -> dict:
        """Quit the app (a notification: the process exits before any response)."""
        self._quit()
        return {}

    def _ipc_set_config(self, params: dict) -> dict:
        """Set a config value, then refresh the sleep schedule and settings panel."""
        section = require_str(params, "section")
        key = require_str(params, "key")
        value = require_scalar(params, "value")
        self._config.set(section, key, value)
        if section == "sleep":
            self._sleep.kick()
        if hasattr(self, "_settings"):
            self._settings.sync_from_config()
        return {}

    def _ipc_trigger_sync(self, params: dict) -> dict:
        """Trigger a photo sync."""
        sync = getattr(self, "_sync", None)
        if sync is not None:
            sync.trigger()
        return {}


def main() -> None:
    """Entry point for the slideshow CLI."""
    App().run()
