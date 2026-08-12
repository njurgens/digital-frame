# Requirements: Album Provider Abstraction

## Goal

Replace the hardcoded OneDrive sync in `SyncService` with a pluggable `AlbumProvider` protocol so that multiple photo sources (OneDrive, Google Photos, local directory) can be selected at configuration time and swapped without code changes.

## Why

- `SyncService._do_sync()` imports the sync module directly: the sync logic is a concrete dependency, not an abstraction.
- `ConfigStore._SyncCfg` exposes only OneDrive-specific fields (`share_url`, `password`) with no way to select a different source.
- `SyncModule.create()` always constructs a `SyncService` wired to OneDrive: no conditional logic for alternate providers.
- Adding any new album source requires modifying `SyncService`, `ConfigStore`, and `SyncModule` simultaneously, violating single-responsibility.

## Functional Requirements

### FR-1: AlbumProvider Protocol

A `Protocol` (structural type) defines the contract all providers must satisfy. It lives in `src/piframe/providers/album_provider.py` so it's discoverable by name. `SyncStatus` remains in `types.py` since it's used across the app.

The protocol exposes:

- `sync(output_dir: Path) -> list[Path]`: Download new photos into `output_dir`. Return the list of newly created files. Perform destructive cleanup (delete local files not present remotely).
- `status() -> SyncStatus`: Return the current sync status (last sync time, photo count, in-progress flag, last error).
- `stop() -> None`: Gracefully halt any in-flight sync work.

### FR-2: OneDriveProvider

Extract the existing OneDrive sync logic from a `OneDriveProvider` class that implements `AlbumProvider`.

- Lives in `src/piframe/providers/onedrive.py` with a `OneDriveConfig` dataclass.
- Uses the Badger token API (token acquisition, password validation, share redemption, folder sync) as it does today.
- Receives its configuration (`share_url`, `password`) from the config store.
- Returns `SyncStatus` populated with `last_sync_time`, `photo_count`, `in_progress`, and `last_error` fields consistent with the existing `SyncStatus` dataclass.
- The `framesync/` directory and its `config.toml` are **removed**. The provider is the sole owner of the OneDrive sync logic.

### FR-3: LocalProvider

A provider that reads images from a local directory. The existing `DirectoryAlbumProvider` in `album_provider.py` already implements directory scanning but uses a different interface (`get_album()` returning `list[Path]`).

- Lives in `src/piframe/providers/local.py` with a `LocalConfig` dataclass.
- Scans a configurable source directory for supported image files (`.jpg`, `.jpeg`, `.png`, `.gif`).
- `sync()` copies or symlinks files into `output_dir` (or scans directly if `output_dir` is the source).
- `status()` returns photo count and last sync time.
- `stop()` is a no-op (no background work to cancel).

### FR-4: GooglePhotosProvider (Stub)

A placeholder provider for Google Photos that satisfies the `AlbumProvider` protocol.

- Lives in `src/piframe/providers/google.py` with a `GooglePhotosConfig` dataclass.
- `sync()` raises `NotImplementedError` with a descriptive message.
- `status()` returns a `SyncStatus` with `last_error` set to indicate the provider is not yet implemented.
- `stop()` is a no-op.

### FR-5: Provider Selection via Config

The `[sync]` section of `config.toml` gains a `provider` field that selects which provider to use.

- Default value is `"local"`.
- Valid values: `"onedrive"`, `"local"`, `"google"`.
- Unknown values produce a clear error at startup (not a silent fallback).
- Provider-specific config lives in sub-sections: `[sync.onedrive]`, `[sync.local]`, `[sync.google]`.

### FR-6: SyncModule Refactor

`SyncModule.create()` reads `config.sync.provider` and constructs the appropriate provider class, then passes it to `SyncService`.

- `SyncService` accepts an `AlbumProvider` in its constructor instead of importing the sync module directly.
- `SyncService._do_sync()` delegates to `self._provider.sync(output_dir)` and updates status from `self._provider.status()`.
- The polling interval, trigger, and stop behaviour remain unchanged.

### FR-7: ConfigStore Changes

`ConfigStore._SyncCfg` gains a `provider` property. The vestigial flat keys
(`share_url`, `password`) are **removed**: provider-specific config lives
only in sub-sections (`[sync.onedrive]`, `[sync.local]`, `[sync.google]`).

- `output_dir`, `cache_dir`, `interval_minutes` remain on `_SyncCfg` as
  existing properties.
- Protected keys are `output_dir`, `cache_dir`, `provider`.
- Default config includes `provider = "local"`.

### FR-8: Providers Package

A `src/piframe/providers/` package is created with:

- `__init__.py`: re-exports `AlbumProvider` from `album_provider.py` and lists available provider classes.
- `onedrive.py`: `OneDriveConfig` + `OneDriveProvider`.
- `local.py`: `LocalConfig` + `LocalProvider`.
- `google.py`: `GooglePhotosConfig` + `GooglePhotosProvider` (stub).

Each file is a single conceptual unit (config dataclass + provider class), following the existing `widgets/` convention.

### FR-9: Environment Variable Overrides

`ConfigStore` reads environment variables prefixed with `PIFRAME__` and overlays them onto the loaded TOML config. This enables secrets and environment-specific values to be injected via `.env` files or CI/CD pipelines without touching the TOML file.

- Convention: strip the `PIFRAME__` prefix, split the remainder on `__`. All segments except the last form the dotted section path; the last segment is the key. E.g. `PIFRAME__SYNC__ONEDRIVE__SHARE_URL` maps to `sync.onedrive.share_url`. `PIFRAME__DISPLAY__BRIGHTNESS` maps to `display.brightness`.
- Overrides are applied **after** TOML is loaded and merged with defaults, so env vars always win.
- Only keys that already exist in the merged config (TOML + defaults) are overridden: unknown env vars are silently ignored.
- Protected keys can still be overridden by env vars (the protection applies only to UI-driven `set()` calls).
- `config.devcontainer.toml` is a TOML config for local devcontainer use, with env vars supplying secrets via `.env`.

## Non-Functional Requirements

### NFR-1: Clean Config

`config.toml.example` reflects the new provider-based structure. Existing config files are not migrated: users update their config on next deploy.

### NFR-1b: No Backward Compatibility

The project is in alpha. No backward-compatibility shims, migration logic, or
fallback paths are needed. Existing `config.toml` files are left as-is; users
update them on next deploy.

### NFR-2: No Behaviour Change for OneDrive Users

The OneDrive sync flow (token acquisition, password validation, share redemption, folder sync, destructive cleanup) produces identical results to the current implementation.

### NFR-3: Type Safety

All provider code uses the `AlbumProvider` Protocol for type hints. Static type checkers (basedpyright) report no errors in the providers package.

### NFR-4: Testability

Each provider is independently unit-testable without network access. `SyncService` is testable with a mock `AlbumProvider`.

### NFR-5: Minimal Footprint

No new runtime dependencies are added. The providers package uses only stdlib and existing project dependencies (`requests` for OneDrive).

### NFR-6: Thread Safety

`SyncService` continues to use its existing locking strategy for `SyncStatus`. Provider implementations that perform I/O must not hold the status lock during network calls.

## Scope

### In Scope

- Create `AlbumProvider` Protocol in `src/piframe/providers/album_provider.py`.
- Create `src/piframe/providers/` package with `__init__.py`, `onedrive.py`, `local.py`, `google.py`.
- Extract OneDrive sync logic from `OneDriveProvider`.
- Implement `LocalProvider` with directory scanning.
- Add stub `GooglePhotosProvider`.
- Refactor `SyncService` to accept `AlbumProvider` in constructor.
- Refactor `SyncModule.create()` to resolve provider by name from config.
- Add `provider` field to `ConfigStore._SyncCfg` and `_DEFAULTS`.
- Update `config.toml.example` with the new config structure.
- Fix the broken `AlbumProvider` import in existing `album_provider.py`.
- All existing tests pass.
- New unit tests for provider resolution and each provider class.
- Add `_apply_env_overrides()` to `ConfigStore` that overlays `PIFRAME_*` env vars onto the loaded config.
- Create `config.devcontainer.toml` with devcontainer-appropriate defaults.
- Update `.env.example` with placeholder entries for secrets supplied via env vars.

### Out of Scope

- Implementing a real Google Photos sync (that is a future issue).
- Adding new UI elements for provider selection in the settings panel (that is a future issue).
- Supporting nested sub-directories in `LocalProvider` (flat directory scan only, matching existing behaviour).
- Adding OAuth or other authentication flows beyond what OneDrive Badger already uses.

## Exit Criteria

All of the following must be true before the issue is considered complete:

1. **AlbumProvider Protocol exists** in `src/piframe/providers/album_provider.py` with `sync()`, `status()`, and `stop()` methods.
2. **Three provider implementations exist**: `OneDriveProvider` (fully functional), `LocalProvider` (fully functional), `GooglePhotosProvider` (stub with `NotImplementedError`).
3. **SyncService accepts AlbumProvider** via constructor and delegates sync to it.
4. **SyncModule resolves provider by name** from `config.sync.provider` and passes the correct instance to `SyncService`.
5. **ConfigStore supports provider field** with default `"local"`.
6. **config.toml.example updated** with the new `[sync]` structure including `provider` and provider-specific sub-sections.
7. **Broken import fixed**: `album_provider.py` compiles and `DirectoryAlbumProvider` works correctly.
8. **`eng/test.sh` passes** with zero failures (all existing tests plus new ones).
9. **`eng/check.sh` passes** with zero lint/format/type errors (pre-existing issues included).
10. **New tests added** for: provider resolution in `SyncModule`, `OneDriveProvider` sync flow (mocked HTTP), `LocalProvider` directory scanning, `GooglePhotosProvider` stub behaviour, and `SyncService` with mock provider.
11. **No new runtime dependencies** added to `pyproject.toml`.
12. **OneDrive sync behaviour unchanged**: provider produces identical results to the current implementation.
13. **Env var overrides work**: `PIFRAME__SYNC__PROVIDER=onedrive` overrides `config.sync.provider`; `PIFRAME__SYNC__ONEDRIVE__SHARE_URL` overrides nested key. Unknown env vars are silently ignored.
14. **config.devcontainer.toml exists** with devcontainer-appropriate defaults.
15. **.env.example updated** with placeholder entries for secrets.