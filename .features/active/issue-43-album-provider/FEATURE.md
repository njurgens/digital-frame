# Requirements: Album Provider Abstraction

## Goal

Replace the hardcoded OneDrive sync in `SyncService` with a pluggable provider model so that multiple photo sources (OneDrive, Google Photos, local directory) can be selected at configuration time and swapped without code changes.

## Why

- `SyncService._do_sync()` imports the sync module directly: the sync logic is a concrete dependency, not an abstraction.
- `ConfigStore._SyncCfg` exposes only OneDrive-specific fields (`share_url`, `password`) with no way to select a different source.
- `SyncModule.create()` always constructs a `SyncService` wired to OneDrive: no conditional logic for alternate providers.
- `SlideshowPlayer.rescan()` scans `output_dir` via `iterdir()`: the slideshow player is coupled to a filesystem convention instead of asking the provider for its images.
- Adding any new album source requires modifying `SyncService`, `ConfigStore`, and `SyncModule` simultaneously, violating single-responsibility.

## Functional Requirements

### FR-1: Provider-Managed File Lifecycle

Each provider is the sole owner of its image files. The provider decides where files are stored, when they are downloaded, and when they are deleted. No other component writes to or scans a provider's storage. The provider protocol replaces the existing `sync(output_dir)` signature so that storage location is a provider-internal concern.

### FR-2: Provider Returns an Image Collection

The provider exposes its available images as a collection that the rest of the system can iterate and index. The collection must support both iteration (for sequential access) and indexed access (for shuffle and filtering). Each image in the collection supports lazy-loaded EXIF metadata (at minimum capture datetime and orientation) that loads on first access without blocking sync or playlist construction.

### FR-3: OneDrive Provider

A provider implementation that syncs from a OneDrive shared folder using the existing Badger token API. It maintains its own local cache, performs destructive cleanup (deletes cached files no longer present on the remote), and returns the cached images as a collection.

### FR-4: Local Provider

A provider implementation that reads images from a configurable local directory. It returns direct references to the source files — no copying, no caching, no cleanup. The user controls the source directory contents.

### FR-5: Google Photos Provider (Stub)

A placeholder provider that satisfies the provider contract. Signals not-yet-implemented on sync. Returns an empty collection and reports a not-yet-implemented status.

### FR-6: Provider Selection via Configuration

The user selects which provider to use via a `provider` field in the `[sync]` config section. Default is `"local"`. Valid values are `"onedrive"`, `"local"`, `"google"`. Unknown values produce a clear error at startup — no silent fallback. Provider-specific settings (e.g. OneDrive credentials, local source directory) live in config sub-sections scoped to that provider.

### FR-7: SyncService Delegates to Provider

`SyncService` accepts a provider instance and delegates sync work to it. It no longer imports or invoke the framesync module directly. Photo count, sync timing, and error status are derived from the provider's responses. Polling interval, trigger, and stop behaviour remain unchanged.

### FR-8: SlideshowPlayer Consumes Provider Collection

`SlideshowPlayer.rescan()` rebuilds its playlist from the provider's image collection instead of scanning `output_dir`. It applies existing shuffle and extension-filtering behaviour over the collection the provider returns.

### FR-9: Config Store Supports Provider Model

The config store is restructured to support provider selection and provider-specific settings:
- A provider selection field with a sensible default.
- Provider-specific settings (credentials, source paths) live in sub-sections scoped to each provider.
- Truly shared sync settings (polling interval) are retained. Provider-specific storage settings (cache location, output directory) are scoped to each provider.
- Provider-specific keys are read-only in the UI but overridable via environment variables.
- The config writer handles nested sub-sections without corrupting the file.

### FR-10: Environment Variable Overrides

`ConfigStore` reads `PIFRAME_`-prefixed environment variables and overlays them onto the loaded TOML config after defaults are merged. Unknown env vars are silently ignored. Environment variables can override keys that are read-only in the UI. Enables secrets injection via `.env` files or CI/CD.

### FR-11: Devcontainer Configuration

A `config.devcontainer.toml` file provides devcontainer-appropriate defaults, with secrets supplied via `.env`. An updated `.env.example` lists placeholder entries for secrets that should be supplied via environment variables.

### FR-12: Provider Initialization Failure

Initialization covers config loading and credential validation before the first sync. When the selected provider cannot be initialized (missing credentials, bad config), the error is logged and the system continues with an empty album.

### FR-13: Runtime Sync Failure

When a sync operation fails during normal operation (network unreachable, remote folder inaccessible, I/O error), the error is logged and reported via the provider's status. The slideshow continues displaying the last known image collection. Subsequent sync retries attempt recovery automatically.

## Non-Functional Requirements

### NFR-1: Clean Config

`config.toml.example` reflects the new provider-based structure. Existing config files are not migrated — users update their config on next deploy.

### NFR-1b: No Backward Compatibility

The project is in alpha. No backward-compatibility shims, migration logic, or fallback paths are needed. Existing users must update their config on next deploy.

### NFR-2: Type Safety

Static type checkers (basedpyright) report no errors in the new code.

### NFR-3: Testability

Each provider is independently unit-testable without network access. `SyncService` is testable with a mock provider. Lazy-loaded EXIF is testable with temporary files.

### NFR-4: Minimal Footprint

No new runtime dependencies are added. Only stdlib and existing project dependencies (`requests` for OneDrive, `PIL` for EXIF).

### NFR-5: Thread Safety

`SyncService` continues to use its existing locking strategy for `SyncStatus`.

### NFR-6: Lazy EXIF Performance

EXIF metadata is loaded lazily on first access to avoid blocking sync or playlist construction. EXIF loading must not delay provider sync or slideshow startup.

## Scope

### In Scope

- Provider protocol and three implementations (OneDrive, Local, Google stub).
- Image collection type with lazy-loaded EXIF metadata.
- Refactor `SyncService` to accept a provider.
- Refactor `SyncModule.create()` to resolve provider by config name.
- Refactor `SlideshowPlayer.rescan()` to consume provider collection.
- Restructure config store to support provider selection and provider-specific sub-sections.
- Config writer handles nested sub-sections without corrupting the file.
- Nested provider config keys are read-only in the UI but overridable via environment variables.
- Environment variable overlay for secrets injection.
- Create `config.devcontainer.toml` and update `.env.example`.
- Update `config.toml.example` with the new structure.
- Fix the broken import in existing `album_provider.py`.
- All existing tests pass; new tests for provider resolution, each provider, lazy EXIF, and mock-based SyncService.

### Out of Scope

- Implementing a real Google Photos sync (future issue).
- Adding UI elements for provider selection in settings (future issue).
- Supporting nested sub-directories in LocalProvider (flat scan only).
- Adding OAuth or other authentication flows beyond OneDrive Badger.
- Additional EXIF tags beyond `datetime` and `orientation` (follow-up issue).
- Migrating `PhotoCache` to `ImageOps.exif_transpose()` (follow-up issue).
- Startup validation of provider-specific config (covered by issue #51).
- Provider switching between sources (e.g., OneDrive to Local) is not addressed in this issue.

## Exit Criteria

All of the following must be true before the issue is considered complete:

1. **Provider protocol exists** and is implemented by all three providers.
2. **Three provider implementations exist**: OneDrive (fully functional with own cache and destructive cleanup), Local (directory scan, no copying/cleanup), Google Photos (stub).
3. **SyncService accepts a provider** and delegates sync/status to it. No direct framesync imports.
4. **SyncModule resolves provider by name** from `config.sync.provider`.
5. **SlideshowPlayer.rescan()** builds its playlist from the provider's image collection, not from directory scanning.
6. **Config store supports provider selection** with sensible default; flat OneDrive-specific keys removed in favor of provider-scoped sub-sections.
7. **config.toml.example updated** with provider and provider-specific sub-sections.
8. **Broken import fixed**: existing `album_provider.py` compiles and `DirectoryReader` works.
9. **`eng/test.sh` passes** with zero failures (all existing tests plus new ones).
10. **`eng/check.sh` passes** with zero lint/format/type errors.
11. **New tests added** for: provider resolution, each provider class, lazy EXIF loading, SyncService with mock provider.
12. **No new runtime dependencies** in `pyproject.toml`.
12. **Env var overrides work**: provider selection and nested provider keys can be overridden via environment variables; unknown env vars silently ignored.
13. **config.devcontainer.toml exists** with devcontainer-appropriate defaults.
14. **.env.example updated** with placeholder entries for secrets.