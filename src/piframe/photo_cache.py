from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

import pygame
from PIL import Image, ImageEnhance, ImageFilter

from piframe.types import SCREEN_H, SCREEN_W

_CACHE_VERSION = 2
MAX_CACHE = 6
BLUR_RADIUS = 40

try:
    _LANCZOS = Image.Resampling.LANCZOS
except AttributeError:
    _LANCZOS = Image.LANCZOS


class PhotoCache:
    def __init__(
        self,
        screen_size: tuple[int, int] = (SCREEN_W, SCREEN_H),
        cache_dir: Path | None = None,
    ):
        self._w, self._h = screen_size
        self._cache_dir = Path(cache_dir) if cache_dir is not None else Path.home() / ".cache" / "framesync"
        self._fit_mode = "fit"
        self._cache: OrderedDict[str, pygame.Surface] = OrderedDict()
        self._last_path: Path | None = None

    def get(
        self,
        path: Path,
        fit_mode: str,
        screen_w: int | None = None,
        screen_h: int | None = None,
    ) -> pygame.Surface:
        if screen_w is not None and screen_h is not None:
            self._w, self._h = screen_w, screen_h
        self._fit_mode = fit_mode
        key = self._key(path, fit_mode)
        surf = self._cache.get(key)
        if surf is not None:
            self._cache.move_to_end(key)
            return surf

        disk_path = self._cache_dir / f"{key}.png"
        if disk_path.exists():
            surf = pygame.image.load(str(disk_path)).convert()
            self._put(key, surf)
            return surf

        surf = self._render(path, fit_mode)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        pygame.image.save(surf, str(disk_path))
        self._put(key, surf)
        return surf

    def _key(self, path: Path, fit_mode: str) -> str:
        return f"{path.stem}_{fit_mode}_v{_CACHE_VERSION}"

    def _put(self, key: str, surf: pygame.Surface) -> None:
        self._cache[key] = surf
        self._cache.move_to_end(key)
        if len(self._cache) > MAX_CACHE:
            self._cache.popitem(last=False)

    def _apply_exif_orientation(self, img: Image.Image) -> Image.Image:
        orientation = 1
        try:
            exif = img._getexif()
            if exif is not None:
                orientation = exif.get(274, 1)
        except AttributeError:
            orientation = 1

        if orientation == 2:
            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif orientation == 3:
            img = img.transpose(Image.Transpose.ROTATE_180)
        elif orientation == 4:
            img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        elif orientation == 5:
            img = img.transpose(Image.Transpose.TRANSPOSE)
        elif orientation == 6:
            img = img.transpose(Image.Transpose.ROTATE_270)
        elif orientation == 7:
            img = img.transpose(Image.Transpose.TRANSVERSE)
        elif orientation == 8:
            img = img.transpose(Image.Transpose.ROTATE_90)
        return img

    def _render(self, path: Path, fit_mode: str) -> pygame.Surface:
        img = Image.open(path)
        img = self._apply_exif_orientation(img)
        img = img.convert("RGB")

        if fit_mode == "fill":
            scale = max(self._w / img.width, self._h / img.height)
            w = int(img.width * scale)
            h = int(img.height * scale)
            filled = img.resize((w, h), _LANCZOS)
            crop_x = (w - self._w) // 2
            crop_y = (h - self._h) // 2
            final_img = filled.crop((crop_x, crop_y, crop_x + self._w, crop_y + self._h))
        else:
            scale_bg = max(self._w / img.width, self._h / img.height)
            bg_w = int(img.width * scale_bg)
            bg_h = int(img.height * scale_bg)
            bg = img.resize((bg_w, bg_h), _LANCZOS)
            bg_x = (bg_w - self._w) // 2
            bg_y = (bg_h - self._h) // 2
            bg = bg.crop((bg_x, bg_y, bg_x + self._w, bg_y + self._h))
            bg = bg.filter(ImageFilter.GaussianBlur(BLUR_RADIUS))
            bg = ImageEnhance.Brightness(bg).enhance(0.4)

            scale_fg = min(self._w / img.width, self._h / img.height)
            fg_w = int(img.width * scale_fg)
            fg_h = int(img.height * scale_fg)
            fg = img.resize((fg_w, fg_h), _LANCZOS)

            final_img = bg.copy()
            paste_x = (self._w - fg_w) // 2
            paste_y = (self._h - fg_h) // 2
            final_img.paste(fg, (paste_x, paste_y))

        return pygame.image.frombuffer(final_img.tobytes(), final_img.size, "RGB")

    def invalidate(self) -> None:
        self._cache.clear()

    def invalidate_disk(self) -> None:
        if self._cache_dir.exists():
            for f in self._cache_dir.glob("*.png"):
                f.unlink(missing_ok=True)

    def set_fit_mode(self, mode: str) -> None:
        self._fit_mode = mode
        self.invalidate_disk()
        self.invalidate()

    def prefetch(self, path: Path, fit_mode: str, screen_w: int, screen_h: int) -> None:
        key = self._key(path, fit_mode)
        if key not in self._cache:
            self.get(path, fit_mode, screen_w, screen_h)
