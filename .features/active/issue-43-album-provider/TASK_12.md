# T12: Update `config.toml.example` with new structure

## Description

Update `config.toml.example` to reflect the new provider-based config structure with sub-sections.

## References

- [DESIGN.md §3.10](DESIGN.md#310-configtomlexample-updated)

## Write tests

No new tests needed. This is a config file update task.

## Implement

**Modified:** `config.toml.example`
- `[sync]` with `provider = "local"`, `output_dir`, `cache_dir`, `interval_minutes`
- `[sync.onedrive]` with `share_url`, `password`
- `[sync.local]` with `source_dir`
- `[sync.google]` placeholder comment
- Remove flat `share_url` and `password` from `[sync]` section

## Validate

```bash
python -c "
import tomllib
with open('config.toml.example', 'rb') as f:
    data = tomllib.load(f)
assert data['sync']['provider'] == 'local'
assert 'onedrive' in data['sync']
assert 'local' in data['sync']
assert 'share_url' not in data['sync']  # no longer flat
print('OK')
"
bash eng/test.sh --skip-diff
```
## Commit

```bash
bash eng/format.sh
bash eng/check.sh
git add -A
git commit -m "T12: Update `config.toml.example` with new structure"
```
