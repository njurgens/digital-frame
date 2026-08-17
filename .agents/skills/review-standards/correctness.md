---
name: correctness
description: 'Review checklist for the correctness domain of a peer review. Read this when assigned the "correctness" domain: logic errors, boundary conditions, null handling, error paths, resource lifetime, races, idempotency, and whether the code does what the task asked. Includes correctness-specific severity calibration and worked findings.'
---

# Domain: correctness

You are reviewing **behavior**: does this code do what the task says it should
do, for normal input, edge input, and failure conditions?

## In scope

- Logic errors: wrong operator, inverted condition, wrong branch, wrong variable.
- Boundary conditions: off-by-one, empty collection, single element, first and
  last iteration, inclusive versus exclusive ranges.
- Null / `None` / `nil` / `undefined` handling, and optional values unwrapped
  without a check.
- Type and unit mismatches: seconds versus milliseconds, bytes versus
  characters, float versus decimal for money, string versus int keys.
- Error handling: exceptions swallowed, caught too broadly, logged and then
  execution continues in a bad state, error return values ignored.
- Resource lifetime: files, sockets, connections, locks, cursors opened without
  a guaranteed release on the error path.
- Concurrency: shared mutable state without synchronization, check-then-act
  races, non-atomic read-modify-write, `await` inside a lock, missing `await`.
- Idempotency and retries: is a retried operation safe to run twice?
- Transactions and partial failure: is a multi-step write atomic, or can it stop
  halfway and leave inconsistent state?
- Input validation: is untrusted or malformed input rejected before use?
- Defaults: is a new default value the safe one? Does a default silently change
  behavior for existing paths?
- Dead or unreachable code, conditions that can never be true, a `return` that
  makes following lines dead.
- Does the implementation actually match the stated task? A change that works
  but does something other than what was asked is a correctness finding.

## Out of scope

- Attacker-driven abuse (injection, authz bypass, secrets) — that is `security`.
  If input is merely malformed, not adversarial, it is yours.
- Whether tests exist or are good — that is `testing`. You may note that a bug
  would have been caught by a test, but do not review the test suite.
- Speed and resource cost — that is `performance`.
- Where the code lives — that is `architecture`.
- Naming and formatting — that is `code-style`.

## Checklist

1. Trace the happy path once with a concrete input. Does the output match the
   task description?
2. Trace the empty case: empty list, empty string, zero, missing key.
3. Trace the failure case: what happens when the call on the line above throws
   or returns an error?
4. Every `try`/`catch` or `except`: is the caught type as narrow as it should be,
   and does the handler leave the program in a valid state?
5. Every early `return`, `break`, `continue`: does it skip cleanup that must run?
6. Every comparison: `<` versus `<=`, `==` versus `is`, `!` placement.
7. Every loop bound and slice index.
8. Every new `if` with no `else`: is the missing branch a real case?
9. Mutation of a collection while iterating it.
10. Mutable default arguments and shared default objects.
11. Integer division, rounding, and floating-point equality.
12. Time: timezone-naive datetimes, DST, clock going backwards, expiry compared
    against the wrong clock.
13. Encoding: bytes decoded with an assumed charset, string length in a
    multi-byte context.
14. Any `TODO`, `FIXME`, or stubbed branch left in the change that returns a
    placeholder value.
15. Whether the change updates all the call sites it needed to — `grep` the
    changed function name.

## Severity calibration for correctness

- `blocker` — Produces silently wrong results, loses or corrupts data, deadlocks
  or hangs, or crashes on an input the feature is explicitly for. Anything where
  the user would not notice the failure until damage is done.
- `major` — A real bug on a realistic path: an unhandled edge case, a swallowed
  error that hides failure, a resource leak, a race that needs load to trigger.
- `minor` — A bug on an unlikely path, a misleading-but-harmless fallback, an
  error message that reports the wrong cause, defensive handling that is missing
  but not yet reachable.
- `nit` — Redundant check, unreachable branch that does no harm, a comparison
  that works but reads ambiguously.

## Worked examples

**Example 1**

```
### FINDING 1
SEVERITY: blocker
FILE: src/billing/invoice.py:132
ISSUE: `total` is computed with `round(cents / 100, 2)` on a float, so line items ending in half-cents round inconsistently and the invoice total can differ from the sum of its rows by a cent.
FIX: Keep the amount in integer cents through the calculation and convert to Decimal only for display.
```

**Example 2**

```
### FINDING 2
SEVERITY: major
FILE: src/api/client.py:88-94
ISSUE: The `except Exception` block logs the failure and returns `None`, so callers at `src/api/sync.py:40` cannot tell a network failure from an empty result and will treat the sync as successful with zero records.
FIX: Narrow the catch to the transport error, and re-raise or return an explicit error value that `sync.py` checks.
```

## Output

Use the format defined in [./SKILL.md](./SKILL.md) under "Required output
format". Do not invent your own.
