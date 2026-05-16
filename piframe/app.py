from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import queue
import sys
import time

import pygame
import pygame.freetype
from pygame import Rect, Surface

from piframe.assets import Assets
from piframe.clock_widget import ClockWidget
from piframe.config_store import ConfigStore
from piframe.photo_cache import PhotoCache
from piframe.types import AppState, FPS, SCREEN_H, SCREEN_W, TRANS_DURATION, init_events


class SlideshowPlayer:
    def __init__(self, config: ConfigStore, cache: PhotoCache, screen_size):
        self._config = config
        self._cache = cache
        self._w, self._h = screen_size
        self._playlist: list[Path] = []
        self._index: int = 0
        self._current_surf: Surface | None = None
        self._next_surf: Surface | None = None
        self._elapsed: float = 0.0
        self._trans_t: float = 0.0
        self._in_transition: bool = False
        self._direction: int = 1
        self._paused: bool = False
        self._trans_mode: str = "crossfade"

        self._slide_rect: Rect = Rect(0, 0, self._w, self._h)
        self.rescan()

    def rescan(self):
        output_dir = Path(self._config.sync.output_dir)
        exts = {".jpg", ".jpeg", ".png", ".gif"}
        files = [p for p in output_dir.iterdir() if p.suffix.lower() in exts] if output_dir.exists() else []
        self._playlist = self._fisher_yates(files)
        self._index = 0
        if self._playlist:
            self._current_surf = self._cache.get(self._playlist[0], self._config.slideshow.fit_mode)
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
            self._trans_t += dt / trans_dur
            if self._trans_t >= 1.0:
                self._trans_t = 1.0
                self._current_surf = self._next_surf
                self._next_surf = None
                self._in_transition = False
                self._elapsed = 0.0
        else:
            self._elapsed += dt
            if self._elapsed >= interval:
                self.advance()

    def advance(self, direction: int = 1):
        if not self._playlist:
            return
        self._direction = direction
        next_idx = (self._index + direction) % len(self._playlist)
        self._next_surf = self._cache.get(self._playlist[next_idx], self._config.slideshow.fit_mode)
        self._index = next_idx
        self._in_transition = True
        self._trans_t = 0.0

    def go_back(self):
        self.advance(direction=-1)

    def skip(self):
        self.advance(direction=1)

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
                offset = int(self._trans_t * self._w) * self._direction
                screen.blit(self._current_surf, (-offset, 0))
                screen.blit(self._next_surf, (self._w * self._direction - offset, 0))
            else:
                screen.blit(self._next_surf if self._trans_t >= 0.5 else self._current_surf, (0, 0))
        else:
            screen.blit(self._current_surf, (0, 0))

    def draw_pip(self, screen: Surface):
        cx = self._w // 2
        cy = self._h - 20
        pygame.draw.circle(screen, (255, 255, 255, 200), (cx, cy), 6)

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

        parser = argparse.ArgumentParser()
        parser.add_argument("--test-harness", action="store_true")
        parser.add_argument("--mock-wifi", action="store_true")
        self._args = parser.parse_args()

        self._assets = Assets.load()

        config_path = Path(__file__).parent.parent / "config.toml"
        self._config = ConfigStore(config_path)

        self._cache = PhotoCache((SCREEN_W, SCREEN_H))

        self._clock_w = ClockWidget(self._assets)

        self._player = SlideshowPlayer(self._config, self._cache, (SCREEN_W, SCREEN_H))

        self._harness_queue: queue.SimpleQueue = queue.SimpleQueue()
        if self._args.test_harness:
            self._start_harness()

    def run(self) -> None:
        prev_time = time.monotonic()
        while True:
            now = time.monotonic()
            dt = min(now - prev_time, 0.1)
            prev_time = now

            self._process_pygame_events()
            self._drain_harness_queue()
            self._update(dt)
            self._draw()
            pygame.display.flip()
            self._clock.tick(FPS)

    def _process_pygame_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._quit()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._quit()

    def _update(self, dt: float):
        self._player.update(dt)
        if hasattr(self, "_config"):
            self._config.tick(time.monotonic())

    def _draw(self):
        self._player.draw(self._screen)
        if self._config.display.show_clock:
            self._clock_w.draw(self._screen)

    def _quit(self):
        self._clock_w.stop()
        pygame.quit()
        sys.exit(0)

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
                result = self._handle_harness_cmd(msg, conn)
                _ = result
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
        if cmd == "state":
            return {"ok": True, "state": self._state.name}
        elif cmd == "tap":
            x, y = msg["x"], msg["y"]
            ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(x, y), button=1)
            pygame.event.post(ev)
            ev2 = pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(x, y), button=1)
            pygame.event.post(ev2)
            return {"ok": True}
        elif cmd == "swipe":
            x, y, dx, dy, ms = msg["x"], msg["y"], msg["dx"], msg["dy"], msg.get("ms", 300)
            steps = max(5, ms // 16)
            down = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(x, y), button=1)
            pygame.event.post(down)
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
            up = pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(x + dx, y + dy), button=1)
            pygame.event.post(up)
            return {"ok": True}
        elif cmd == "screenshot":
            path = msg["path"]
            pygame.image.save(self._screen, path)
            return {"ok": True}
        elif cmd == "quit":
            self._quit()
            return {"ok": True}
        elif cmd == "set_config":
            self._config.set(msg["section"], msg["key"], msg["value"])
            return {"ok": True}
        elif cmd == "trigger_sync":
            if hasattr(self, "_sync"):
                self._sync.trigger()
            return {"ok": True}
        else:
            return {"ok": False, "error": f"unknown command: {cmd}"}
