---
name: review-standards
description: Shared handbook for single-domain peer review of a code change. Use whenever an agent has been assigned one review domain — architecture, correctness, testing, backwards-compatibility, security, performance, code-style, or technical-communication — and must produce a structured review with a machine-parseable VERDICT line. Defines the domain scopes, the per-domain checklists, the severity scale, and the one output format all reviewers use.
---

# Review Standards

This is the shared handbook for all peer-review domains. Eight reviewers each
review the same code change from one angle. This file defines what is common to
all of them: how to review, how to rate severity, and the exact output format.
The per-domain checklists live in the sub-documents linked below.

## Pick your domain document

You were assigned exactly one domain. Read its document now, before reviewing.
Ignore the other seven.

| Domain | What it covers | Document |
| --- | --- | --- |
| `architecture` | Structure, boundaries, coupling, where code lives, whether the design fits the system | [./architecture.md](./architecture.md) |
| `correctness` | Does the code do what it is supposed to do, including edge cases and error paths | [./correctness.md](./correctness.md) |
| `testing` | Are there tests, do they test the right things, will they catch regressions | [./testing.md](./testing.md) |
| `backwards-compatibility` | Does this break existing callers, data, configs, or deployments | [./backwards-compatibility.md](./backwards-compatibility.md) |
| `security` | Can an attacker abuse this: injection, authz, secrets, unsafe input handling | [./security.md](./security.md) |
| `performance` | Time and memory cost, complexity, queries, I/O, hot paths | [./performance.md](./performance.md) |
| `code-style` | Naming, structure, idioms, consistency with the surrounding codebase | [./code-style.md](./code-style.md) |
| `technical-communication` | Docs, comments, commit messages, changelogs, error and log messages | [./technical-communication.md](./technical-communication.md) |

Each document tells you what is **out of scope** for it. Respect that. If a
problem belongs to another domain, do not report it — the reviewer for that
domain will catch it.

## How to review — same for every domain

1. Read the change summary and the task context in your prompt so you know what
   the change is *supposed* to do.
2. Open the diff file at the path given in your prompt with `read`, and read it
   top to bottom once, without judging. You have no shell — the diff is a file,
   not something you generate.
3. Open surrounding context with `read` and `grep` where the diff is not
   self-explanatory: the function being called, the class being subclassed, the
   existing test file, the caller.
4. Walk your domain checklist against the changed lines.
5. Write findings. Cite `file:line` for each one. Suggest a concrete fix in one
   or two lines. Do not paste a rewritten version of the code.
6. Record what you could not review — missing files, truncated diffs, code you
   had no context for. An honest scope note is worth more than a guess.
7. Choose the verdict using the mapping table below.

Only review files that are part of the change — the ones listed in the changed
files list you were given. If you open another file for context and notice it is
bad, that is not your business today.

You cannot run anything. There is no `bash` tool, so you cannot execute the
tests, the linter, or `git`. Do not claim a test passes or fails; review what the
code says. If a judgment truly requires running something, record that under
`NOT_REVIEWED` instead of guessing.

## Severity scale

| Severity | Meaning |
| --- | --- |
| `blocker` | Must not ship. Causes real damage: data loss, breach, outage, silent wrong results for real users. |
| `major` | Should not ship as-is. A real defect or a real design problem, but bounded and not catastrophic. |
| `minor` | Should be fixed, but the change is still shippable. Small defects, gaps, or clear improvements. |
| `nit` | Preference or polish. The author may decline it without argument. |

Each domain document sharpens these definitions for its own subject matter —
what counts as a `blocker` for `security` is not what counts as a `blocker` for
`code-style`. Read your domain's calibration section.

## Verdict — pick from the severities you found

Apply this table mechanically. Do not override it with a feeling.

| Highest severity you found | Verdict |
| --- | --- |
| any `blocker` | `BLOCK` |
| any `major`, no `blocker` | `REQUEST_CHANGES` |
| only `minor` and/or `nit` | `APPROVE_WITH_NITS` |
| no findings at all | `APPROVE` |

`BLOCK` versus `REQUEST_CHANGES`: use `BLOCK` when shipping the change would
cause harm that is expensive or impossible to undo — leaked credentials, dropped
production data, a security hole, a silently corrupted output. Use
`REQUEST_CHANGES` when the change is simply wrong or unfinished and needs another
pass. If you are unsure, use `REQUEST_CHANGES`.

One exception: if you could not review the change at all — the diff was empty,
missing, or unreadable — do not guess. Report it in the scope section and use
`REQUEST_CHANGES`.

## Required output format

Use this exact template. The orchestrator parses your final message with it, so
extra headings, missing headings, or a missing `VERDICT:` line will cause the
review to be rejected and re-run.

```
## REVIEW
DOMAIN: <the one domain you were assigned>
SUMMARY: <1-3 sentences on the state of this change in your domain>

## FINDINGS
### FINDING 1
SEVERITY: <blocker|major|minor|nit>
FILE: <path/to/file.ext:LINE>
ISSUE: <one or two sentences: what is wrong and why it matters>
FIX: <one or two sentences: a concrete change, or "none">

### FINDING 2
SEVERITY: ...
FILE: ...
ISSUE: ...
FIX: ...

## SCOPE
REVIEWED: <files or areas you actually examined>
NOT_REVIEWED: <what you could not check, and why — or "nothing">

VERDICT: <APPROVE|APPROVE_WITH_NITS|REQUEST_CHANGES|BLOCK>
```

Rules for the format:

- Number findings from 1 upward. If there are no findings, write `NONE` on the
  line under `## FINDINGS` and nothing else in that section.
- One severity per finding. Do not combine two problems into one finding.
- `FILE:` is a path plus a line number, e.g. `src/db/pool.py:214`. A range is
  fine: `src/db/pool.py:214-231`.
- Keep `ISSUE` and `FIX` to one or two sentences each. Long findings get ignored.
- `VERDICT:` is the **last line** of your final message. Write nothing after it.
