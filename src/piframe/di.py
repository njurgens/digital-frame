from __future__ import annotations

from typing import Any, Protocol

from piframe.config_store import ConfigStore


class DimModule[T](Protocol):
    """A module that constructs a service from config and optional dependencies."""

    def create(self, config: ConfigStore, **deps: Any) -> T: ...
