---
name: architecture
description: 'Review checklist for the architecture domain of a peer review. Read this when assigned the "architecture" domain: module placement, dependency direction, coupling, cohesion, state ownership, abstraction boundaries, and duplicated capability. Includes architecture-specific severity calibration and worked findings.'
---

# Domain: architecture

You are reviewing **structure**: where code lives, what depends on what, and
whether the shape of the change fits the system it lands in.

## In scope

- Placement: is this code in the right module, layer, package, or service?
- Dependency direction: does a lower layer now import an upper layer? Does a
  domain module now import a framework, transport, or storage detail?
- Coupling: does the change reach into another module's internals instead of
  going through its interface?
- Cohesion: does one class or function now do two unrelated jobs?
- Duplication of capability: does this reimplement something the codebase
  already has (a retry helper, a cache, a config loader, a client)?
- Abstraction level: is the new abstraction earning its keep, or is it a wrapper
  with one caller and no behavior? Conversely, is a genuinely shared concept
  copy-pasted into three places?
- State ownership: who owns this state, is it now owned in two places, is global
  or module-level mutable state being introduced?
- Boundaries and contracts: are new interfaces at a sensible seam, with a clear
  contract, or do they leak implementation details of one side to the other?
- Concurrency model: does this introduce threads, tasks, or background work that
  does not match how the rest of the system runs?
- Configuration and wiring: are dependencies injected/passed, or constructed
  deep inside business logic where they cannot be swapped or tested?
- Error propagation design: does an error cross a boundary in a form the other
  side can act on, or is a low-level exception type now part of a public
  contract?
- Extensibility versus speculation: is there machinery for requirements that do
  not exist?

## Out of scope

- Whether the logic produces the right answer — that is `correctness`.
- Whether external callers break — that is `backwards-compatibility`, even
  though public API shape overlaps. You may comment on where an interface sits;
  leave "this breaks v2 clients" to that reviewer.
- Speed, allocation, query counts — that is `performance`.
- Naming, formatting, function length, idioms — that is `code-style`.
- Whether tests exist for the new structure — that is `testing`.

## Checklist

1. New file or module added: is it in a directory whose existing contents are
   the same kind of thing?
2. New import added: does it point "downward" (toward more general, more stable
   code) or "upward"/sideways in a way that creates a cycle?
3. Does any new import cross a documented boundary (e.g. `domain/` importing
   `web/`, `core/` importing `plugins/`)?
4. Does the change access another component's private members, module-level
   internals, or database tables that another component owns?
5. Does a function now take a flag parameter that switches it between two
   behaviors? That is usually two functions.
6. `grep` for an existing helper with the same job before accepting a new one.
7. Is new mutable global/singleton state introduced? Who resets it?
8. Is a third-party type from a dependency now exposed in an internal interface,
   coupling the whole system to that library?
9. Does the change put business rules inside a controller, view, serializer,
   migration, or template?
10. Is there an interface, factory, or registry with exactly one implementation
    and no stated plan for a second?
11. Does the change split one logical operation across two components such that
    neither can be understood alone?
12. Are transaction, session, or connection lifetimes still owned by one clear
    layer?

## Severity calibration for architecture

- `blocker` — Introduces a circular dependency between modules, breaks a
  documented layering rule the project enforces, or puts ownership of persistent
  state in two places at once so the components can disagree. Also: a design
  that cannot be undone cheaply once shipped (a new persisted format, a new
  public extension point) and is clearly wrong.
- `major` — Business logic in the wrong layer, a new module reaching into
  another's internals, a reimplementation of an existing shared capability, or a
  new global mutable singleton.
- `minor` — An abstraction that is thinner or thicker than it needs to be, a
  helper placed in a plausible-but-not-ideal module, mild feature envy between
  two classes.
- `nit` — Speculative generality with no cost yet, or a file that would read
  better split in two.

## Worked examples

**Example 1**

```
### FINDING 1
SEVERITY: major
FILE: src/domain/order.py:14
ISSUE: The domain model now imports `src/web/serializers.py` to build its JSON payload, which points the dependency from the domain layer up into the transport layer and makes the model unusable outside the web app.
FIX: Move the payload construction into the serializer and have it read fields off the model, so the arrow only points from web to domain.
```

**Example 2**

```
### FINDING 2
SEVERITY: minor
FILE: src/jobs/retry.py:1-48
ISSUE: This adds a new exponential-backoff retry helper, but `src/common/backoff.py` already implements the same policy and is used by four call sites, so the project now has two retry semantics to keep in sync.
FIX: Delete the new helper and call `common.backoff.retry` with a jitter argument instead.
```

## Output

Use the format defined in [./SKILL.md](./SKILL.md) under "Required output
format". Do not invent your own.
