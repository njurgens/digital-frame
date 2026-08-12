# T15: Update `.env.example` with env var override placeholders

## Description

Update `.env.example` with placeholder entries for secrets supplied via env vars.

## References

- [FEATURE.md §FR-9](FEATURE.md#fr-9-environment-variable-overrides)

## Write tests

No new tests needed. The file is validated by checking it contains expected entries.

## Implement

**Modified:** `.env.example`
- Add `PIFRAME__SYNC__PROVIDER=local` (commented)
- Add `PIFRAME__SYNC__ONEDRIVE__SHARE_URL=` (commented)
- Add `PIFRAME__SYNC__ONEDRIVE__PASSWORD=` (commented)
- Add `PIFRAME__SYNC__OUTPUT_DIR=` (commented)
- Add `PIFRAME__SYNC__CACHE_DIR=` (commented)
- Include explanatory comments about the `PIFRAME__` convention

## Validate

```bash
grep -q "PIFRAME__SYNC__PROVIDER" .env.example && echo "OK" || echo "FAIL"
grep -q "PIFRAME__SYNC__ONEDRIVE__SHARE_URL" .env.example && echo "OK" || echo "FAIL"
```
## Commit

```bash
bash eng/format.sh
bash eng/check.sh
git add -A
git commit -m "T15: Update `.env.example` with env var override placeholders"
```
