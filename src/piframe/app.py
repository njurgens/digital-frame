"""Main application module for the Pi Frame digital photo frame."""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pygame
import pygame.freetype

if TYPE_CHECKING:
    import socket

from piframe import types as app_types
from piframe.assets import Assets
from piframe.backlight import BacklightController
from piframe.clock_widget import ClockWidget
from piframe.config_store import ConfigStore
from piframe.keyboard import Keyboard
from piframe.modules import (
    CacheModule,
    PlayerModule,
    SettingsModule,
    SyncModule,
    WifiModule,
)
from piframe.overlay_ui import OverlayUI
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


class App:
    """Main application class for the Pi Frame digital photo frame."""

    def __init__(self) -> None:
        """Initialise all services and enter the main loop."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--test-harness", action="store_true")
        parser.add_argument(
            "--windowed", action="store_true", help="Run in a window instead of fullscreen"
        )
        self._args = parser.parse_args()

        pygame.init()
        pygame.freetype.init()
        init_events()

        Path("/tmp/slideshow.pid").write_text(str(os.getpid()))

        if self._args.windowed:
            self._screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.SCALED)
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

        config_path = Path(__file__).parent.parent / "config.toml"
        self._config = ConfigStore(config_path)

        # Modules construct services — conditional logic is encapsulated
        self._cache = CacheModule().create(self._config)
        self._clock_w = ClockWidget(self._assets)
        self._sync = SyncModule().create(self._config)
        self._player = PlayerModule().create(self._config, cache=self._cache, assets=self._assets)
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

        self._harness_queue: queue.SimpleQueue = queue.SimpleQueue()
        if self._args.test_harness:
            self._start_harness()

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
            self._drain_harness_queue()  # drain even when sleeping
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
            sync.stop()
        self._sleep.stop()
        self._clock_w.stop()
        self._config.flush_now()

    def restart(self) -> None:
        """Restart the application by re-executing the process."""
        self._cleanup()
        env = os.environ.copy()
        env["XDG_RUNTIME_DIR"] = "/run/user/1000"
        env["WAYLAND_DISPLAY"] = "wayland-0"
        os.execve(sys.executable, [sys.executable] + sys.argv, env)

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

    def _start_harness(self):
        import socket as sock_mod
        import threading

        sock_path = "/tmp/piframe_test.sock"
        try:
            os.unlink(sock_path)
        except FileNotFoundError:
            pass
        server = sock_mod.socket(sock_mod.AF_UNIX, sock_mod.SOCK_STREAM)
        server.bind(sock_path)
        server.listen(5)
        t = threading.Thread(target=self._harness_loop, args=(server,), daemon=True)
        t.start()

    def _harness_loop(self, server: socket.socket) -> None:
        while True:
            conn = None
            try:
                conn, _ = server.accept()
                data = b""
                while True:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                    if b"\n" in data:
                        break
                msg = json.loads(data.strip())
                _ = self._handle_harness_cmd(msg, conn)
            except Exception as e:
                if conn is not None:
                    try:
                        conn.sendall((json.dumps({"ok": False, "error": str(e)}) + "\n").encode())
                    except Exception:
                        pass
                    try:
                        conn.close()
                    except Exception:
                        pass

    def _handle_harness_cmd(self, msg: dict, conn: socket.socket) -> None:
        import threading

        cmd = msg.get("cmd")
        response_event = threading.Event()
        result_holder = {}
        self._harness_queue.put((cmd, msg, conn, response_event, result_holder))

    def _drain_harness_queue(self):
        while True:
            try:
                cmd, msg, conn, done_event, result_holder = self._harness_queue.get_nowait()
                _ = done_event, result_holder
            except Exception:
                break
            try:
                resp = self._exec_harness_cmd(cmd, msg)
            except Exception as e:
                resp = {"ok": False, "error": str(e)}
            try:
                conn.sendall((json.dumps(resp) + "\n").encode())
            except Exception:
                pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    def _exec_harness_cmd(self, cmd: str, msg: dict) -> dict:
        import time as _time

        if cmd == "state":
            return {"ok": True, "state": self._state.name}
        if cmd == "tap":
            x, y = msg["x"], msg["y"]
            ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(x, y), button=1)
            pygame.event.post(ev)
            _time.sleep(0.05)
            ev2 = pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(x, y), button=1)
            pygame.event.post(ev2)
            return {"ok": True}
        if cmd == "swipe":
            x, y, dx, dy, ms = msg["x"], msg["y"], msg["dx"], msg["dy"], msg.get("ms", 300)
            steps = max(5, ms // 16)
            down = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(x, y), button=1)
            pygame.event.post(down)
            delay_s = max(0.001, (ms / 1000.0) / float(steps))
            for i in range(1, steps + 1):
                fx = x + dx * i // steps
                fy = y + dy * i // steps
                mv = pygame.event.Event(
                    pygame.MOUSEMOTION,
                    pos=(fx, fy),
                    rel=(dx // steps, dy // steps),
                    buttons=(1, 0, 0),
                )
                pygame.event.post(mv)
                _time.sleep(delay_s)
            up = pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(x + dx, y + dy), button=1)
            pygame.event.post(up)
            return {"ok": True}
        if cmd == "play_pause":
            self._player.is_paused = not self._player.is_paused
            self._overlay.set_paused(self._player.is_paused)
            return {"ok": True, "paused": self._player.is_paused}
        if cmd == "prev":
            self._player.go_back()
            if self._state == AppState.OVERLAY:
                self._overlay.dismissed = False
                self._overlay._extend_dismiss()
            return {"ok": True}
        if cmd == "next":
            self._player.skip()
            if self._state == AppState.OVERLAY:
                self._overlay.dismissed = False
                self._overlay._extend_dismiss()
            return {"ok": True}
        if cmd == "screenshot":
            path = msg["path"]
            pygame.image.save(self._screen, path)
            return {"ok": True}
        if cmd == "quit":
            self._quit()
            return {"ok": True}
        if cmd == "set_config":
            self._config.set(msg["section"], msg["key"], msg["value"])
            if msg.get("section") == "sleep":
                self._sleep.kick()
            if hasattr(self, "_settings"):
                self._settings.sync_from_config()
            return {"ok": True}
        if cmd == "trigger_sync":
            sync = getattr(self, "_sync", None)
            if sync is not None:
                sync.trigger()
            return {"ok": True}
        return {"ok": False, "error": f"unknown command: {cmd}"}


def main() -> None:
    """Entry point for the slideshow CLI."""
    App().run()
