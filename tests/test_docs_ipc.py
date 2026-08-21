"""The docs/ipc.md method table stays in sync with the app and the client (D-5)."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import piframe.app as app_module
from piframe import ipc_client

REPO_ROOT = Path(__file__).resolve().parents[1]


def _doc_methods() -> set[str]:
    """The method names in docs/ipc.md's method table (one per row)."""
    text = (REPO_ROOT / "docs" / "ipc.md").read_text()
    return set(re.findall(r"^\|\s*`([a-z_]+)`\s*\|", text, re.M))


def _registered_subcommands() -> set[str]:
    """The subcommands the piframe-ipc parser actually registers."""
    parser = ipc_client._build_parser()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    return set()


def test_method_names_match_across_doc_app_and_client() -> None:
    """The doc table, the app's dispatch table, and the client all agree."""
    assert _doc_methods() == set(app_module.IPC_METHOD_NAMES)
    assert set(ipc_client.COMMANDS) == set(app_module.IPC_METHOD_NAMES)
    assert _registered_subcommands() == set(ipc_client.COMMANDS)


def test_every_command_is_a_registered_subcommand() -> None:
    """Each documented command is a subcommand (its --help exits 0)."""
    for name in sorted(ipc_client.COMMANDS):
        assert ipc_client.main([name, "--help"]) == 0


def test_unknown_command_is_a_usage_error() -> None:
    """An unregistered command is a usage error (exit 2)."""
    assert ipc_client.main(["definitely-not-a-command"]) == 2
