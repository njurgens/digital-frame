# T07: Refactor `SyncService` and `SyncModule` for `AlbumProvider`

## Description

Refactor `SyncService` to accept an `AlbumProvider` in its constructor and update `SyncModule.create()` to resolve the provider by name. **Both changes must land in the same commit** to avoid a broken intermediate state.

## References

- [DESIGN.md §3.6](DESIGN.md#36-srcpiframesync_servicepy-modified) — `SyncService` constructor change
- [DESIGN.md §3.7](DESIGN.md#37-srcpiframesync_servicepy-modified) — `SyncModule` provider resolution

## Write tests

**File:** `tests/test_modules.py` (add to existing file)

```python
def test_sync_service_delegates_to_provider(mocker):
    """SyncService._do_sync() calls provider.sync() with correct output_dir."""

def test_sync_service_posts_event_on_success(mocker):
    """EVT_SYNC_COMPLETE is posted after successful sync."""

def test_sync_service_catches_provider_error(mocker):
    """Exception from provider is caught, last_error is set."""

def test_sync_service_stop_calls_provider_stop(mocker):
    """stop() calls provider.stop()."""

def test_sync_module_resolves_onedrive(tmp_path):
    """config with provider='onedrive' produces OneDriveProvider instance."""

def test_sync_module_resolves_local(tmp_path):
    """config with provider='local' produces LocalProvider instance."""

def test_sync_module_resolves_google(tmp_path):
    """config with provider='google' produces GooglePhotosProvider instance."""

def test_sync_module_rejects_unknown(tmp_path):
    """config with provider='unknown' raises ValueError."""

def test_sync_module_defaults_to_local(tmp_path):
    """No provider field defaults to LocalProvider."""
```

Run: `bash eng/test.sh --skip-diff -k "test_sync_service_ or test_sync_module_"` — tests should fail (constructor/resolution not yet updated).

## Implement

**Modified:** `src/piframe/sync_service.py`
- Constructor takes `provider: AlbumProvider, config: ConfigStore` (two args instead of one)
- `_do_sync()` calls `self._provider.sync(output_dir)` and `self._provider.status()`
- `stop()` calls `self._provider.stop()`
- Remove all `framesync` imports and `sys.path` manipulation
- Remove `share_url`/`password` checks (provider handles that)
- Update docstrings: replace "framesync" with "provider" references

**Modified:** `src/piframe/modules/sync.py`
- Import provider classes and `ProviderName` from `piframe.providers`
- Add `_resolve_provider(name: ProviderName, config: ConfigStore)` helper that matches on enum
- `create()` reads `config.sync.provider`, resolves provider, passes to `SyncService`
- Update docstrings: replace "framesync" with "provider" references

## Validate

```bash
bash eng/test.sh --skip-diff -k "test_sync_service_ or test_sync_module_"
bash eng/test.sh --skip-diff
bash eng/check.sh
```

## Commit

```bash
bash eng/format.sh
bash eng/check.sh
git add -A
git commit -m "T07: refactor SyncService and SyncModule for AlbumProvider"
```