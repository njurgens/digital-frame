---
name: testing
description: 'Review checklist for the testing domain of a peer review. Read this when assigned the "testing" domain: coverage of new behavior, regression tests, assertion quality, flakiness, over-mocking, test isolation, and weakened or deleted tests. Includes testing-specific severity calibration and worked findings.'
---

# Domain: testing

You are reviewing the **tests**: whether this change is covered, whether the
tests would actually fail if the code broke, and whether they will stay
trustworthy over time.

## In scope

- Coverage of the new behavior: is there a test for what this change added?
- Regression tests: if this change fixes a bug, is there a test that fails on the
  old code and passes on the new?
- Assertion quality: does the test assert on the thing that matters, or does it
  assert `assert result is not None` and call it a day?
- Edge cases in tests: empty input, boundary values, error paths, not just the
  happy path.
- Test independence: does the test depend on execution order, on state left by
  another test, or on a shared mutable fixture?
- Determinism and flakiness: `sleep`, wall-clock time, `random` without a seed,
  real network or DNS, real filesystem paths outside a temp dir, timing
  assumptions, dependence on dict/set ordering.
- Over-mocking: does the test mock the very thing it claims to verify, so it
  passes regardless of the implementation?
- Under-mocking: does a unit test hit a real database, real HTTP endpoint, or
  real clock?
- Test naming and failure output: when it fails at 3am, does the name and the
  assertion message say what broke?
- Fixtures and helpers: duplicated setup, giant fixtures that hide what the test
  depends on, fixtures with side effects.
- Deleted or weakened tests: did this change delete a test, loosen an assertion,
  widen a tolerance, or add a skip/xfail marker? Ask why.
- Test placement and wiring: is the new test in a file the runner picks up? Is a
  new test directory added to the CI config?
- Async test correctness: is the coroutine actually awaited, or does the test
  pass by never running?

## Out of scope

- Whether the production code is correct — that is `correctness`. If you find a
  bug, do not report it; report the missing test that would have caught it.
- Test file naming conventions and formatting — that is `code-style`, unless the
  name is so unclear that a failure would be unreadable.
- How long the test suite takes as a product concern — mention runaway test cost
  only if a single new test adds minutes.

## Checklist

1. List the behaviors this change adds or modifies. For each one, `grep` the test
   files for a test that exercises it. Name the ones with no test.
2. For a bugfix: is there a test that reproduces the original bug?
3. Read each new test's assertions. Would the test fail if you deleted the
   change's core logic? If not, it is not testing anything.
4. Look for `assert True`, `assert x == x`, assertions on mock call counts only,
   and tests with no assertion at all.
5. Look for error paths: is there a test that the function raises/returns an
   error for bad input?
6. Search the new tests for `sleep`, `time.time`, `datetime.now`, `random`,
   `requests`, `socket`, hard-coded ports, hard-coded absolute paths.
7. Check that mocks patch the object where it is *used*, not where it is defined,
   and that patched attributes actually exist.
8. Check that fixtures clean up: temp dirs removed, patches undone, DB rolled
   back.
9. Check for tests that share module-level state or a class attribute.
10. Check for `skip`, `xfail`, `only`, `.only(`, `fdescribe`, `it.only` left in.
11. If parameterized, do the cases cover distinct behavior or just repeat one
    path with different numbers?
12. Does any test depend on a fixture file that the diff does not add?

## Severity calibration for testing

- `blocker` — The change is untested and the untested part is high-risk (money,
  auth, data migration, deletion), or an existing test was deleted/disabled to
  make the change pass, or a test asserts nothing but appears to guard critical
  behavior.
- `major` — New user-visible behavior with no test at all; a test that cannot
  fail; a clearly flaky construct (real sleep, real network, unseeded random) in
  a test that will run in CI.
- `minor` — Happy path is covered but an obvious edge case or error path is not;
  a weak assertion alongside a strong one; a slow test that could be fast.
- `nit` — Unclear test name, duplicated setup that could be a fixture, a missing
  assertion message.

## Worked examples

**Example 1**

```
### FINDING 1
SEVERITY: major
FILE: tests/test_invoice.py:41
ISSUE: `test_apply_discount` mocks `Invoice.recalculate`, which is the method the change actually modified, so the test passes whether or not the new proration logic is correct.
FIX: Let `recalculate` run for real and assert on the resulting line-item totals for a mid-cycle upgrade.
```

**Example 2**

```
### FINDING 2
SEVERITY: minor
FILE: tests/test_retry.py:77
ISSUE: The test calls `time.sleep(2)` to wait for the backoff, which adds two seconds to every CI run and will start failing intermittently on a loaded runner.
FIX: Inject a fake clock or patch the sleep function and assert the requested delays instead of waiting for them.
```

## Output

Use the format defined in [./SKILL.md](./SKILL.md) under "Required output
format". Do not invent your own.
