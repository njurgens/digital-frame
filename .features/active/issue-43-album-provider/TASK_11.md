# T11: Create `config.devcontainer.toml`

## Description

Create a devcontainer-appropriate config file with local defaults.

## References

- [FEATURE.md §FR-9](FEATURE.md#fr-9-environment-variable-overrides) — `config.devcontainer.toml`
- [DESIGN.md §3.10](DESIGN.md#310-configtomlexample-updated) — config structure

## Write tests

No new tests needed. This is a config file creation task.

## Implement

**New file:** `./config.devcontainer.toml` (repo root, alongside `config.toml.example`)
- `provider = "local"`
- `output_dir` / `cache_dir` set to reasonable local paths (e.g., `/tmp/piframe-output`, `/tmp/piframe-cache`)
- `mock_wifi = true` (for devcontainer)
- All other sections with sensible defaults matching `config.toml.example`
- Include provider-specific sub-sections: `[sync.local]`, `[sync.onedrive]`

## Validate

```bash
python -c "
import tomllib
with open('config.devcontainer.toml', 'rb') as f:
    data = tomllib.load(f)
assert data['sync']['provider'] == 'local'
assert data['app']['mock_wifi'] is True
print('OK')
"
bash eng/test.sh --skip-diff
```
## Commit

```bash
bash eng/format.sh
bash eng/check.sh
git add -A
git commit -m "T11: Create `config.devcontainer.toml`"
```
