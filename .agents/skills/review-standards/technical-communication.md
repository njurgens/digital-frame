---
name: technical-communication
description: 'Review checklist for the technical-communication domain of a peer review. Read this when assigned the "technical-communication" domain: docstrings, stale documentation, comment accuracy, commit messages, changelog entries, error messages, log messages, and user-facing strings. Includes domain-specific severity calibration and worked findings.'
---

# Domain: technical-communication

You are reviewing **everything the change says in words**: documentation,
comments, commit messages, changelog entries, error messages, log messages, and
user-facing strings. You review whether a human reading them later gets accurate,
sufficient, actionable information.

## In scope

- **Docstrings and API docs** for new or changed public functions: present?
  accurate? do they describe parameters, return value, raised errors, and units?
  Did a signature change without the docstring changing with it?
- **Stale documentation**: a doc, README, comment, or example that the change
  makes wrong. This is the highest-value thing you look for — wrong docs are
  worse than no docs.
- **Comments**: do they explain *why* (the constraint, the tradeoff, the bug
  being worked around) rather than restating the code? Is the non-obvious code
  commented at all? Are there comments that contradict the code?
- **Commit message / PR description**: does the subject line say what changed in
  the imperative mood and under ~72 characters? Does the body say *why*? Does it
  follow whatever convention the repo uses? Does it reference the issue or
  ticket? The commit messages are supplied to you as a file — read it; you
  cannot run `git log`.
- **Changelog / release notes**: does a user-visible change have an entry? Is it
  written for the user ("Fixed timestamps being off by one hour in daily
  exports") rather than for the developer ("refactor tz handling in exporter")?
  Are breaking changes and migration steps called out?
- **Error messages**: do they say what went wrong, what input caused it, and what
  the user can do? Do they avoid leaking internals or blaming the user? Are they
  distinguishable from each other when they appear in a support ticket?
- **Log messages**: right level (`debug`/`info`/`warning`/`error`)? Enough
  context (IDs, counts) to be actionable? Not a bare string like `"failed"`?
  Structured fields where the project uses structured logging?
- **User-facing strings**: UI copy, CLI help text, prompts. Clear, consistent
  terminology, correct spelling and grammar.
- **Deprecation notices**: do they say what to use instead and by when?
- **Examples and snippets** in docs: do they actually run against the new code?
- **Terminology consistency**: does the change call the same concept by two
  different names across code, docs, and messages?
- **README / setup instructions**: does the change add a step (a new env var, a
  new service, a new migration) that setup docs do not mention?

## Out of scope

- Identifier naming in the code — that is `code-style`. Naming in *prose and
  messages* is yours; naming of variables and functions is theirs.
- Whether the documented behavior is the right behavior — that is `correctness`
  or `architecture`. Your question is whether the words match the code.
- Whether a breaking change is acceptable — that is `backwards-compatibility`.
  Whether it is *announced* is yours.

## Checklist

1. For every changed public function, diff the docstring against the new
   signature: parameters added/removed/renamed, return type, raised exceptions.
2. `grep` the docs/ directory and README for the names of anything renamed,
   removed, or changed in this diff. Any hit is a stale-doc finding.
3. Read every comment in the diff. Flag ones that restate the code, ones that are
   now false, and non-obvious code with no comment.
4. Open the commits file whose path is given in your prompt and read the commit
   messages for this change. Check subject mood and length, presence of a "why",
   and whether they match the convention used by the other commits in that file.
5. Check whether the repo has a `CHANGELOG.md`. If it does and this change is
   user-visible, check for an entry.
6. Read every new `raise`, `throw`, or error string. Ask: if this appeared in a
   support ticket with no other context, would someone know what to do?
7. Read every new log line. Check the level and whether it carries identifiers.
8. Check for `TODO`/`FIXME` prose that is unintelligible or has no owner.
9. Spell-check new prose (docs, comments, messages) — especially in user-facing
   strings.
10. Check that any new configuration option is documented somewhere a user would
    look.
11. Check that code examples in docs match the new API surface.
12. Check terminology: pick the main new noun in the change and see whether it is
    called the same thing everywhere.

## Severity calibration for technical-communication

- `blocker` — Documentation or a message that will actively cause harm: setup or
  migration instructions that are now wrong in a destructive way, a security- or
  data-related warning removed, a breaking change shipped with documentation
  that still describes the old behavior as current.
- `major` — Public API documented incorrectly after a signature change; a
  user-visible breaking change with no changelog entry; an error message for a
  common failure that gives the user nothing to act on; a comment that
  contradicts the code it sits above.
- `minor` — Missing docstring on a new public function; a `debug`-level message
  that should be `warning`; a changelog entry written in developer jargon; a log
  line with no identifiers; commit body missing the "why".
- `nit` — Typos, grammar, wording that could be crisper, a comment that could be
  shorter, inconsistent capitalization in messages.

## Worked examples

**Example 1**

```
### FINDING 1
SEVERITY: major
FILE: src/export/scheduler.py:47
ISSUE: The docstring still documents `interval` as minutes, but the change switched the parameter to seconds at line 52, so anyone following the docs will schedule exports sixty times too often.
FIX: Update the docstring to say seconds and rename the parameter to `interval_seconds` so the unit is visible at call sites.
```

**Example 2**

```
### FINDING 2
SEVERITY: minor
FILE: src/upload/validate.py:88
ISSUE: The new error raises `ValueError("invalid file")`, which does not say which file, which rule it failed, or what an acceptable file looks like, so a user hitting it has nothing to act on.
FIX: Include the filename and the failed constraint, e.g. `f"{name}: expected a CSV under 50 MB, got {size_mb:.1f} MB"`.
```

## Output

Use the format defined in [./SKILL.md](./SKILL.md) under "Required output
format". Do not invent your own.
