from __future__ import annotations

import json
import shutil
import tarfile
import urllib.request
from pathlib import Path

GITHUB_API = "https://api.github.com/repos/{repo}/releases/latest"


def check_update(repo: str) -> tuple[str, str]:
    url = GITHUB_API.format(repo=repo)
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.loads(resp.read())
    return data["tag_name"], data["tarball_url"]


def _safe_extract(tf: tarfile.TarFile, destination: Path) -> None:
    base = destination.resolve()
    for member in tf.getmembers():
        target = (destination / member.name).resolve()
        if not str(target).startswith(str(base)):
            raise ValueError("refusing unsafe archive path")
    tf.extractall(destination)


def apply_update(tarball_url: str) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    staging_dir = repo_root / ".update-staging"
    staging_tar = staging_dir / "release.tar.gz"
    extract_dir = staging_dir / "extract"

    shutil.rmtree(staging_dir, ignore_errors=True)
    extract_dir.mkdir(parents=True, exist_ok=True)

    try:
        with urllib.request.urlopen(tarball_url, timeout=30) as resp:
            staging_tar.write_bytes(resp.read())
        with tarfile.open(staging_tar) as tf:
            _safe_extract(tf, extract_dir)
        src = next(extract_dir.iterdir())
        shutil.copytree(
            src,
            repo_root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("config.toml", "assets", ".git"),
        )
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)
