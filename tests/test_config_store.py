"""Tests for ConfigStore loading, merging, and flushing."""

import logging
import os
import time
import tomllib
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pytest

from piframe.config_store import ConfigStore, _remove_path, _set_path
from piframe.providers import ProviderName


def write_toml(path: Path, content: str) -> None:
    """Write toml."""
    path.write_text(content)


def test_load_from_file(tmp_path: Path) -> None:
    """Load from file."""
    p = tmp_path / "config.toml"
    write_toml(p, "[slideshow]\ninterval = 15\n")
    cfg = ConfigStore(p)
    assert cfg.slideshow.interval == 15.0


def test_load_missing_file_uses_defaults(tmp_path: Path) -> None:
    """Load missing file uses defaults."""
    p = tmp_path / "nonexistent.toml"
    cfg = ConfigStore(p)
    assert cfg.slideshow.interval == 30.0
    assert cfg.display.brightness == 72


def test_load_malformed_toml_creates_backup(tmp_path: Path) -> None:
    """Load malformed toml creates backup."""
    p = tmp_path / "config.toml"
    p.write_text("this is not valid [[[ toml")
    cfg = ConfigStore(p)
    assert cfg.slideshow.interval == 30.0
    assert (tmp_path / "config.bak").exists()


def test_interval_clamped_below_min(tmp_path: Path) -> None:
    """Interval clamped below min."""
    p = tmp_path / "config.toml"
    write_toml(p, "[slideshow]\ninterval = -5.0\n")
    cfg = ConfigStore(p)
    assert cfg.slideshow.interval == 1.0


def test_brightness_clamped_above_max(tmp_path: Path) -> None:
    """Brightness clamped above max."""
    p = tmp_path / "config.toml"
    write_toml(p, "[display]\nbrightness = 200\n")
    cfg = ConfigStore(p)
    assert cfg.display.brightness == 100


def test_set_and_debounce_write(tmp_path: Path) -> None:
    """Set and debounce write."""
    p = tmp_path / "config.toml"
    cfg = ConfigStore(p)
    now = time.monotonic()
    cfg.set("display", "brightness", 42)
    cfg.tick(now + 0.3)
    assert not p.exists() or "42" not in p.read_text()
    cfg.tick(now + 0.6)
    assert p.exists()
    assert "42" in p.read_text()


def test_flush_now_writes_immediately(tmp_path: Path) -> None:
    """Flush now writes immediately."""
    p = tmp_path / "config.toml"
    cfg = ConfigStore(p)
    cfg.set("display", "brightness", 77)
    cfg.flush_now()
    assert p.exists()
    assert "77" in p.read_text()


def test_protected_keys_never_overwritten(tmp_path: Path) -> None:
    """Protected keys (provider, OneDrive credentials) are never persisted."""
    p = tmp_path / "config.toml"
    write_toml(
        p,
        "[sync]\n"
        'provider = "onedrive"\n'
        "[sync.onedrive]\n"
        'share_url = "https://secret"\n'
        'password = "pw"\n',
    )
    cfg = ConfigStore(p)
    cfg.set("sync", "provider", "google")
    cfg.flush_now()
    with p.open("rb") as f:
        data = tomllib.load(f)
    assert data["sync"]["provider"] == "onedrive"
    assert data["sync"]["onedrive"]["share_url"] == "https://secret"
    assert data["sync"]["onedrive"]["password"] == "pw"


def test_sync_provider_default_local(tmp_path: Path) -> None:
    """Default provider is LOCAL when no config file exists."""
    cfg = ConfigStore(tmp_path / "nonexistent.toml")
    assert cfg.sync.provider is ProviderName.LOCAL


def test_sync_provider_from_file(tmp_path: Path) -> None:
    """Provider = 'onedrive' in TOML is read as ProviderName.ONEDRIVE."""
    p = tmp_path / "config.toml"
    write_toml(p, '[sync]\nprovider = "onedrive"\n')
    cfg = ConfigStore(p)
    assert cfg.sync.provider is ProviderName.ONEDRIVE


def test_sync_provider_invalid_raises(tmp_path: Path) -> None:
    """An unknown provider value raises a clear error (no silent fallback)."""
    p = tmp_path / "config.toml"
    write_toml(p, '[sync]\nprovider = "dropbox"\n')
    cfg = ConfigStore(p)
    with pytest.raises(ValueError, match="Unknown sync provider"):
        _ = cfg.sync.provider


def test_sync_interval_minutes_default(tmp_path: Path) -> None:
    """interval_minutes defaults to 60."""
    cfg = ConfigStore(tmp_path / "nonexistent.toml")
    assert cfg.sync.interval_minutes == 60


def test_read_nested_success(tmp_path: Path) -> None:
    """read_nested returns a value from a provider sub-section."""
    p = tmp_path / "config.toml"
    write_toml(p, '[sync.onedrive]\nshare_url = "https://example.com"\n')
    cfg = ConfigStore(p)
    assert cfg.read_nested("sync", "onedrive", "share_url") == "https://example.com"


def test_read_nested_missing_intermediate(tmp_path: Path) -> None:
    """read_nested with a missing intermediate key returns the default."""
    cfg = ConfigStore(tmp_path / "nonexistent.toml")
    assert cfg.read_nested("sync", "nonexistent", "key", default="fallback") == "fallback"


def test_read_nested_missing_leaf(tmp_path: Path) -> None:
    """read_nested with a missing leaf key returns the default."""
    cfg = ConfigStore(tmp_path / "nonexistent.toml")
    assert cfg.read_nested("sync", "onedrive", "nonexistent", default="x") == "x"


def test_sync_nested_defaults_exist(tmp_path: Path) -> None:
    """_DEFAULTS['sync'] contains nested dicts for onedrive, local, google."""
    cfg = ConfigStore(tmp_path / "nonexistent.toml")
    assert cfg.read_nested("sync", "onedrive", "share_url") == ""
    assert cfg.read_nested("sync", "onedrive", "password") == ""
    assert cfg.read_nested("sync", "onedrive", "cache_dir") == "~/.cache/piframe/onedrive"
    assert cfg.read_nested("sync", "local", "source_dir") == "~/Pictures/slideshow"
    assert cfg.read_nested("sync", "google") == {}


def test_deep_merge_preserves_sibling_defaults(tmp_path: Path) -> None:
    """A partial [sync.onedrive] in the file keeps default sibling keys."""
    p = tmp_path / "config.toml"
    write_toml(p, '[sync.onedrive]\nshare_url = "https://example.com"\n')
    cfg = ConfigStore(p)
    assert cfg.read_nested("sync", "onedrive", "share_url") == "https://example.com"
    assert cfg.read_nested("sync", "onedrive", "password") == ""
    assert cfg.read_nested("sync", "onedrive", "cache_dir") == "~/.cache/piframe/onedrive"


def test_env_override_flat_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PIFRAME__ env vars override flat config keys with type coercion."""
    monkeypatch.setenv("PIFRAME__SLIDESHOW__INTERVAL", "15")
    monkeypatch.setenv("PIFRAME__DISPLAY__BRIGHTNESS", "40")
    monkeypatch.setenv("PIFRAME__SLIDESHOW__SHUFFLE", "false")
    cfg = ConfigStore(tmp_path / "nonexistent.toml")
    assert cfg.slideshow.interval == 15.0
    assert cfg.display.brightness == 40
    assert cfg.slideshow.shuffle is False


def test_env_override_nested_provider_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PIFRAME__ env vars override nested provider keys."""
    monkeypatch.setenv("PIFRAME__SYNC__PROVIDER", "onedrive")
    monkeypatch.setenv("PIFRAME__SYNC__ONEDRIVE__SHARE_URL", "https://injected")
    monkeypatch.setenv("PIFRAME__SYNC__ONEDRIVE__PASSWORD", "s3cret")
    monkeypatch.setenv("PIFRAME__SYNC__LOCAL__SOURCE_DIR", "/tmp/photos")
    cfg = ConfigStore(tmp_path / "nonexistent.toml")
    assert cfg.sync.provider is ProviderName.ONEDRIVE
    assert cfg.read_nested("sync", "onedrive", "share_url") == "https://injected"
    assert cfg.read_nested("sync", "onedrive", "password") == "s3cret"
    assert cfg.read_nested("sync", "local", "source_dir") == "/tmp/photos"


def test_env_override_unknown_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown env var paths are silently ignored (no new sections created)."""
    monkeypatch.setenv("PIFRAME__NONSENSE__KEY", "value")
    monkeypatch.setenv("PIFRAME__SYNC__ONEDRIVE__FAKE", "value")
    cfg = ConfigStore(tmp_path / "nonexistent.toml")
    assert "nonsense" not in cfg._data
    assert cfg.read_nested("sync", "onedrive", "fake", default=None) is None


def test_env_override_bad_number_keeps_existing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-numeric env value for a numeric key keeps the existing value."""
    monkeypatch.setenv("PIFRAME__DISPLAY__BRIGHTNESS", "not-a-number")
    cfg = ConfigStore(tmp_path / "nonexistent.toml")
    assert cfg.display.brightness == 72


def test_env_override_clamped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Env overrides are clamped like file values."""
    monkeypatch.setenv("PIFRAME__DISPLAY__BRIGHTNESS", "250")
    cfg = ConfigStore(tmp_path / "nonexistent.toml")
    assert cfg.display.brightness == 100


def test_flush_does_not_persist_env_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Env-injected secrets are never written to the file (V-4)."""
    monkeypatch.setenv("PIFRAME__SYNC__ONEDRIVE__PASSWORD", "s3cret")
    p = tmp_path / "config.toml"
    write_toml(p, '[sync]\nprovider = "onedrive"\n')
    cfg = ConfigStore(p)
    assert cfg.read_nested("sync", "onedrive", "password") == "s3cret"
    cfg.set("display", "brightness", 55)
    cfg.flush_now()
    with p.open("rb") as f:
        data = tomllib.load(f)
    assert data["display"]["brightness"] == 55
    # The secret is not in the file (key absent, not the injected value).
    assert data["sync"]["onedrive"].get("password") in (None, "")
    # The in-memory value keeps working for the running app.
    assert cfg.read_nested("sync", "onedrive", "password") == "s3cret"


def test_flush_restores_file_secret_over_memory(tmp_path: Path) -> None:
    """Without an env var, a file-edited protected key wins on the next flush."""
    p = tmp_path / "config.toml"
    write_toml(p, '[sync.onedrive]\npassword = "filepw"\n')
    cfg = ConfigStore(p)
    # Simulate the user editing the file while the app is running.
    write_toml(p, '[sync.onedrive]\npassword = "editedpw"\n')
    cfg.flush_now()
    assert cfg.read_nested("sync", "onedrive", "password") == "editedpw"
    with p.open("rb") as f:
        data = tomllib.load(f)
    assert data["sync"]["onedrive"]["password"] == "editedpw"


def test_writer_nested_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The TOML writer handles nested sub-sections without corrupting the file."""
    monkeypatch.setenv("PIFRAME__SYNC__ONEDRIVE__CACHE_DIR", "/tmp/od-cache")
    p = tmp_path / "config.toml"
    write_toml(p, '[sync]\nprovider = "onedrive"\n')
    cfg = ConfigStore(p)
    cfg.flush_now()
    with p.open("rb") as f:
        data = tomllib.load(f)
    assert data["sync"]["provider"] == "onedrive"
    assert data["sync"]["onedrive"]["cache_dir"] == "/tmp/od-cache"
    # A protected key absent from the file is never written by the app.
    assert "share_url" not in data["sync"]["onedrive"]
    # The file must still be valid, complete TOML with all default sections.
    assert data["slideshow"]["interval"] == 30.0


def test_writer_escapes_special_characters(tmp_path: Path) -> None:
    """String values with quotes and backslashes round-trip through the writer."""
    p = tmp_path / "config.toml"
    cfg = ConfigStore(p)
    cfg.set("system", "timezone", 'weird "tz" \\ path')
    cfg.flush_now()
    with p.open("rb") as f:
        data = tomllib.load(f)
    assert data["system"]["timezone"] == 'weird "tz" \\ path'


def test_set_path_stops_at_scalar() -> None:
    """_set_path does not descend through a scalar intermediate value."""
    data: dict = {"sync": {"provider": "local"}}
    _set_path(data, ("sync", "provider", "x"), "v")
    assert data["sync"]["provider"] == "local"


def test_remove_path_stops_at_scalar() -> None:
    """_remove_path does not descend through a scalar intermediate value."""
    data: dict = {"sync": {"provider": "local"}}
    _remove_path(data, ("sync", "provider", "x"))
    assert data["sync"]["provider"] == "local"


def test_load_directory_named_config_uses_defaults(tmp_path: Path) -> None:
    """A directory at the config path fails to load and to back up; defaults win."""
    d = tmp_path / "config.toml"
    d.mkdir()
    cfg = ConfigStore(d)
    assert cfg.display.brightness == 72


def test_legacy_sync_keys_without_share_url_log_migration_hint(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A pre-provider config with no migratable keys logs a hint and stays local."""
    p = tmp_path / "config.toml"
    p.write_text('[sync]\ncache_dir = "~/.cache/old"\n')
    with caplog.at_level(logging.WARNING):
        cfg = ConfigStore(p)
    assert cfg.sync.provider is ProviderName.LOCAL
    assert any("legacy [sync] keys" in m for m in caplog.messages)


def test_load_legacy_output_dir_only_points_local_provider(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A legacy config with only a custom output_dir keeps the user's photos visible.

    No OneDrive share to migrate, so the local provider is pointed at the
    legacy output_dir instead of falling back to its default directory.
    """
    p = tmp_path / "config.toml"
    p.write_text('[sync]\noutput_dir = "~/MyPhotos"\n')
    with caplog.at_level(logging.INFO):
        cfg = ConfigStore(p)
    assert cfg.sync.provider is ProviderName.LOCAL
    assert cfg.read_nested("sync", "local", "source_dir") == "~/MyPhotos"
    assert any("pointed the local provider" in m for m in caplog.messages)
    assert not any("no longer read" in m for m in caplog.messages)


def test_legacy_keys_with_provider_are_noted_not_warned(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A migrated file with leftover legacy keys gets an info note, not a warning."""
    p = tmp_path / "config.toml"
    p.write_text(
        "[sync]\n"
        'provider = "onedrive"\n'
        'share_url = "https://1drv.ms/f/old"\n'
        'output_dir = "~/Pictures/slideshow"\n'
    )
    with caplog.at_level(logging.INFO):
        cfg = ConfigStore(p)
    assert cfg.sync.provider is ProviderName.ONEDRIVE
    assert any("retained for rollback" in m for m in caplog.messages)
    assert not any("no longer read" in m for m in caplog.messages)


def test_load_migrates_legacy_onedrive_config(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A legacy OneDrive config is auto-migrated to the new layout on load.

    The old output_dir (where the photos live) becomes the provider's
    cache_dir so existing downloads are reused instead of re-downloaded.
    """
    p = tmp_path / "config.toml"
    p.write_text(
        "[sync]\n"
        'share_url = "https://1drv.ms/f/old"\n'
        'password = "pw"\n'
        'output_dir = "~/Pictures/slideshow"\n'
        'cache_dir = "~/.cache/old"\n'
    )
    with caplog.at_level(logging.INFO):
        cfg = ConfigStore(p)
    assert cfg.sync.provider is ProviderName.ONEDRIVE
    assert cfg.read_nested("sync", "onedrive", "share_url") == "https://1drv.ms/f/old"
    assert cfg.read_nested("sync", "onedrive", "password") == "pw"
    assert cfg.read_nested("sync", "onedrive", "cache_dir") == "~/Pictures/slideshow"
    assert any("migrated legacy OneDrive" in m for m in caplog.messages)


def test_flush_after_migration_preserves_legacy_keys(tmp_path: Path) -> None:
    """Flush after a migration keeps the legacy keys for rollback; re-loading re-applies it."""
    p = tmp_path / "config.toml"
    p.write_text(
        "[sync]\n"
        'share_url = "https://1drv.ms/f/old"\n'
        'password = "pw"\n'
        'output_dir = "~/Pictures/slideshow"\n'
    )
    cfg = ConfigStore(p)
    cfg.set("display", "brightness", 40)
    cfg.flush_now()
    with p.open("rb") as f:
        data = tomllib.load(f)
    # Legacy keys preserved for rollback.
    assert data["sync"]["share_url"] == "https://1drv.ms/f/old"
    assert data["sync"]["password"] == "pw"
    assert data["sync"]["output_dir"] == "~/Pictures/slideshow"
    # The flush converges the file to the new format: the file's own
    # migrated values are written (they are the file's data, not a foreign
    # secret), and the legacy keys remain for rollback.
    assert data["sync"]["provider"] == "onedrive"
    assert data["sync"]["onedrive"]["share_url"] == "https://1drv.ms/f/old"
    assert data["sync"]["onedrive"]["password"] == "pw"
    assert data["sync"]["onedrive"]["cache_dir"] == "~/Pictures/slideshow"
    # Re-loading the flushed file needs no re-migration: the provider key is
    # present and the onedrive sub-section is read directly.
    cfg2 = ConfigStore(p)
    assert cfg2.sync.provider is ProviderName.ONEDRIVE
    assert cfg2.read_nested("sync", "onedrive", "share_url") == "https://1drv.ms/f/old"


def test_load_new_format_config_not_migrated(tmp_path: Path) -> None:
    """A file that already has sync.provider is used as-is (no migration)."""
    p = tmp_path / "config.toml"
    p.write_text('[sync]\nprovider = "local"\n[sync.local]\nsource_dir = "~/MyPhotos"\n')
    cfg = ConfigStore(p)
    assert cfg.sync.provider is ProviderName.LOCAL
    assert cfg.read_nested("sync", "local", "source_dir") == "~/MyPhotos"


def test_env_override_malformed_name_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Env var names with empty path components are ignored."""
    monkeypatch.setenv("PIFRAME__DISPLAY__", "75")
    cfg = ConfigStore(tmp_path / "nonexistent.toml")
    assert cfg.display.brightness == 72


def test_env_override_dict_key_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An env var targeting a table-valued key is ignored (no scalar overwrite)."""
    monkeypatch.setenv("PIFRAME__SYNC__ONEDRIVE", "scalar")
    cfg = ConfigStore(tmp_path / "nonexistent.toml")
    assert isinstance(cfg.read_nested("sync", "onedrive"), dict)


def test_env_override_path_through_scalar_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A path whose intermediate component is a scalar value is ignored."""
    monkeypatch.setenv("PIFRAME__SLIDESHOW__INTERVAL__X", "5")
    cfg = ConfigStore(tmp_path / "nonexistent.toml")
    assert cfg.slideshow.interval == 30.0


def test_env_override_bad_float_keeps_existing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-numeric env value for a float key keeps the existing value."""
    monkeypatch.setenv("PIFRAME__SLIDESHOW__INTERVAL", "not-a-number")
    cfg = ConfigStore(tmp_path / "nonexistent.toml")
    assert cfg.slideshow.interval == 30.0


def test_flush_on_migrated_file_keeps_in_memory_provider(tmp_path: Path) -> None:
    """A flush on a migrated file must not revert the in-memory provider to the default.

    The on-disk file has no provider key (it is protected and absent); the
    in-memory value was set by the migration and reflects the running
    provider, so the disk-wins restore must not apply to it.
    """
    p = tmp_path / "config.toml"
    p.write_text(
        "[sync]\n"
        'share_url = "https://1drv.ms/f/old"\n'
        'password = "pw"\n'
        'output_dir = "~/Pictures/slideshow"\n'
    )
    cfg = ConfigStore(p)
    assert cfg.sync.provider is ProviderName.ONEDRIVE
    cfg.set("display", "brightness", 40)
    cfg.flush_now()
    # The file may hold credentials: it is written owner read/write only.
    assert oct(p.stat().st_mode & 0o777) == "0o600"
    assert cfg.sync.provider is ProviderName.ONEDRIVE
    with p.open("rb") as f:
        data = tomllib.load(f)
    # The file converges to the new format: the migrated provider value is
    # the file's own data, so it is written.
    assert data["sync"]["provider"] == "onedrive"


def test_flush_missing_file_does_not_write_env_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Env-var-injected secrets are never written, even when the config file is missing.

    A fresh device has no src/config.toml; a flush must not create it with
    env-owned credentials in it.
    """
    p = tmp_path / "config.toml"
    monkeypatch.setenv("PIFRAME__SYNC__ONEDRIVE__SHARE_URL", "https://injected")
    monkeypatch.setenv("PIFRAME__SYNC__ONEDRIVE__PASSWORD", "s3cret")
    cfg = ConfigStore(p)
    assert cfg.read_nested("sync", "onedrive", "share_url") == "https://injected"
    cfg.set("display", "brightness", 30)
    cfg.flush_now()
    with p.open("rb") as f:
        data = tomllib.load(f)
    assert "share_url" not in data["sync"]["onedrive"]
    assert "password" not in data["sync"]["onedrive"]
    assert data["display"]["brightness"] == 30
    # The in-memory value (the env value) stays for the running app.
    assert cfg.read_nested("sync", "onedrive", "share_url") == "https://injected"


def test_flush_write_failure_does_not_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A failed config write is logged, not raised; the in-memory state stays live."""

    def _raise(data: object) -> str:
        raise ValueError("cannot serialize")

    monkeypatch.setattr("piframe.config_store.tomli_w.dumps", _raise)
    p = tmp_path / "config.toml"
    cfg = ConfigStore(p)
    cfg.set("display", "brightness", 40)
    with caplog.at_level(logging.WARNING):
        cfg.flush_now()  # must not raise
    assert any("config write" in m and "failed" in m for m in caplog.messages)
    assert cfg.display.brightness == 40


def test_flush_corrupt_file_keeps_in_memory_protected_values(tmp_path: Path) -> None:
    """A config file corrupted after load keeps its in-memory protected values on flush.

    Treating an unreadable file as "all protected keys absent" would wipe
    the user's credentials; instead the in-memory (load-time) values are
    written and the read failure is logged.
    """
    p = tmp_path / "config.toml"
    p.write_text(
        '[sync]\nprovider = "onedrive"\n'
        "[sync.onedrive]\n"
        'share_url = "https://1drv.ms/f/x"\n'
        'password = "pw"\n'
    )
    cfg = ConfigStore(p)
    assert cfg.sync.provider is ProviderName.ONEDRIVE
    # The file is corrupted after the load (e.g. a hand-edit while running).
    p.write_text("this is not valid [[[ toml")
    cfg.set("display", "brightness", 50)
    cfg.flush_now()
    with p.open("rb") as f:
        data = tomllib.load(f)
    assert data["sync"]["provider"] == "onedrive"
    assert data["sync"]["onedrive"]["share_url"] == "https://1drv.ms/f/x"
    assert data["sync"]["onedrive"]["password"] == "pw"
    assert data["display"]["brightness"] == 50
