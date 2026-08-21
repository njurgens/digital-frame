"""Test the --provider and --config flags on eng/run.sh.

The app has no --provider or --config option (its CLI only takes --windowed);
the provider reaches it through the PIFRAME_SYNC__PROVIDER env override and the
config path through PIFRAME_CONFIG_PATH. run.sh's flags set those variables, so
these tests stub ``uv`` on PATH to capture the environment run.sh hands to the
app, without launching the real slideshow.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: A stand-in for the ``uv`` console launcher: record the environment the app
#: would receive, then exit 0 so ``run.sh``'s foreground ``exec`` returns cleanly.
STUB_UV = """#!/usr/bin/env bash
if [[ -n "${PIFRAME_RUNSH_TEST_CAPTURE:-}" ]]; then
  {
    printf 'PROVIDER=%s\\n' "${PIFRAME_SYNC__PROVIDER:-}"
    printf 'CONFIG_PATH=%s\\n' "${PIFRAME_CONFIG_PATH:-}"
    printf 'ARGS=%s\\n' "$*"
  } > "$PIFRAME_RUNSH_TEST_CAPTURE"
fi
exit 0
"""


def _run_run_sh(
    tmp_path: Path,
    *argv: str,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run ``eng/run.sh`` with a stub ``uv`` on PATH and return the process.

    The stub writes the provider and config-path values (and argv) it would
    hand the app to a capture file in *tmp_path*; the test then reads them back.
    """
    stub_dir = tmp_path / "stubbin"
    stub_dir.mkdir(exist_ok=True)
    stub = stub_dir / "uv"
    stub.write_text(STUB_UV)
    stub.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{stub_dir}{os.pathsep}{env['PATH']}"
    env["PIFRAME_RUNSH_TEST_CAPTURE"] = str(tmp_path / "capture.txt")
    # Start from a clean slate so inherited overrides can't leak in.
    env.pop("PIFRAME_SYNC__PROVIDER", None)
    env.pop("PIFRAME_CONFIG_PATH", None)
    if env_extra:
        env.update(env_extra)

    return subprocess.run(
        ["bash", "eng/run.sh", *argv],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _captured(tmp_path: Path, key: str) -> str:
    text = (tmp_path / "capture.txt").read_text()
    for line in text.splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1]
    raise AssertionError(f"no {key} line in capture: {text!r}")


# --- --provider --------------------------------------------------------------


def test_provider_flag_reaches_the_app_env(tmp_path: Path) -> None:
    """``--provider onedrive`` sets PIFRAME_SYNC__PROVIDER=onedrive for the app."""
    proc = _run_run_sh(tmp_path, "-f", "--provider", "onedrive")
    assert proc.returncode == 0, proc.stderr
    assert _captured(tmp_path, "PROVIDER") == "onedrive"


def test_provider_flag_beats_an_inherited_env_var(tmp_path: Path) -> None:
    """An explicit --provider overrides a PIFRAME_SYNC__PROVIDER already in the env."""
    proc = _run_run_sh(
        tmp_path, "-f", "--provider", "local", env_extra={"PIFRAME_SYNC__PROVIDER": "onedrive"}
    )
    assert proc.returncode == 0, proc.stderr
    assert _captured(tmp_path, "PROVIDER") == "local"


def test_env_provider_passes_through_when_no_flag(tmp_path: Path) -> None:
    """Without --provider, an env PIFRAME_SYNC__PROVIDER is honored, not reset to local."""
    proc = _run_run_sh(tmp_path, "-f", env_extra={"PIFRAME_SYNC__PROVIDER": "google"})
    assert proc.returncode == 0, proc.stderr
    assert _captured(tmp_path, "PROVIDER") == "google"


def test_provider_flag_without_value_is_a_usage_error(tmp_path: Path) -> None:
    """``--provider`` with no value is a usage error (exit 2), before the app starts."""
    proc = _run_run_sh(tmp_path, "-f", "--provider")
    assert proc.returncode == 2


# --- --config ----------------------------------------------------------------


def test_config_flag_reaches_the_app_env(tmp_path: Path) -> None:
    """``--config <path>`` sets PIFRAME_CONFIG_PATH=<path> for the app (no copy)."""
    proc = _run_run_sh(tmp_path, "-f", "--config", "config.devcontainer.toml")
    assert proc.returncode == 0, proc.stderr
    assert _captured(tmp_path, "CONFIG_PATH") == "config.devcontainer.toml"


def test_config_flag_beats_an_inherited_env_var(tmp_path: Path) -> None:
    """An explicit --config overrides a PIFRAME_CONFIG_PATH already in the env."""
    proc = _run_run_sh(
        tmp_path, "-f", "--config", "a.toml", env_extra={"PIFRAME_CONFIG_PATH": "b.toml"}
    )
    assert proc.returncode == 0, proc.stderr
    assert _captured(tmp_path, "CONFIG_PATH") == "a.toml"


def test_env_config_path_passes_through_when_no_flag(tmp_path: Path) -> None:
    """Without --config, an env PIFRAME_CONFIG_PATH is honored (no bootstrap, no copy)."""
    proc = _run_run_sh(tmp_path, "-f", env_extra={"PIFRAME_CONFIG_PATH": "c.toml"})
    assert proc.returncode == 0, proc.stderr
    assert _captured(tmp_path, "CONFIG_PATH") == "c.toml"


def test_no_config_flag_or_env_leaves_path_unset(tmp_path: Path) -> None:
    """With neither --config nor PIFRAME_CONFIG_PATH, the app uses its default path."""
    proc = _run_run_sh(tmp_path, "-f")
    assert proc.returncode == 0, proc.stderr
    assert _captured(tmp_path, "CONFIG_PATH") == ""


def test_config_flag_without_value_is_a_usage_error(tmp_path: Path) -> None:
    """``--config`` with no value is a usage error (exit 2), before the app starts."""
    proc = _run_run_sh(tmp_path, "-f", "--config")
    assert proc.returncode == 2
