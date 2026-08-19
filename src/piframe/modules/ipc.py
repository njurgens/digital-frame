"""IPC module: constructs the socket command server from config."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from piframe.config_store import ConfigStore
from piframe.di import DimModule
from piframe.ipc import Executor, IpcServer


class IpcModule(DimModule["IpcServer | None"]):
    """Construct the IPC server when the ``[ipc]`` section enables it."""

    def create(
        self,
        config: ConfigStore,
        *,
        socket_path: Path,
        executors: Mapping[str, Executor],
        **deps: object,
    ) -> IpcServer | None:
        """Build and start the IPC server, or return None when the API is disabled.

        Args:
            config: Application configuration.
            socket_path: Where to bind the socket (the resolved runtime dir).
            executors: The dispatch table: method name to executor callable.
            **deps: Unused.

        Returns:
            A started ``IpcServer``, or None when ``[ipc] enabled`` is false.

        """
        if not config.ipc.enabled:
            return None
        return IpcServer(socket_path, executors)
