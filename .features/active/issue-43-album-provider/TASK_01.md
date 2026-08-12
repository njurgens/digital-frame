# T01: Create `providers/` package with `AlbumProvider` Protocol and `ProviderName` enum

## Description

Create `src/piframe/providers/` as a new package with `__init__.py` and `album_provider.py`.

## References

- [DESIGN.md §3.1](DESIGN.md#31-srcpiframeprovidersalbum_providery) — `AlbumProvider` Protocol
- [DESIGN.md §3.9](DESIGN.md#39-srcpiframeproviders__initpy) — `ProviderName(StrEnum)` and `__init__.py`

## Write tests

**File:** `tests/test_providers.py` (new file)

```python
def test_provider_name_from_string_local():
    """from_string('local') returns ProviderName.LOCAL."""


def test_provider_name_from_string_onedrive():
    """from_string('onedrive') returns ProviderName.ONEDRIVE."""


def test_provider_name_from_string_google():
    """from_string('google') returns ProviderName.GOOGLE."""


def test_provider_name_from_string_unknown_raises():
    """from_string('unknown') raises ValueError with valid options in message."""


def test_album_provider_protocol_importable():
    """AlbumProvider is importable from piframe.providers."""
```

Run: `bash eng/test.sh --skip-diff -k "test_provider_name or test_album_provider"` — tests should fail (module doesn't exist yet).

## Implement

- **New file:** `src/piframe/providers/__init__.py` — `ProviderName` enum + `from_string()` + re-export `AlbumProvider`
- **New file:** `src/piframe/providers/album_provider.py` — `AlbumProvider` Protocol (`sync`, `status`, `stop`)

## Validate

```bash
bash eng/test.sh --skip-diff -k "test_provider_name or test_album_provider"
bash eng/test.sh --skip-diff
bash eng/check.sh
```
## Commit

```bash
bash eng/format.sh
bash eng/check.sh
git add -A
git commit -m "T01: Create `providers/` package with `AlbumProvider` Protocol and `ProviderName` enum"
```
