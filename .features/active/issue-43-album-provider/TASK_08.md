# T08: Refactor `SyncModule.create()` to resolve provider by name

## Description

Update `SyncModule.create()` to read `config.sync.provider` and instantiate the correct provider.

## References

- [DESIGN.md §3.7](DESIGN.md#37-srcpiframe-modulessyncpy-modified)

## Write tests

**File:** `tests/test_modules.py` (add to existing file)

```python
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

Run: `bash eng/test.sh --skip-diff -k "test_sync_module_resolves or test_sync_module_rejects or test_sync_module_defaults"` — tests should fail.

## Implement

**Modified:** `src/piframe/modules/sync.py`
- Import provider classes and `ProviderName` from `piframe.providers`
- Add `_resolve_provider(name: ProviderName, config: ConfigStore)` helper that matches on enum
- `create()` reads `config.sync.provider`, resolves provider, passes to `SyncService`

## Validate

```bash
bash eng/test.sh --skip-diff -k "test_sync_module_resolves or test_sync_module_rejects or test_sync_module_defaults"
bash eng/test.sh --skip-diff
bash eng/check.sh
```
## Commit

```bash
bash eng/format.sh
bash eng/check.sh
git add -A
git commit -m "T08: Refactor `SyncModule.create()` to resolve provider by name"
```
