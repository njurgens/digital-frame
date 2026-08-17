# Album Providers

Pi Frame gets its photos from an **album provider**: a component that owns a
source of images (a OneDrive shared folder, a local directory, …) and exposes
the current collection as an `Album`. The app never touches a provider's
storage directly — it reads the album through `album()` and lets the sync
service call `sync()` on an interval.

## Contents

**Users**

- [Available providers](#available-providers)
- [Configuration](#configuration)
- [Sync behaviour](#sync-behaviour)

**Developers**

- [The provider contract](#the-provider-contract)
- [Implementing a new provider](#implementing-a-new-provider)

## Available providers

| `sync.provider` | Class | Source | Storage behaviour |
|-----------------|-------|--------|-------------------|
| `"onedrive"` | `OneDriveProvider` | OneDrive shared folder (Badger token API — no OAuth) | Owns a private cache directory (0700 permissions). Downloads new files atomically and performs **destructive cleanup**: cached files no longer present on the remote are deleted. |
| `"local"` | `LocalProvider` | A user-managed local directory | No copying, no caching, no cleanup — the album references the source files directly. The user owns the directory contents. A missing directory yields an empty album (a warning, not an error). |
| `"google"` | `GooglePhotosProvider` | (reserved) | Stub: `sync()` returns an empty album and sets `last_error` to "Google Photos provider is not yet implemented" instead of raising, so the slideshow keeps running. |

An unknown `provider` value fails startup with a clear error — there is no
silent fallback.

## Configuration

The provider is selected in the `[sync]` section; provider-specific keys live
in per-provider sub-sections:

```toml
[sync]
provider         = "onedrive"   # "onedrive" | "local" | "google"
interval_minutes = 60

[sync.onedrive]
share_url = "https://1drv.ms/f/..."
password  = ""
cache_dir = "/home/frame/.cache/piframe/onedrive"

[sync.local]
source_dir = "/home/frame/Pictures/slideshow"

[sync.google]
# Reserved — no keys yet.
```

- **OneDrive.** `share_url` is required (a missing value fails the first
  sync with "No OneDrive share URL configured"). `password` is for
  password-protected shares. `cache_dir` is where photos are stored — it
  must not be a directory the user manages, because sync deletes cached
  files that were removed remotely.
- **Local.** `source_dir` (default `~/Pictures/slideshow`) is scanned for
  `.jpg`, `.jpeg`, `.png`, and `.gif` files.
- **Environment overrides.** Any existing config key can be overridden at
  startup with a `PIFRAME__`-prefixed variable: the remainder of the name is
  the config path, upper-cased and joined with `__` (e.g.
  `PIFRAME__SYNC__PROVIDER=local`,
  `PIFRAME__SYNC__ONEDRIVE__SHARE_URL=...`). Unknown paths are silently
  ignored. Protected keys (provider selection, OneDrive credentials) are
  never written back to the config file, so env-var-injected secrets do not
  leak into it.

## Sync behaviour

The `SyncService` runs `sync()` in a background thread every
`interval_minutes`; the slideshow rebuilds its playlist from the provider's
album after each completed sync. A failed sync keeps the last known good
album and surfaces the error in `status().last_error` (shown in the
settings panel). On shutdown, `close()` waits up to 60 s for an in-flight
sync before releasing the provider.

## The provider contract

A provider is any object that satisfies the `AlbumProvider` protocol
(`src/piframe/providers/album_provider.py`):

| Member | Type | Contract |
|--------|------|----------|
| `sync()` | `-> Album` | Refresh the local cache from the source. Runs to completion in the caller's thread. On failure, records the error in the status before raising; the last known good album is retained. |
| `album()` | `-> Album` | A defensive copy of the current album. Empty before the first successful sync; never raises. |
| `status()` | `-> SyncStatus` | A defensive copy of the sync status (`last_sync_time`, `photo_count`, `in_progress`, `last_error`). Never raises. |
| `close()` | `-> None` | Release resources. Idempotent; waits up to 60 s for an in-flight sync. No further calls after close. |
| `storage_dir` | `Path \| None` (property) | The directory holding the provider's image files (its cache, or the source directory it exposes). `None` when the provider has no local storage. |

All concrete providers subclass `BaseAlbumProvider`
(`src/piframe/providers/base.py`), which implements the whole lifecycle:
status bookkeeping under a lock, defensive copies, last-known-good album
retention, and close semantics. A concrete provider therefore only
implements:

- `_do_sync() -> Album` — the source-specific work (fetch, scan, download).
- `_release() -> None` — optional; called once from `close()`.
- the `storage_dir` property.

## Implementing a new provider

Worked example: adding a hypothetical `flickr` provider.

1. **Add the name** to the `ProviderName` enum in
   `src/piframe/providers/provider_name.py`:

   ```python
   FLICKR = "flickr"
   ```

2. **Create the module** `src/piframe/providers/flickr.py` with a config
   wrapper and a provider class:

   ```python
   """Flickr provider: exposes the images in a local Flickr export."""

   from __future__ import annotations

   from pathlib import Path
   from typing import TYPE_CHECKING

   from piframe.album import Album
   from piframe.image import IMAGE_EXTENSIONS, Image
   from piframe.providers.base import BaseAlbumProvider

   if TYPE_CHECKING:
       from piframe.config_store import ConfigStore


   class FlickrConfig:
       """Flickr provider settings, read from the ``[sync.flickr]`` section."""

       def __init__(self, config: ConfigStore) -> None:
           self._config = config

       @property
       def source_dir(self) -> Path:
           raw = self._config.read_nested(
               "sync", "flickr", "source_dir", default="~/Pictures/flickr"
           )
           return Path(str(raw)).expanduser()


   class FlickrProvider(BaseAlbumProvider):
       """Exposes the images in a user-managed Flickr export directory."""

       def __init__(self, config: FlickrConfig) -> None:
           super().__init__()
           self._config = config

       @property
       def storage_dir(self) -> Path:
           return self._config.source_dir

       def _do_sync(self) -> Album:
           source = self._config.source_dir
           if not source.is_dir():
               return Album()
           images = [
               Image(path)
               for path in sorted(source.iterdir())
               if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
           ]
           return Album.from_images(images)
   ```

   Contract notes for `_do_sync`:

   - **Raise on failure.** Do not catch and return a partial album — the
     base class records `str(exc)` in `last_error` and retains the last
     known good album. For non-fatal issues, use
     `self._note_error(message)` instead.
   - **Run to completion.** It runs in the sync thread, not the render
     loop — but the target is a 512 MB Pi 3A+, so keep memory bounded and
     stream file I/O in chunks.
   - **Own your storage.** If the provider downloads files, it owns that
     directory: create it (0700), download atomically (temp file +
     `os.replace`), and clean up files the source no longer has — or
     document that it deliberately does not. See `onedrive.py` for the
     full download-based pattern.
   - **Validate external names** before using them as path components
     (see `_is_safe_name` in `onedrive.py`).

3. **Wire it into dependency injection (DI).** Add a case to `ProviderModule.create` in
   `src/piframe/modules/provider.py`:

   ```python
   case ProviderName.FLICKR:
       return FlickrProvider(FlickrConfig(config))
   ```

   and export the new names from `src/piframe/providers/__init__.py`.

4. **Document the config.** Add a `[sync.flickr]` section to
   `config.toml.example` (and to `config.devcontainer.toml` if the
   devcontainer uses it), and the matching env-var overrides to
   `.env.example`.

5. **Test it.** Add cases to `tests/test_providers.py` following the
   existing pattern: a happy-path sync, a failure path (error recorded in
   the status, last good album retained), and `close()` behaviour.

## See also

- [Dependency injection — module pattern](dependency-injection.md) — how `ProviderModule` fits the app's DI
- [Pi Frame LLD](pi-frame-lld.md) — full design, including the config store's protected-key rules
- [DESIGN.md](../.features/active/issue-43-album-provider/DESIGN.md) — the accepted design for this feature
