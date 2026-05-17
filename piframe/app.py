from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import time

import pygame
import pygame.freetype
from pygame import Rect, Surface

from piframe.assets import Assets, IC_PAUSE
from piframe.backlight import BacklightController
from piframe.clock_widget import ClockWidget
from piframe.config_store import ConfigStore
from piframe.keyboard import Keyboard
from piframe.overlay_ui import OverlayUI
from piframe.photo_cache import PhotoCache
from piframe.settings_panel import SettingsPanel
from piframe.sleep_scheduler import SleepScheduler
from piframe.sync_service import SyncService
from piframe.updater import apply_update, check_update
from piframe.wifi_manager import WifiManager
from piframe.widgets.confirm_dialog import ConfirmDialog
from piframe import types as app_types
from piframe.types import AppState, FPS, SCREEN_H, SCREEN_W, SIDEBAR_W, TRANS_DURATION, WAKE_GRACE, init_events

_SWIPE_MIN_DX = 60
_SWIPE_MAX_DT = 0.4
_SWIPE_MAX_SLOPE = 0.5
_TAP_MAX_DIST = 20.0


class MockWifiManager:
    def scan(self):
        import threading as _threading
        from piframe.types import WifiNetwork, WifiResult
        from piframe import types as _types

        def _post() -> None:
            import time as _time
            _time.sleep(0.2)
            networks = [
                WifiNetwork(ssid="MockNetwork-WPA2", security="WPA2", signal=85),
                WifiNetwork(ssid="MockNetwork-Open", security="--", signal=60),
            ]
            result = WifiResult("scan", True, data=networks)
            try:
                if _types.EVT_WIFI_RESULT is not None:
                    pygame.event.post(pygame.event.Event(_types.EVT_WIFI_RESULT, result=result))
            except Exception:
                pass

        _threading.Thread(target=_post, daemon=True).start()

    def connect(self, ssid, password=None):
        _ = ssid, password
        return None

    def forget(self, ssid):
        _ = ssid
        return None

    def disconnect(self):
        return None

    def get_status(self):
        return None


class SlideshowPlayer:
    def __init__(self, config: ConfigStore, cache: PhotoCache, screen_size, assets: Assets | None = None):
        self._config = config
        self._cache = cache
        self._assets = assets
        self._w, self._h = screen_size
        self._playlist: list[Path] = []
        self._index: int = 0
        self._current_surf: Surface | None = None
        self._next_surf: Surface | None = None
        self._elapsed: float = 0.0
        self._trans_t: float = 0.0
        self._in_transition: bool = False
        self._trans_start: float = 0.0
        self._direction: int = 1
        self._paused: bool = False

        self._slide_rect: Rect = Rect(0, 0, self._w, self._h)
        self.rescan()

    def rescan(self):
        output_dir = Path(self._config.sync.output_dir)
        exts = {".jpg", ".jpeg", ".png", ".gif"}
        files = sorted([p for p in output_dir.iterdir() if p.suffix.lower() in exts]) if output_dir.exists() else []
        self._playlist = files
        if self._config.slideshow.shuffle:
            self._playlist = self._fisher_yates(self._playlist)
        self._index = 0
        if self._playlist:
            self._current_surf = self._cache.get(
                self._playlist[0],
                self._config.slideshow.fit_mode,
                self._w,
                self._h,
            )
        else:
            self._current_surf = None

    def _fisher_yates(self, items: list) -> list:
        import random

        lst = list(items)
        for i in range(len(lst) - 1, 0, -1):
            j = random.randint(0, i)
            lst[i], lst[j] = lst[j], lst[i]
        return lst

    def update(self, dt: float):
        if self._paused or not self._playlist:
            return
        interval = self._config.slideshow.interval
        trans_dur = TRANS_DURATION

        if self._in_transition:
            elapsed = time.monotonic() - self._trans_start
            self._trans_t = min(1.0, elapsed / trans_dur)
            if self._trans_t >= 1.0:
                self._commit_transition()
        else:
            self._elapsed += dt
            if self._elapsed >= interval:
                self.advance()

    def advance(self, direction: int = 1):
        if not self._playlist:
            return
        self._direction = direction
        next_idx = (self._index + direction) % len(self._playlist)
        self._next_surf = self._cache.get(
            self._playlist[next_idx],
            self._config.slideshow.fit_mode,
            self._w,
            self._h,
        )
        self._index = next_idx
        self._start_transition()

    def _start_transition(self) -> None:
        self._trans_start = time.monotonic()
        self._in_transition = True
        self._trans_t = 0.0

    def _commit_transition(self) -> None:
        self._trans_t = 1.0
        self._current_surf = self._next_surf
        self._next_surf = None
        self._in_transition = False
        self._elapsed = 0.0

    def go_back(self):
        self.advance(direction=-1)

    def skip(self):
        self.advance(direction=1)

    def skip_next(self):
        return self.skip()

    def draw(self, screen: Surface):
        if self._current_surf is None:
            screen.fill((0, 0, 0))
            return
        if self._in_transition and self._next_surf is not None:
            trans = self._config.slideshow.transition
            if trans == "crossfade":
                screen.blit(self._current_surf, (0, 0))
                alpha_surf = self._next_surf.copy()
                alpha_surf.set_alpha(int(self._trans_t * 255))
                screen.blit(alpha_surf, (0, 0))
            elif trans == "slide":
                cur_x = int(-self._direction * self._trans_t * self._w)
                next_x = int(self._direction * (1.0 - self._trans_t) * self._w)
                screen.blit(self._current_surf, (cur_x, 0))
                screen.blit(self._next_surf, (next_x, 0))
            else:
                screen.blit(self._next_surf if self._trans_t >= 0.5 else self._current_surf, (0, 0))
        else:
            screen.blit(self._current_surf, (0, 0))

    def draw_pip(self, screen: Surface):
        if not self._paused:
            return
        pill_rect = pygame.Rect(12, 762, 26, 26)
        pygame.draw.rect(screen, (0, 0, 0), pill_rect, border_radius=13)
        if self._assets is not None:
            icon_font = self._assets.icon(24)
            icon_surf, _ = icon_font.render(IC_PAUSE, (255, 255, 255))
            screen.blit(
                icon_surf,
                (
                    pill_rect.centerx - icon_surf.get_width() // 2,
                    pill_rect.centery - icon_surf.get_height() // 2,
                ),
            )

    @property
    def is_paused(self) -> bool:
        return self._paused

    @is_paused.setter
    def is_paused(self, value: bool):
        self._paused = value


class App:
    def __init__(self) -> None:
        pygame.init()
        pygame.freetype.init()
        init_events()

        Path("/tmp/slideshow.pid").write_text(str(os.getpid()))

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

        parser = argparse.ArgumentParser()
        parser.add_argument("--test-harness", action="store_true")
        parser.add_argument("--mock-wifi", action="store_true")
        self._args = parser.parse_args()

        self._assets = Assets.load()

        config_path = Path(__file__).parent.parent / "config.toml"
        self._config = ConfigStore(config_path)

        self._cache = PhotoCache(cache_dir=Path(self._config.sync.cache_dir))

        self._clock_w = ClockWidget(self._assets)

        self._sync: SyncService | None = SyncService(self._config)
        self._player = SlideshowPlayer(self._config, self._cache, (SCREEN_W, SCREEN_H), self._assets)
        self._backlight = BacklightController()
        self._overlay = OverlayUI(self._assets, self._config)
        self._wifi = MockWifiManager() if self._args.mock_wifi else WifiManager()
        self._settings = SettingsPanel(
            self._assets,
            self._config,
            on_brightness_change=self._on_brightness_change,
            on_focus_text=self._on_focus_text,
            wifi_manager=self._wifi,
            sync_service=self._sync,
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

    def _on_focus_text(self, field) -> None:
        self._keyboard.attach(field)
        self._state = AppState.KEYBOARD

    def _on_keyboard_done(self) -> None:
        self._state = AppState.SETTINGS

    def run(self) -> None:
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
                    if event.type == pygame.MOUSEBUTTONDOWN and not kb_rect.collidepoint(event.pos):
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
            elif event.type == pygame.MOUSEMOTION and event.buttons[0] and self._state == AppState.OVERLAY:
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
        if elapsed < _SWIPE_MAX_DT and abs_dx > _SWIPE_MIN_DX and abs_dy <= abs_dx * _SWIPE_MAX_SLOPE:
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
        if getattr(self, "_sync", None) is not None:
            self._sync.stop()
        self._sleep.stop()
        self._clock_w.stop()
        self._config.flush_now()

    def restart(self) -> None:
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

    def _harness_loop(self, server):
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

    def _handle_harness_cmd(self, msg: dict, conn) -> None:
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
            if hasattr(self, "_sync"):
                self._sync.trigger()
            return {"ok": True}
        return {"ok": False, "error": f"unknown command: {cmd}"}
