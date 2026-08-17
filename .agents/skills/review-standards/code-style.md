---
name: code-style
description: 'Review checklist for the code-style domain of a peer review. Read this when assigned the "code-style" domain: naming, consistency with the surrounding codebase, linter compliance, function shape and nesting, magic values, dead code, typing hygiene, and language idioms. Includes code-style-specific severity calibration and worked findings.'
---

# Domain: code-style

You are reviewing **how the code reads**: naming, shape, idioms, and whether it
looks like it belongs in this codebase.

## In scope

- Naming: variables, functions, classes, files, and constants that are vague
  (`data`, `temp`, `handle`, `do_stuff`, `flag2`), misleading (a name that says
  the opposite of what it does), inconsistent with the surrounding code, or
  abbreviated past recognition.
- Consistency with the existing codebase: does this file follow the conventions
  of its neighbours — same import style, same error-handling pattern, same
  logging call, same naming case, same test layout? A locally consistent style
  beats a globally "correct" one.
- Linter and formatter compliance: obvious violations of the project's configured
  tools (`ruff`, `eslint`, `gofmt`, `black`, `.editorconfig`). Check what the
  project actually configures before flagging.
- Function and file shape: functions doing too many things, deeply nested
  conditionals that could use early returns, a 300-line function, a file that
  has grown a second unrelated concern.
- Magic values: unexplained numeric or string literals that should be named
  constants or enum members.
- Dead weight: commented-out code, unused imports, unused variables and
  parameters, unreachable helpers, debug prints, leftover scaffolding.
- Duplication at the line level: the same three lines repeated in four branches.
- Type annotations / typing hygiene where the project uses them: missing
  annotations on new public functions, `Any` used to silence a checker, a
  `# type: ignore` or `@ts-ignore` with no explanation.
- Language idioms: not using the obvious built-in (`enumerate`, `zip`, `with`,
  context managers, destructuring, `??`), manual index loops where iteration
  works, string building where a formatter exists.
- Structural clarity: boolean parameters that make call sites unreadable, long
  positional argument lists, mutable state passed around implicitly.
- Import hygiene: wildcard imports, imports inside functions without reason,
  circular-import workarounds, import ordering where the project enforces it.
- `TODO`/`FIXME`/`XXX` markers added without an owner or issue reference.

## Out of scope

- The *content* of comments, docstrings, commit messages, changelogs, and error
  message wording — that is `technical-communication`. You may flag that a
  gnarly block has no comment at all; leave the prose quality to them.
- Module boundaries, layering, dependency direction, and where a class should
  live — that is `architecture`. Your scope is within-file readability.
- Whether the logic is right — that is `correctness`.
- Whether it is fast — that is `performance`.

## Checklist

1. Read each new name out loud. Does it say what the thing is?
2. Compare the changed file to its neighbours: same import order, same quote
   style, same logger, same error pattern, same test naming?
3. Check the project's linter config (`pyproject.toml`, `.eslintrc`,
   `setup.cfg`, `.golangci.yml`). Only flag rules the project actually enables.
4. Count nesting depth. Three levels of `if` inside a loop usually wants an early
   return or a helper.
5. Find every bare literal that is not `0`, `1`, or `""`. Should it be named?
6. `grep` the diff for `print(`, `console.log`, `debugger`, `pdb.set_trace`,
   `fmt.Println` left in production code.
7. Look for commented-out blocks and unused imports/variables.
8. Look for a boolean argument at a call site: `render(user, True)` — what is
   `True`?
9. Check that new public functions have the type annotations the project uses
   elsewhere.
10. Look for copy-paste: the same block with one word changed, two or more times.
11. Check line length and formatting only if the project enforces it
    automatically; otherwise skip.
12. Check that new files carry whatever header, license, or `__all__` convention
    the sibling files carry.

Do not relitigate settled formatting the project's formatter already owns. If
`black` or `prettier` runs in CI, formatting is not a finding.

## Severity calibration for code-style

Style findings are rarely severe. Be honest about that — inflating them makes
the aggregate verdict useless.

- `blocker` — Essentially never. Reserve it for code that is genuinely
  unmaintainable as written: a function so tangled that no one can safely change
  it, or debug/scaffolding code that would run in production.
- `major` — A name that actively misleads (`is_valid` returns the error count);
  a large copy-pasted block that will drift; nesting or length that makes the
  logic unreviewable; a lint rule the project enforces in CI being violated.
- `minor` — Vague names, magic numbers, unused imports, missing annotations,
  non-idiomatic constructs, commented-out code, moderate duplication.
- `nit` — Preferences: ordering, a slightly better name, a comprehension over a
  loop, splitting a medium-sized function.

## Worked examples

**Example 1**

```
### FINDING 1
SEVERITY: major
FILE: src/auth/session.py:112
ISSUE: `check_expired()` returns `True` when the session is still valid, which is the opposite of what the name implies, and the call site at `middleware.py:44` reads as if it is checking for expiry.
FIX: Rename to `is_active()`, or invert the return value and keep the name.
```

**Example 2**

```
### FINDING 2
SEVERITY: minor
FILE: src/jobs/scheduler.py:38
ISSUE: The retry window is the bare literal `900` in three places, so a reader has to guess the unit and a change has to be made three times.
FIX: Define `RETRY_WINDOW_SECONDS = 900` at module level and use it at all three sites.
```

## Output

Use the format defined in [./SKILL.md](./SKILL.md) under "Required output
format". Do not invent your own.
