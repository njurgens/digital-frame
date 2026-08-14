# DESIGN.md Assessment Against FEATURE.md

> Generated from review of `.features/active/issue-43-album-provider/FEATURE.md`
> against `.features/active/issue-43-album-provider/DESIGN.md`

---

## Critical Mismatches

### 1. FR-1: Provider-Managed File Lifecycle — `sync(output_dir)` signature is wrong

**Feature says:** "The provider protocol replaces the existing `sync(output_dir)` signature so that storage location is a provider-internal concern."

**Design has:** `sync(self, output_dir: Path) -> list[Path]` — the provider is still told where to store files via a parameter. This directly contradicts FR-1's intent that the provider decides its own storage location internally.

The protocol should not take `output_dir` as a parameter. The provider owns its cache/storage path (likely from its own config), and the rest of the system asks the provider for images, not the other way around.

### 2. FR-2: Image Collection with Lazy EXIF — entirely missing from the design

**Feature says:** The provider exposes an "image collection" supporting iteration and indexed access, with lazy-loaded EXIF metadata (capture datetime and orientation) on each image.

**Design has:** `sync() -> list[Path]` returning "newly created files." There is no `ImageCollection` type, no `Image` type with lazy EXIF, and no way for the slideshow to iterate/index images from the provider. The design has no representation of FR-2 at all.

### 3. FR-4: Local Provider — design adds copying/cleanup that the feature explicitly forbids

**Feature says:** "It returns direct references to the source files — **no copying, no caching, no cleanup.**"

**Design has:** "copy files from `source_dir` to `output_dir`... Perform destructive cleanup: delete files in `output_dir` not present in `source_dir`." This is the opposite of what FR-4 specifies. The LocalProvider should return paths to the source files directly.

### 4. FR-5: Google Photos stub — design raises instead of returning empty collection

**Feature says:** "Returns an empty collection and reports a not-yet-implemented status."

**Design has:** `sync()` raises `NotImplementedError`. Per FR-13, runtime sync failures should be logged and the slideshow should continue with the last known collection. Raising an exception from `sync()` will be caught by `SyncService._do_sync()` as an error, but the feature explicitly wants an empty collection returned, not an exception.

### 5. FR-8: SlideshowPlayer consumes provider collection — design retains old directory scanning

**Feature says:** "`SlideshowPlayer.rescan()` rebuilds its playlist from the provider's image collection instead of scanning `output_dir`."

**Design has:** Section 3.9 retains `DirectoryReader` "for the slideshow player's `rescan()` path" and Section 7 says it "is not replaced by `LocalProvider`." The design never shows `SlideshowPlayer.rescan()` consuming a provider collection. The entire point of FR-2 and FR-8 — decoupling the slideshow from filesystem conventions — is not addressed.

### 6. FR-10: Environment variable prefix — needs minor fix

**Feature says:** "`PIFRAME_`-prefixed environment variables"

**Design has:** `_ENV_PREFIX = "PIFRAME__"` (double underscore).

**Fix:** Change to `_ENV_PREFIX = "PIFRAME_"` (single underscore). The `__` separator between
nested path components is a design choice for encoding nested keys (e.g. `PIFRAME_SYNC__ONEDRIVE__SHARE_URL`).
The parsing logic (strip prefix, split remainder on `__`) is fine as-is — only the constant is wrong.

### 7. FR-12: Provider initialization failure — not addressed

**Feature says:** "When the selected provider cannot be initialized (missing credentials, bad config), the error is logged and the system continues with an empty album."

**Design has:** No coverage of initialization-time failures. `OneDriveConfig` will simply return empty strings for missing keys (via `_read_nested` defaulting to `""`), with no validation or error logging.

---

## Underspecified / Missing Areas

### 8. NFR-6: Lazy EXIF performance — not designed

**Feature says:** "EXIF metadata is loaded lazily on first access to avoid blocking sync or playlist construction."

**Design has:** No mention of lazy EXIF anywhere. No `Image` type, no caching strategy, no loading mechanism. This is a core part of FR-2.

### 9. FR-13: Runtime sync failure — not designed

**Feature says:** "The error is logged and reported via the provider's status. The slideshow continues displaying the last known image collection. Subsequent sync retries attempt recovery automatically."

**Design has:** `SyncService._do_sync()` catches exceptions generically, but there is no design for how the provider reports persistent errors via `status()`, how the slideshow retains the last known collection, or how retries work.

### 10. FR-9: Provider-specific keys read-only in UI — not addressed

**Feature says:** "Provider-specific keys are read-only in the UI but overridable via environment variables."

**Design has:** `_PROTECTED` is updated but there is no design for how the UI enforces read-only on nested provider keys. The `_PROTECTED` set uses tuple paths — the design doesn't show how nested keys like `("sync", "onedrive", "password")` are handled.

### 11. FR-11: `config.devcontainer.toml` — structure not shown

**Feature says:** "A `config.devcontainer.toml` file provides devcontainer-appropriate defaults, with secrets supplied via `.env`."

**Design has:** Lists it as "NEW" in the package layout but never shows its contents or how it differs from `config.toml.example`.

### 12. NFR-1b: "No Backward Compatibility" — design includes migration section

**Feature says:** "No backward-compatibility shims, migration logic, or fallback paths are needed."

**Design has:** Section 5 "Config Migration" discusses migration paths and user update behavior. While not implementing migration code, the section implies a concern for backward compatibility that contradicts NFR-1b's explicit dismissal of it.

---

## Summary

| Category | Count | Items |
|----------|-------|-------|
| **Direct contradictions** | 3 | FR-1 (sync signature), FR-4 (Local copying), FR-5 (Google raises vs empty) |
| **Minor fixes** | 1 | FR-10 (env prefix constant: `PIFRAME__` → `PIFRAME_`) |
| **Entirely missing** | 3 | FR-2 (ImageCollection + lazy EXIF), FR-8 (SlideshowPlayer uses provider), NFR-6 (lazy EXIF) |
| **Underspecified** | 5 | FR-9 (UI read-only), FR-11 (devcontainer config), FR-12 (init failure), FR-13 (runtime failure), NFR-1b (migration section) |

The most impactful gap is the absence of an **ImageCollection** type and **lazy EXIF** — these are central to the feature's goal of decoupling the slideshow from filesystem scanning. The design's `sync(output_dir) -> list[Path]` protocol keeps the system tightly coupled to a shared output directory, which is precisely what FR-1 and FR-8 seek to eliminate.

---

## Resolution Notes

### Resolved by data model rewrite

| # | Finding | Status |
|---|---------|--------|
| 1 | FR-1: `sync(output_dir)` signature | **RESOLVED** — `sync()` takes no args, returns `Album` |
| 2 | FR-2: ImageCollection + lazy EXIF missing | **RESOLVED** — new `piframe.images` package with `Image`, `Exif`, `Album` |
| 3 | FR-4: LocalProvider copies/cleans up | **RESOLVED** — direct references, no copy/cache/cleanup |
| 5 | FR-8: SlideshowPlayer uses directory scan | **RESOLVED** — `rescan()` consumes `provider.album()` |
| 8 | NFR-6: Lazy EXIF not designed | **RESOLVED** — `Image.exif` lazy-loads on first access |
| 12 | NFR-1b: Migration section contradicts | **RESOLVED** — migration section removed |

### Still open

| # | Finding | Status |
|---|---------|--------|
| 4 | FR-5: Google `sync()` raises instead of returning empty album | **RESOLVED** — `sync()` returns `Album([])` and sets `last_error` |
| 6 | FR-10: `_ENV_PREFIX = "PIFRAME__"` wrong | **RESOLVED** — changed to `"PIFRAME_"`, examples updated to `PIFRAME_SYNC__ONEDRIVE__SHARE_URL` |
| 7 | FR-12: Provider initialization failure not addressed | **DEFERRED to #51** — removed from FEATURE.md as out of scope |
| 9 | FR-13: Runtime sync failure | **RESOLVED** — design now explicit: provider retains cached album on error, slideshow keeps last-known playlist |
| 10 | FR-9: Provider keys read-only in UI | **STRIKEN** — UI read-only requirement removed from FEATURE.md (out of scope) |
| 11 | FR-11: `config.devcontainer.toml` not shown | **RESOLVED** — added §3.16 (devcontainer config) and §3.17 (`.env.example`) |

### New issues found in revised design

| # | Finding | Detail |
|---|---------|--------|
| A | `Image` is `frozen=True` but `exif` property mutates `_exif` | **RESOLVED** — switched to `@property @cache` pattern (no mutation needed; see [bpo-42127](https://bugs.python.org/issue42127)) |
| B | `OneDriveProvider._CACHE_DIR` is hardcoded to `~/.cache/piframe/onedrive` | **RESOLVED** — `OneDriveConfig.cache_dir` reads `[sync.onedrive].cache_dir` with `~/.cache/piframe/onedrive` default. Also fixed `LocalConfig.source_dir` default from `cache_dir` to `~/Pictures/slideshow`. |
| C | `LocalProvider` fallback to `cache_dir` is odd | **RESOLVED** — default changed to `~/Pictures/slideshow`. Added note that `Album` is a snapshot, not a live view. |
| D | `LocalProvider.album()` rescans on every call | **ACKNOWLEDGED** — documented in design: `Album` is a snapshot, not a live view. Intentional behavior. |
| E | ~~Google `sync()` raise vs return-empty~~ | **RESOLVED** alongside #4 — `sync()` now returns `Album([])` and sets `last_error`. |