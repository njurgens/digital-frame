# T03: Add `provider` property and `_read_nested()` to `ConfigStore`

## Description

Update `ConfigStore` to support the new provider-based config structure. Add nested provider defaults so env var overrides can inject credentials.

## References

- [DESIGN.md §3.8](DESIGN.md#38-srcpiframeconfig_storepy-modified)

## Write tests

**File:** `tests/test_config_store.py` (add to existing file)

```python
def test_sync_provider_default(tmp_path):
    """Default provider is LOCAL when no config file exists."""


def test_sync_provider_from_file(tmp_path):
    """provider = 'onedrive' in TOML is read as ProviderName.ONEDRIVE."""
    # Write TOML with [sync] provider = "onedrive"


def test_sync_provider_protected(tmp_path):
    """provider is in _PROTECTED set (cannot be overwritten by flush)."""
    # Write TOML with [sync] provider = "onedrive"
    # Call cfg.set("sync", "provider", "google")
    # Call cfg.flush_now()
    # Assert cfg.sync.provider is still ProviderName.ONEDRIVE


def test_read_nested_success(tmp_path):
    """_read_nested('sync', 'onedrive', 'share_url') returns correct value."""
    # Write TOML with [sync.onedrive] share_url = "..."


def test_read_nested_missing(tmp_path):
    """_read_nested() with missing keys returns the default."""


def test_sync_no_share_url_password():
    """_SyncCfg has no share_url or password attributes."""


def test_sync_nested_defaults_exist():
    """_DEFAULTS['sync'] contains nested dicts for onedrive, local, google."""
    # Verify _DEFAULTS['sync']['onedrive'] = {'share_url': '', 'password': ''}
    # Verify _DEFAULTS['sync']['local'] = {'source_dir': ''}
    # Verify _DEFAULTS['sync']['google'] = {}
```

Run: `bash eng/test.sh --skip-diff -k "test_sync_provider or test_read_nested or test_sync_no_share or test_sync_nested"` — tests should fail.

## Implement

**Modified:** `src/piframe/config_store.py`
1. Add `from piframe.providers import ProviderName` import
2. `_SyncCfg`: add `provider` property (returns `ProviderName`, validated via `from_string()`)
3. `_SyncCfg`: **retain** `share_url` and `password` properties as deprecated (they're still used by `SyncService` until T07). Mark with `@deprecated` comment or `warnings.warn()`.
4. `_DEFAULTS["sync"]`: add `provider = "local"`, add nested dicts: `onedrive = {"share_url": "", "password": ""}`, `local = {"source_dir": ""}`, `google = {}`
5. `_DEFAULTS["sync"]`: **retain** `share_url` and `password` (removed in T07)
6. `_PROTECTED`: add `("sync", "provider")`, **retain** `("sync", "share_url")` and `("sync", "password")` (removed in T07)
7. `ConfigStore`: add `_read_nested(*keys, default=...)` protected method
8. **Update existing test:** `test_protected_keys_never_overwritten` in `tests/test_config_store.py` (line 82) currently tests `share_url`/`password` protection. Rewrite it to test `provider` protection instead:
   - Write TOML with `[sync] provider = "onedrive"`
   - Call `cfg.set("sync", "provider", "google")`
   - Call `cfg.flush_now()`
   - Assert `cfg.sync.provider` is still `ProviderName.ONEDRIVE`
9. **Update `_clamp()` return type annotation** from `float | str | bool` to `float | str | bool | dict` (or `object`) to handle nested dict values from TOML sections like `[sync.onedrive]`.

## Validate

```bash
bash eng/test.sh --skip-diff -k "test_sync_provider or test_read_nested or test_sync_no_share or test_sync_nested"
bash eng/test.sh --skip-diff
bash eng/check.sh
```
## Commit

```bash
bash eng/format.sh
bash eng/check.sh
git add -A
git commit -m "T03: Add `provider` property and `_read_nested()` to `ConfigStore`"
```