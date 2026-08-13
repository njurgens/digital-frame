# T03: Add `provider` property and `read_nested()` to `ConfigStore`

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
    """read_nested('sync', 'onedrive', 'share_url') returns correct value."""
    # Write TOML with [sync.onedrive] share_url = "https://example.com"
    # Assert cfg.read_nested("sync", "onedrive", "share_url") == "https://example.com"


def test_read_nested_missing_intermediate(tmp_path):
    """read_nested() with missing intermediate key returns the default."""
    # Assert cfg.read_nested("sync", "nonexistent", "key", default="fallback") == "fallback"


def test_read_nested_missing_leaf(tmp_path):
    """read_nested() with missing leaf key returns the default."""
    # Assert cfg.read_nested("sync", "onedrive", "nonexistent", default="x") == "x"


def test_sync_no_share_url_password():
    """_SyncCfg has no share_url or password attributes (deprecated, removed in T07)."""


def test_sync_nested_defaults_exist():
    """_DEFAULTS['sync'] contains nested dicts for onedrive, local, google."""
    # Verify _DEFAULTS['sync']['onedrive'] = {'share_url': '', 'password': ''}
    # Verify _DEFAULTS['sync']['local'] = {'source_dir': ''}
    # Verify _DEFAULTS['sync']['google'] = {}


def test_clamp_dict_passthrough():
    """_clamp() passes dict values through unchanged."""
    # Verify _clamp("sync", "onedrive", {"share_url": "x"}) returns the dict
```

Run: `bash eng/test.sh --skip-diff -k "test_sync_provider or test_read_nested or test_sync_no_share or test_sync_nested or test_clamp_dict"` — tests should fail.

## Implement

**Modified:** `src/piframe/config_store.py`
1. Add lazy import of `ProviderName` inside the `provider` property body (not at module level) to avoid circular import with `providers/__init__.py`. Use string annotation `"ProviderName"` on the return type.
2. `_SyncCfg`: add `provider` property (returns `ProviderName`, validated via `from_string()`). **Add edge case tests for `from_string()`**: case sensitivity (`"Onedrive"` vs `"onedrive"`), whitespace (`" onedrive "`), empty string, invalid value (`"dropbox"`).
3. `_SyncCfg`: **retain** `share_url` and `password` properties as deprecated (still used by `SyncService` until T07). Mark with `@deprecated` comment or `warnings.warn()`.
4. `_DEFAULTS["sync"]`: add `provider = "local"`, add nested dicts: `onedrive = {"share_url": "", "password": ""}`, `local = {"source_dir": ""}`, `google = {}`
5. `_DEFAULTS["sync"]`: **retain** `share_url` and `password` (removed in T07)
6. `_PROTECTED`: add `("sync", "provider")`, **retain** `("sync", "share_url")` and `("sync", "password")` (removed in T07)
7. `ConfigStore`: add `read_nested(*keys, default=...)` **public** method (not `_read_nested()`). The provider Config classes need to call this from outside `ConfigStore`.
8. **Update existing test:** `test_protected_keys_never_overwritten` (line 82) currently tests `share_url`/`password` protection. Rewrite it to test `provider` protection:
   - Write TOML with `[sync] provider = "onedrive"`
   - Call `cfg.set("sync", "provider", "google")`
   - Call `cfg.flush_now()`
   - Assert `cfg.sync.provider` is still `ProviderName.ONEDRIVE`
9. **Update `_clamp()` return type annotation** from `float | str | bool` to `float | str | bool | dict` (or `object`) to handle nested dict values from TOML sections like `[sync.onedrive]`. Dicts pass through `_clamp()` unchanged (the `isinstance(value, (int, float))` check returns `False` for dicts, so they are returned as-is).

## Validate

```bash
bash eng/test.sh --skip-diff -k "test_sync_provider or test_read_nested or test_sync_no_share or test_sync_nested or test_clamp_dict"
bash eng/test.sh --skip-diff
bash eng/check.sh
```
## Commit

```bash
bash eng/format.sh
bash eng/check.sh
git add -A
git commit -m "T03: Add `provider` property and `read_nested()` to `ConfigStore`"
```