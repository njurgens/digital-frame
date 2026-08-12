"""Dependency-injection protocol for service construction."""
from __future__ import annotations

from typing import Any, Protocol

from piframe.config_store import ConfigStore


class DimModule[T](Protocol):
    """
    Protocol for modules that construct a service from config and dependencies.

    Subclasses decide which concrete implementation to instantiate based on
    configuration values, keeping conditional logic out of ``App.__init__``.
    """

    def create(self, config: ConfigStore, **deps: Any) -> T:
        """
        Construct and return a service instance.

        Args:
            config: Application configuration store.
            **deps: Optional dependency objects required by the service.

        Returns:
            A fully initialised service instance.

        """
        ...
