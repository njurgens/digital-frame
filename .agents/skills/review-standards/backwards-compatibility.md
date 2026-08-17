---
name: backwards-compatibility
description: 'Review checklist for the backwards-compatibility domain of a peer review. Read this when assigned the "backwards-compatibility" domain: public API and signature changes, changed defaults, wire and serialization formats, migrations, config keys, rollout and rollback safety, and deprecation hygiene. Includes domain-specific severity calibration and worked findings.'
---

# Domain: backwards-compatibility

You are reviewing **what this change breaks for things that already exist**:
existing callers, existing stored data, existing configs, existing deployments,
and the version of the code that is still running during a rollout.

## In scope

- Public API surface: functions, methods, classes, and constants that are
  exported or documented. Removed, renamed, or moved symbols.
- Signature changes: a parameter added without a default, a parameter removed or
  renamed, positional order changed, a keyword made required, return type or
  shape changed, a value that used to be nullable now guaranteed (or vice versa).
- Behavior changes under an unchanged signature: a changed default value, a
  different exception type raised, an operation that used to be a no-op now
  having an effect, changed sort order or iteration order that callers relied on.
- HTTP/RPC contracts: removed or renamed fields, changed status codes, changed
  error body shape, stricter validation on an existing endpoint, changed
  pagination or defaults.
- Serialization and persisted formats: JSON/protobuf/pickle field changes, enum
  values added or removed, on-disk or cache formats that old readers must parse.
- Database migrations: dropping or renaming a column, adding a `NOT NULL` column
  without a default, a migration that is not safe to run while the old code is
  still serving traffic, a migration with no reverse.
- Configuration: renamed or removed config keys, environment variables, CLI
  flags, changed defaults, config that is now required.
- Rollout safety: can old and new versions run at the same time? Can you roll
  back after this ships, or does the migration/data write make rollback lossy?
- Dependency and platform requirements: raised minimum language/runtime version,
  a new required system package, a dependency bumped across its own major
  version.
- Deprecation hygiene: is a removal happening without a prior deprecation period,
  a warning, or a note in the changelog?
- Semantic versioning: does the change require a major bump that is not being
  taken?

## Out of scope

- Whether the new behavior itself is right — that is `correctness`.
- Whether the new interface is well-designed or in the right module — that is
  `architecture`. Your question is only "does the old thing still work?"
- Whether the changelog wording is clear — that is `technical-communication`.
  Whether a change *needs* a changelog entry to warn users is yours to flag.

## Checklist

1. For every removed or renamed symbol in the diff, `grep` the repo for
   remaining references — then ask whether external users could also reference it.
2. For every changed function signature, check whether new parameters have
   defaults and whether existing call sites were all updated.
3. For every changed default value, ask what an existing caller who passed
   nothing now gets.
4. For every changed return value, check whether callers destructure, index, or
   type-check it.
5. For every changed exception/error type, `grep` for handlers catching the old
   type.
6. For every API response change, check whether a field was removed or renamed
   rather than added. Additions are usually safe; removals are not.
7. For every new validation rule on an existing input, ask whether previously
   accepted requests are now rejected.
8. For every migration: is it additive? Is there a down-migration? Is there a
   window where old code reads a column the migration dropped?
9. For every config key touched: is the old name still accepted? Is there a
   fallback and a warning?
10. Check for enum values removed, or new enum values that old consumers will
    receive and not recognize.
11. Check whether persisted data written by the old version still deserializes
    under the new code, and vice versa.
12. Check the version file / changelog: does the version bump match the size of
    the break?

## Severity calibration for backwards-compatibility

- `blocker` — Existing persisted data becomes unreadable or is destructively
  migrated with no rollback; a deployed old version will crash against the new
  schema or new payload during rollout; a documented public API is removed with
  no deprecation in a non-major release.
- `major` — A public signature, config key, CLI flag, or response field changes
  in a way that breaks known callers without a compatibility shim or warning; a
  changed default silently alters behavior for existing users.
- `minor` — A break confined to internal callers that were all updated but with
  no deprecation alias for out-of-tree consumers; a raised minimum dependency
  version not mentioned anywhere; missing deprecation warning on a symbol that
  still works.
- `nit` — A rename that is compatible today but will be confusing later; a
  deprecation notice missing a target removal version.

## Worked examples

**Example 1**

```
### FINDING 1
SEVERITY: blocker
FILE: migrations/0042_drop_legacy_email.py:12
ISSUE: The migration drops `users.legacy_email` in the same release that stops writing it, so during a rolling deploy the still-running old version selects that column and every request errors until the rollout finishes.
FIX: Split into two releases — stop reading/writing the column now, drop it in the following release once no old instances remain.
```

**Example 2**

```
### FINDING 2
SEVERITY: major
FILE: src/client/config.py:29
ISSUE: `timeout` changes its default from 30 to 5 seconds, so existing callers that never passed a timeout will start failing on slow requests with no code change on their side.
FIX: Keep the default at 30, document 5 as the recommended value, and note the intended change in the changelog for the next major release.
```

## Output

Use the format defined in [./SKILL.md](./SKILL.md) under "Required output
format". Do not invent your own.
