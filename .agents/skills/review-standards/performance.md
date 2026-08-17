---
name: performance
description: 'Review checklist for the performance domain of a peer review. Read this when assigned the "performance" domain: algorithmic complexity, N+1 queries, missing indexes, blocking I/O, unbounded memory, repeated work, caching, and payload size. Includes performance-specific severity calibration and worked findings.'
---

# Domain: performance

You are reviewing **cost**: time, memory, I/O, and how each of those grows with
input size and load.

## In scope

- Algorithmic complexity: a nested loop over the same collection, a linear scan
  inside a loop, sorting inside a loop, repeated `in` checks against a list where
  a set would do, quadratic string concatenation.
- Database access: N+1 queries (a query inside a loop over rows), missing
  `select_related`/`join`/eager loading, `SELECT *` on a wide table, a query with
  no index on the filtered column, a query with no `LIMIT` on an unbounded table,
  a write per item where a batch insert exists.
- Missing or wrong indexes for a new query pattern; a migration that adds an
  index on a large table without a concurrent/online option.
- Network calls: a request per item instead of a batch endpoint, no connection
  pooling or session reuse, no timeout, serial calls that could be concurrent,
  chatty round trips inside a request handler.
- Blocking work in the wrong place: synchronous I/O inside an async function or
  event loop, CPU-heavy work in a request handler that should be a background
  job, a `sleep` on a hot path.
- Memory: reading a whole file or whole result set into memory instead of
  streaming/iterating; building a large intermediate list where a generator
  works; caches with no eviction or size bound; retaining references that prevent
  collection.
- Repeated work: recomputing the same value inside a loop, recompiling a regex
  each call, re-parsing config per request, re-creating a client per call.
- Caching: a cache added with no invalidation story, or an expensive pure
  function called repeatedly with the same arguments and no memoization.
- Concurrency cost: a lock held across I/O, a lock with more scope than needed,
  a thread or task spawned per item with no pool or bound.
- Payload size: returning unbounded collections, no pagination, sending fields
  the caller does not need, uncompressed large responses.
- Hot-path awareness: is this code on a per-request, per-row, or per-frame path,
  or does it run once at startup? Cost only matters relative to call frequency.

## Out of scope

- Wrong results — that is `correctness`.
- Attacker-controlled resource exhaustion — that is `security`. Ordinary load is
  yours; a hostile input designed to blow up the process is theirs.
- Where the expensive code lives — that is `architecture`.
- Test suite runtime — that is `testing`.

## Checklist

1. For each new loop, ask what N is in production. A quadratic loop over 5 items
   is fine; over 50,000 rows it is not.
2. Look inside every loop for: a query, an HTTP call, a file open, a lock
   acquisition, a regex compile, a sort, or an object construction that could be
   hoisted.
3. For every new query, name the column it filters on and check whether an index
   exists (`grep` the migrations/schema).
4. For every ORM access to a related object, check whether it was eager-loaded.
5. For every new endpoint returning a collection, check for pagination or a hard
   limit.
6. For every `open()`/`read()`/`readlines()`, check whether the file could be
   large and whether streaming is available.
7. In async code, `grep` for synchronous library calls (`requests`, `time.sleep`,
   blocking file I/O, blocking DB drivers).
8. For every new cache or dict used as a cache: what bounds it, and what
   invalidates it?
9. For every `list(...)`, comprehension, or `.all()` on a query: could it be
   iterated lazily?
10. For every lock/mutex: what runs while it is held?
11. Check whether an existing batch/bulk API was available and not used.
12. If the change claims a performance improvement, check whether there is any
    measurement backing it.

State the growth, not just the smell: "O(n²) over the order-lines table, which
has ~200k rows per tenant" is actionable; "this looks slow" is not.

## Severity calibration for performance

- `blocker` — Will take down or badly degrade production: unbounded memory growth
  on a real workload, a query with no index on a large table in a hot path, an
  N+1 across a table that grows with users, blocking I/O on the event loop of a
  service that serves all traffic through it.
- `major` — A clear, measurable regression on a real path: a per-request cost
  that grows with data size, serial network calls where a batch exists, a
  missing index on a moderately sized table, an unbounded cache.
- `minor` — Wasteful but bounded: recompiled regex, an avoidable intermediate
  list, a redundant computation on a warm path with small N.
- `nit` — Micro-optimizations with no measured impact. Keep these rare;
  readability usually wins over a nanosecond.

## Worked examples

**Example 1**

```
### FINDING 1
SEVERITY: major
FILE: src/reports/summary.py:64-71
ISSUE: The loop calls `Order.objects.get(id=line.order_id)` for each line item, producing one query per row — roughly 2,000 queries for a typical monthly report instead of one.
FIX: Fetch the orders once with `Order.objects.filter(id__in=order_ids)` before the loop and index them by ID, or use `select_related("order")` on the line-item query.
```

**Example 2**

```
### FINDING 2
SEVERITY: blocker
FILE: src/ingest/loader.py:19
ISSUE: `json.loads(path.read_text())` loads the entire upload into memory; ingest files are routinely several GB, so this will exhaust the worker's memory and get it OOM-killed.
FIX: Stream the file with a line-delimited JSON reader and process records in batches.
```

## Output

Use the format defined in [./SKILL.md](./SKILL.md) under "Required output
format". Do not invent your own.
