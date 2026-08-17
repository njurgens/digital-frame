"""Local directory provider: direct references, no copying or cleanup."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from piframe.album import Album
from piframe.image import IMAGE_EXTENSIONS, Image
from piframe.providers.base import BaseAlbumProvider

if TYPE_CHECKING:
    from piframe.config_store import ConfigStore


class LocalConfig:
    """Local provider settings, read from the ``[sync.local]`` section."""

    def __init__(self, config: ConfigStore) -> None:
        """Wrap the config store."""
        self._config = config

    @property
    def source_dir(self) -> Path:
        """Directory whose contents the provider exposes."""
        raw = self._config.read_nested(
            "sync", "local", "source_dir", default="~/Pictures/slideshow"
        )
        return Path(str(raw)).expanduser()


class LocalProvider(BaseAlbumProvider):
    """Exposes the images in a user-managed local directory.

    Returns direct references to the source files: no copying, no
    caching, no cleanup.  The user controls the source directory
    contents (FR-4).

    For configuration and how to add a new provider, see
    ``docs/album-providers.md``.
    """

    def __init__(self, config: LocalConfig) -> None:
        """Create the provider with its config wrapper."""
        super().__init__()
        self._config = config

    @property
    def storage_dir(self) -> Path:
        """Directory whose contents this provider exposes."""
        return self._config.source_dir

    def _do_sync(self) -> Album:
        source = self._config.source_dir
        if not source.is_dir():
            logging.warning("LocalProvider: source directory %s does not exist", source)
            return Album()
        images = [
            Image(path)
            for path in sorted(source.iterdir())
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        ]
        return Album.from_images(images)
