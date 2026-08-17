> **Superseded:** this task doc predates the final design; its references and details may not match the shipped code — see `DESIGN.md` and `FEATURE.md`.

# T08: Add `_apply_env_overrides()` to `ConfigStore`

## Description

Add environment variable overlay support to `ConfigStore`. `PIFRAME__` prefixed env vars override TOML values after load.

## References

- [DESIGN.md §3.8](DESIGN.md#38-srcpiframeconfig_storepy-modified) — `_apply_env_overrides()`, `_set_nested()`
- [FEATURE.md §FR-9](FEATURE.md#fr-9-environment-variable-overrides)

## Write tests

**File:** `tests/test_config_store.py` (add to existing file)

```python
def test_env_override_simple(tmp_path):
    """PIFRAME__DISPLAY__BRIGHTNESS=50 overrides display.brightness."""


def test_env_override_nested(tmp_path):
    """PIFRAME__SYNC__ONEDRIVE__SHARE_URL overrides nested sync.onedrive.share_url."""


def test_env_override_unknown_ignored(tmp_path):
    """PIFRAME__FAKE__KEY=x is silently ignored (key doesn't exist in config)."""


def test_env_override_type_coercion(tmp_path):
    """Env var values are coerced to match existing Python type (bool, int, float, str)."""


def test_env_override_protected_keys(tmp_path):
    """Protected keys can still be overridden by env vars."""
```

Run: `bash eng/test.sh --skip-diff -k "test_env_override"` — tests should fail (method doesn't exist yet).

## Implement

**Modified:** `src/piframe/config_store.py`
- Add `_ENV_PREFIX = "PIFRAME__"` class attribute
- Add `_apply_env_overrides()` method — iterates `os.environ`, strips prefix, splits on `__`, calls `_set_nested()`
- Add `_set_nested(section_path, key, value)` helper — walks `_data` along path, sets value only if key exists, coerces to existing Python type. **Returns `False` (skip) if any intermediate dict in the path is missing**, matching the "unknown env vars are silently ignored" requirement. **Does NOT check `_PROTECTED`** — protected keys can be overridden by env vars (the protection applies only to UI-driven `set()` calls).
- **Coercion rules:** If the existing value is `int`, coerce via `int(value)`. If `float`, coerce via `float(value)`. If `bool`, coerce via `value.lower() in ("true", "1", "yes")`. If `str`, use as-is. If coercion fails (e.g., `int("abc")`), skip silently.
- **Debug logging:** Log `logging.debug(f"Skipped env override: {key} (path not found)")` for skipped env vars, so typos like `PIFRAME__sync__onedreive__share_url` are visible in debug logs.
- **Note on `flush_now()`:** After env var overrides are applied, `flush_now()` writes in-memory config to disk. Env-var-driven values ARE persisted to disk. This is intentional — the user's env var values become the new "source of truth" on disk. If the env var is not set on the next restart, the persisted value is used.
- Call `_apply_env_overrides()` from `_load()` after TOML is loaded and merged with defaults

## Validate

```bash
bash eng/test.sh --skip-diff -k "test_env_override"
bash eng/test.sh --skip-diff
bash eng/check.sh
```
## Commit

```bash
bash eng/format.sh
bash eng/check.sh
git add -A
git commit -m "T08: Add `_apply_env_overrides()` to `ConfigStore`"
```
