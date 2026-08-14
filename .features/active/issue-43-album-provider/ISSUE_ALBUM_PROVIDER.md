# AlbumProvider Protocol & Image/Album Types

## Problem

`SyncService._do_sync()` imports the sync module directly — the sync logic is a concrete dependency, not an abstraction. `ConfigStore._SyncCfg` exposes only OneDrive-specific fields (`share_url`, `password`) with no way to select a different source. Adding any new album source requires modifying `SyncService`, `ConfigStore`, and `SyncModule` simultaneously.

## Goal

Replace the hardcoded OneDrive sync with a pluggable `AlbumProvider` protocol and introduce `Image`/`Exif`/`Album` domain types so that multiple photo sources (OneDrive, local directory, Google Photos) can be selected at configuration time and swapped without code changes.

## Domain Types

### `Image`

```python
@dataclass(frozen=True)
class Image:
    path: Path
    _exif: Exif | None = None

    @property
    def exif(self) -> Exif | None:
        if self._exif is None:
            self._exif = Exif.load(self.path)
        return self._exif
```

- `path`: filesystem path to the image file (managed by the provider)
- `exif`: lazy-loaded on first access — the provider creates `Image(path=...)` during sync without reading any files; EXIF is read when something actually needs it (e.g., `PhotoCache` for orientation)

### `Exif`

```python
class Exif:
    def __init__(self, path: Path):
        img = Image.open(path)
        self._exif = img.getexif()
        img.close()

    @classmethod
    def load(cls, path: Path) -> "Exif | None":
        try:
            return cls(path)
        except Exception:
            return None

    @property
    def datetime_original(self) -> datetime | None: ...

    @property
    def orientation(self) -> int: ...
```

- Uses Pillow's modern `getexif()` API (replaces deprecated `_getexif()`)
- Reads the file on construction; result is cached in the `Image` instance
- Returns `None` from `load()` if the file has no EXIF or can't be read

### `Album`

```python
class Album:
    def __init__(self, images: list[Image]):
        self._images = images

    def __iter__(self) -> Iterator[Image]: ...
    def __len__(self) -> int: ...
    def __getitem__(self, index: int) -> Image: ...
```

- Iterable collection of `Image` objects
- Consumers iterate: `for img in provider.album(): path = img.path`

### Package Location

```
src/piframe/images/
  __init__.py    # re-exports Image, Exif, Album
  image.py       # Image + Exif
  album.py       # Album
```

Follows the existing `providers/` and `widgets/` convention (one file per conceptual unit, `__init__.py` re-exports).

## AlbumProvider Protocol

```python
class AlbumProvider(Protocol):
    def sync(self) -> Album: ...
    def album(self) -> Album: ...
    def status(self) -> SyncStatus: ...
    def stop(self) -> None: ...
```

- `sync()`: download/update photos into the provider's own cache directory. Return the full image collection. The provider is entirely responsible for its own file management lifecycle.
- `album()`: return the current image collection without triggering a sync. Used by `SlideshowPlayer.rescan()`.
- `status()`: return `SyncStatus` (last sync time, photo count, in-progress flag, last error).
- `stop()`: gracefully halt any in-flight sync work.

## Provider Implementations

### OneDriveProvider

- Extract existing OneDrive sync logic from `framesync/` into `OneDriveProvider`
- Uses Badger token API (token acquisition, password validation, share redemption, folder sync)
- Downloads to its own cache directory (e.g., `~/.cache/piframe/onedrive/`)
- Manages destructive cleanup of its cache (delete local files not present remotely)
- `sync()` returns `Album` with `Image` objects pointing to cached files
- `album()` returns current cache contents
- `LocalConfig` dataclass with `share_url` and `password` fields

### LocalProvider

- Scans a configurable source directory for supported image files (`.jpg`, `.jpeg`, `.png`, `.gif`)
- Returns `Image(path=source_file)` directly — no copy, no cleanup
- `sync()` returns `Album` from directory scan
- `album()` returns current directory contents
- `stop()` is a no-op
- `LocalConfig` dataclass with `source_dir` field; falls back to `config.sync.cache_dir` parent when not set

### GooglePhotosProvider (Stub)

- `sync()` raises `NotImplementedError`
- `status()` returns `SyncStatus` with `last_error` set
- `stop()` is a no-op
- `GooglePhotosConfig` dataclass (empty for now)

## Config Changes

### New `[sync]` Structure

```toml
[sync]
provider = "local"
cache_dir = "/home/frame/.cache/framesync"
interval_minutes = 60

[sync.local]
source_dir = "/home/frame/Pictures/album"

[sync.onedrive]
share_url = "..."
password = "..."
```

- `provider`: selects which provider (`"local"`, `"onedrive"`, `"google"`). Default: `"local"`. Unknown values produce a clear error at startup.
- `cache_dir`: remains for `PhotoCache` (rendered surface cache). Not used by providers.
- `output_dir`: **removed** — each provider manages its own storage
- `share_url`/`password`: **removed** from flat `[sync]` — live in `[sync.onedrive]`
- `interval_minutes`: remains unchanged

### `_SyncCfg` Changes

- Gains `provider` property (returns `ProviderName` enum)
- Loses `output_dir`, `share_url`, `password` properties
- Keeps `cache_dir` and `interval_minutes`
- Protected keys: `("sync", "cache_dir")`, `("sync", "provider")`
- Nested provider keys (`sync.onedrive.share_url`, etc.) must also be protected from UI-driven `set()` calls — `_PROTECTED` needs to support 3-tuples

### `_write_toml()` Changes

Must handle nested dicts as TOML sub-sections:

```python
# data["sync"] = {"provider": "local", "onedrive": {"share_url": "..."}}
# should produce:
# [sync]
# provider = "local"
#
# [sync.onedrive]
# share_url = "..."
```

## SyncService Changes

- Accepts `AlbumProvider` in constructor (passed from `SyncModule.create()`)
- `_do_sync()` calls `self._provider.sync()` and uses returned `Album` for `photo_count`
- No longer references `output_dir` or scans directories
- Polling interval, trigger, and stop behaviour remain unchanged

## SyncModule Changes

- `create()` reads `config.sync.provider`, constructs the appropriate provider class with its config sub-section, passes it to `SyncService`

## SlideshowPlayer Changes

- `rescan()` calls `self._provider.album()` instead of scanning `output_dir`
- Builds playlist from `Image.path` values

## Environment Variable Overrides

`ConfigStore` reads environment variables prefixed with `PIFRAME__` and overlays them onto the loaded TOML config.

- Convention: strip `PIFRAME__` prefix, split remainder on `__`. All segments except the last form the dotted section path; the last segment is the key.
  - `PIFRAME__SYNC__PROVIDER=onedrive` → `sync.provider = "onedrive"`
  - `PIFRAME__SYNC__ONEDRIVE__SHARE_URL=...` → `sync.onedrive.share_url = "..."`
- Overrides are applied **after** TOML is loaded and merged with defaults
- Unknown env vars are silently ignored
- Protected keys can still be overridden by env vars (protection applies only to UI-driven `set()` calls)

## Files to Create

- `src/piframe/images/__init__.py`
- `src/piframe/images/image.py`
- `src/piframe/images/album.py`
- `src/piframe/providers/local.py`
- `src/piframe/providers/onedrive.py`
- `src/piframe/providers/google.py`
- `config.devcontainer.toml`

## Files to Modify

- `src/piframe/providers/album_provider.py` — `AlbumProvider` protocol
- `src/piframe/providers/__init__.py` — re-export provider classes
- `src/piframe/config_store.py` — `_SyncCfg`, `_PROTECTED`, `_write_toml()`, `_apply_env_overrides()`
- `src/piframe/sync_service.py` — accept `AlbumProvider`, delegate to it
- `src/piframe/modules/sync.py` — resolve provider by name from config
- `src/piframe/slideshow_player.py` — get playlist from provider
- `config.toml.example` — new provider-based structure
- `.env.example` — placeholder entries for secrets

## Files to Remove

- `framesync/` directory and its `config.toml`

## Exit Criteria

1. `AlbumProvider` Protocol exists with `sync()`, `album()`, `status()`, `stop()` methods
2. `Image`, `Exif`, `Album` types exist in `src/piframe/images/`
3. Three provider implementations: `OneDriveProvider` (fully functional), `LocalProvider` (fully functional), `GooglePhotosProvider` (stub)
4. `SyncService` accepts `AlbumProvider` via constructor and delegates sync to it
5. `SyncModule.create()` resolves provider by name from `config.sync.provider`
6. `ConfigStore._SyncCfg` has `provider` property, no flat `share_url`/`password`/`output_dir`
7. `config.toml.example` updated with new `[sync]` structure
8. `SlideshowPlayer.rescan()` gets playlist from provider's `album()`
9. Env var overrides work: `PIFRAME__SYNC__PROVIDER=onedrive` overrides nested keys
10. `config.devcontainer.toml` exists with devcontainer-appropriate defaults
11. `.env.example` updated with placeholder entries
12. `eng/test.sh` passes with zero failures
13. `eng/check.sh` passes with zero lint/format/type errors
14. No new runtime dependencies added to `pyproject.toml`
15. OneDrive sync behaviour unchanged (identical results to current implementation)