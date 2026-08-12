---
name: modern-python
description: Use whenever writing, generating, reviewing, or refactoring Python code. Enforces modern, idiomatic Python conventions covering tooling, typing, style, error handling, testing, and packaging so generated code looks hand-written by a senior Python developer rather than generic or dated.
---

# Modern Python Standards

Determine the target Python version from the project:
- Check `requires-python` in `pyproject.toml`.
- For single-file scripts, check the PEP 723 inline metadata block.
- Otherwise check `.python-version` or the lockfile.
- If none exist, default to the newest stable CPython release.

Treat that version as the syntax ceiling. Favor **clarity and explicitness over cleverness**.

## Environment & tooling

- Use **uv** for dependency management (`uv add`, `uv run`, `uv sync`, `uv lock`).
- Use `pip` only for throwaway scripts outside a managed project.
- Put project metadata in `pyproject.toml`.
- Configure **ruff** as the formatter and linter in `pyproject.toml` under `[tool.ruff]`.
- Use the type checker configured in the project's `pyproject.toml`.
- For single-file scripts, declare dependencies with PEP 723 inline metadata:
  ```python
  # /// script
  # requires-python = ">=3.11"
  # dependencies = ["httpx"]
  # ///
  ```

## Typing

- Type every function signature, including `-> None`.
- Use built-in generics: `list[int]`, `dict[str, int]`, `tuple[int, ...]`.
- Use `X | None` for optional values and `X | Y` for unions.
- Use the `type` statement (3.12+) for type aliases: `type UserId = int`.
- Use `Protocol` for structural typing.
- Use `TypedDict` for dict-shaped data crossing a boundary like JSON or config. Use `dataclass` or `pydantic.BaseModel` elsewhere.
- Use `Self` as the return type for methods that return an instance of their own class.
- Reserve `Protocol` and `TypeVar` for genuine structural constraints; keep single-use functions simply typed.

## Language features to prefer

- Use `match` statements to dispatch on the shape or type of data.
- Use the walrus operator (`:=`) to eliminate duplication between a condition and its body.
- Default `dataclasses` to `slots=True, frozen=True`; drop either only when the class needs mutability or dynamic attributes:
  ```python
  from dataclasses import dataclass


  @dataclass(slots=True, frozen=True)
  class Point:
      x: float
      y: float
  ```
- Use `pathlib.Path` for filesystem paths.
- Use f-strings for all string formatting.
- Use `enum.Enum` or `enum.StrEnum` for closed sets of string constants.
- Use exception groups and `except*` when a function can raise multiple independent errors concurrently.
- Use `itertools`/`functools` for iteration and accumulation: `itertools.batched`, `itertools.pairwise`, `functools.cache`.
- Use comprehensions for straightforward transforms and filters; switch to an explicit loop once a comprehension needs a second condition or nesting level.
- Use context managers for reusable setup-teardown pairs.
- Use early returns and guard clauses to keep functions flat.

## Style specifics

- Let ruff own formatting and line length.
- Use `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE` for module-level constants.
- Order imports stdlib, then third-party, then local, alphabetized within each group; let ruff enforce this.
- Default mutable arguments to `None` and assign the value inside the function body.
- Favor composition and small pure functions over deep inheritance hierarchies.
- Write a one-line docstring for simple functions; use Google or NumPy style for public APIs, matching the existing codebase.

## Error handling

- Raise specific, custom exceptions for domain errors (`class OrderNotFoundError(Exception): ...`).
- Catch specific exception types, or at minimum `Exception`, paired with re-raising or logging.
- Use `raise ... from err` to preserve the exception chain when re-raising.
- Validate inputs at the boundary — function entry, API handler.

## Async

- Use `asyncio.TaskGroup` (3.11+) for structured concurrency with proper exception propagation.
- Use `asyncio.timeout()` (3.11+) as a context manager for timeouts.
- Make a function `async def` only when it awaits something. Keep synchronous and asynchronous I/O in separate functions.

## Testing

- Use pytest with plain `assert` statements.
- Put shared fixtures in `conftest.py`; use `@pytest.mark.parametrize` for multiple inputs of the same behavior.
- Name test files `test_*.py` in a `tests/` directory that mirrors the package structure.
- Give each test one assertion focus and a name describing behavior (`test_raises_when_order_missing`).

## Packaging & project layout

- Use a `src/` layout for anything installable; a flat layout is fine for scripts or notebooks.
- Declare entry points and dependencies in `pyproject.toml`; pin versions via `uv.lock`.

## When reviewing existing code

Flag these as dated when found:
`typing.List/Dict/Optional/Union`, `os.path.join`, `.format()`/`%`-formatting, bare `except:`, mutable default arguments, `unittest.TestCase` in a pytest codebase, manual `for` loops that are really a comprehension or `itertools` call in disguise.

## Matching the existing project

Defer to the codebase's existing type checker, formatter, docstring style, and packaging layout. Reserve the walrus operator and `match` statements for cases that genuinely improve readability.
