"""The devcontainer's env template is the single source for PIFRAME overrides.

Issue #67: the ``PIFRAME_`` override block used to live in a root
``.env.example`` that the devcontainer never loads, while the template that
does feed ``.devcontainer/.env`` documented only the git email. The two files
had diverged, and nothing in the devcontainer's own surface advertised the
OneDrive workflow.

This module pins the invariants that keep them from diverging again:

* exactly one env template exists, and it is the one the devcontainer loads;
* that template documents the OneDrive overrides;
* every doc pointer (config, provider guide, README, run.sh) reaches it.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEVCONTAINER_DIR = REPO_ROOT / ".devcontainer"
ENV_TEMPLATE = DEVCONTAINER_DIR / ".env.example"

#: The fully-qualified path of the template the devcontainer loads.
TEMPLATE_PATH = ".devcontainer/.env.example"


def _no_dangling_template_refs(text: str) -> bool:
    """True when every ``.env.example`` mention is the fully-qualified template.

    ``.env.example`` is a substring of ``.devcontainer/.env.example``, so a
    bare (root) reference is detectable only by counting: if the two counts
    differ, some reference points at a file that no longer exists.
    """
    return text.count(".env.example") == text.count(TEMPLATE_PATH)


def test_single_env_template_is_the_devcontainer_one() -> None:
    """Only one env template exists: the one the devcontainer loads."""
    assert ENV_TEMPLATE.is_file()
    assert not (REPO_ROOT / ".env.example").exists()


def test_env_template_documents_the_onedrive_workflow() -> None:
    """The template the devcontainer loads advertises the OneDrive overrides."""
    text = ENV_TEMPLATE.read_text()
    assert "PIFRAME_SYNC__PROVIDER" in text
    assert "PIFRAME_SYNC__ONEDRIVE__SHARE_URL" in text
    assert "PIFRAME_SYNC__ONEDRIVE__PASSWORD" in text


def test_config_devcontainer_points_at_the_devcontainer_template() -> None:
    """config.devcontainer.toml points at the devcontainer template, not a bare one."""
    text = (REPO_ROOT / "config.devcontainer.toml").read_text()
    assert TEMPLATE_PATH in text
    assert _no_dangling_template_refs(text)


def test_album_providers_points_at_the_devcontainer_template() -> None:
    """The provider guide points at the devcontainer template, not a bare one."""
    text = (REPO_ROOT / "docs" / "album-providers.md").read_text()
    assert TEMPLATE_PATH in text
    assert _no_dangling_template_refs(text)


def test_readme_points_at_the_devcontainer_template() -> None:
    """The README points at the devcontainer template, not a bare one."""
    text = (DEVCONTAINER_DIR / "README.md").read_text()
    assert TEMPLATE_PATH in text
    assert _no_dangling_template_refs(text)


def test_readme_documents_running_against_onedrive() -> None:
    """The README advertises the OneDrive workflow, not just git setup."""
    text = (DEVCONTAINER_DIR / "README.md").read_text()
    assert "PIFRAME_SYNC__PROVIDER=onedrive" in text
    assert "PIFRAME_SYNC__ONEDRIVE__SHARE_URL" in text


def test_run_sh_header_lists_the_onedrive_vars() -> None:
    """run.sh's own header documents the OneDrive overrides it accepts."""
    text = (REPO_ROOT / "eng" / "run.sh").read_text()
    assert "PIFRAME_SYNC__ONEDRIVE__SHARE_URL" in text
    assert "PIFRAME_SYNC__ONEDRIVE__PASSWORD" in text
