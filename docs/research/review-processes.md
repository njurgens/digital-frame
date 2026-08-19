# Research: review-process patterns (for issue #64)

Date: 2026-08-19. Sources verified by fetch; snippets from search where fetch failed.

## Question 1 — Is "dynamic (trigger-based) review as the default" an established pattern?

Yes — it is the current direction of travel, with multiple independent instances:

1. **Risk-based code review** — Cortex/Tealium guide (cortex.io/post/risk-based-code-review, 2026).
   "Instead of giving every pull request the same scrutiny, you route human attention
   by risk, letting low-risk changes ship with light or automated review and reserving
   deep human review for the changes that are expensive to get wrong."
   Tealium encodes it with PR labels: >1000 lines, file with no tests, DB schema change.
   Cites SmartBear/Cisco study: reviewer defect detection drops sharply past 200–400
   lines per sitting (~500 lines/hour ceiling) — the economic reason uniform review
   degrades into rubber-stamping.
2. **Meta RADAR** (arXiv:2605.30208, "Automating Low-Risk Code Review at Meta").
   Multi-stage funnel: authorship classification → eligibility gates → static
   heuristics → machine-learned Diff Risk Score → LLM automated review →
   deterministic validation. 535K+ diffs reviewed; 331K+ landed. RADAR-reviewed
   diffs: revert rate 1/3, production-incident rate 1/50 of non-RADAR diffs.
3. **Caliper "lenses"** (getcaliper.dev/lenses.html) — specialist review passes
   (security, data-integrity, api-contracts, concurrency, design) that are
   **auto-activated by trigger rules**:
   - File-path triggers: `migrations/` → data-integrity; `/api/` → api-contracts;
     `route.ts` → api-contracts; `factory.ts`/`provider.ts`/`registry.ts` → design.
   - Diff-content triggers: `auth|session|token|jwt|passport|credential|permission`
     → security; `mutex|semaphore|lock|atomic|Promise.all|Worker` → concurrency.
   - Structural triggers: 3+ changed files in the same directory → design.
   This is exactly the "trigger rules" concept from the issue, shipped as a product.
4. **Grabowski 2026** (arXiv:2606.27045, "Spec Growth Engine"): review rigor tied to
   blast radius and reversibility — "changes to public contracts and core invariants
   get a mandatory human gate before merge, additive changes proceed with
   asynchronous review, and purely internal, reversible refactors need no human
   gate at all."
5. **GitHub required-reviewer rule** (GA 2026-02-17): mandate extra review for
   specific paths (e.g. auth code), layered on ownership rules.
6. **Cortex's own practice**: first-pass review bot fans out to specialist reviewers
   defined **as plain markdown files in the repo** (security, performance, testing
   and risk, query engine) — the same shape as this repo's skills. Every review ends
   with a human-effort recommendation (minimal/low/medium/high).

## Question 2 — Is "leverage-ordered waterfall" (sign off high-leverage first) established?

Yes, under three names:

1. **1-10-100 rule / Boehm cost-of-change curve.** Boehm 1981 (Software Engineering
   Economics): cost to fix a defect rises ~an order of magnitude per lifecycle phase.
   McConnell, "An Ounce of Prevention" (2001, stevemcconnell.com): upstream defects
   cost 10–100x more to remove late; "Work on a software project generally follows a
   pattern of a small number of high-leverage upstream decisions providing the basis
   for a much larger number of lower-leverage downstream decisions." — McConnell's
   own words match the issue's framing. A one-sentence requirements change can imply
   changes across hundreds of lines, dozens of tests, pages of docs.
2. **Stage-Gate (Robert Cooper)** — the canonical waterfall-of-sign-offs: stages
   separated by Go/Kill gates; "Build tough Go/Kill decision points into your
   process — a funnel, not a tunnel." Known failure mode: treating gates as
   bureaucratic sign-off rather than genuine kill points.
3. **Design/architecture review before implementation** — V8 design-review
   guidelines (v8.dev/docs/design-review-guidelines); NASA SWE-143 (architecture
   review before PDR; "the earlier the review board is involved ... the more
   effective the inputs"); AWS ARB (architecture review "after the design phase —
   before a build or purchase decision").

## Question 3 — Is there an existing artifact that orders review *aspects* by leverage?

Yes: **The Code Review Pyramid** (Gunnar Morling, 2022; morling.dev/blog/the-code-review-pyramid/).
Five layers; bottom = foundation = most important; top = least important / most
automatable. Extracted from the original SVG:

1. **API design** (foundation): API as small as possible / as large as needed; one
   way of doing one thing; principle of least surprises; clean API/internals split;
   **no breaking changes to user-facing parts (API classes, config, metrics, log
   formats)**; new API generally useful, not overly specific.
2. **Implementation**: satisfies original requirements; logically correct; no
   unnecessary complexity; robust (concurrency, error handling); **performant**;
   **secure**; observable; dependencies pull their weight / license acceptable.
3. **Documentation**: new features documented; README / API docs / user guide /
   reference covered; understandable, no significant typos.
4. **Tests**: all passing; new features reasonably tested; corner cases; unit where
   possible, integration where necessary; tests for NFRs (e.g. performance).
5. **Code style** (top): formatting applied; naming conventions; DRY; readable.

FAQ: "The lower parts of the pyramid should be the foundation of a code review and
take up the most part of it." Intention: focus on what matters most + which parts
should be automated.

## Question 4 — Performance vs correctness: which comes first?

No canonical source orders these two against each other:

- The Code Review Pyramid puts **both in the same layer** (implementation),
  co-equal: "logically correct" and "performant" are sibling bullets.
- The **test pyramid** (Fowler; OutSystems; testomat.io) orders *execution*:
  functional/correctness tests before performance/load tests — "you don't want to
  perform load testing with non-working code."
- But review ≠ test execution. Performance *defects* split into two classes:
  - **Design-level** (algorithmic complexity, hot-path allocation, data-flow / N+1
    patterns): structural — same leverage class as architecture. Cheapest to fix
    pre-implementation per 1-10-100. This repo's own issues #35 (full-screen
    surface copy per frame → GC pressure) and #32 (PIL render on main thread
    blocking the event loop) are exactly this class.
  - **Measurement-level** (benchmarks, load tests): late, after correctness is
    established (test-pyramid logic).

## Synthesis (proposed, for discussion)

- **Dynamic/selective as the default process** — well supported (Q1). Full gauntlet
  becomes the escalation path for high-blast-radius changes, or when triggers fire
  broadly.
- **Waterfall order, high → low leverage**: architecture → security →
  backwards-compatibility → performance (design-level) → correctness → testing →
  technical-communication → code-style.
  - API/contract design is the pyramid's *foundation* — supports backwards-compat
    sitting high.
  - Code-style at the bottom matches the pyramid's top (least important,
    automatable).
  - If "performance" is split (design-level early, measurement-level late), the
    user's "performance before correctness" intuition is defensible; if performance
    means measurement only, the test pyramid says the opposite.
- **Document process** (design docs / prose artifacts): architecture +
  technical-communication, unchanged — design review before implementation is the
  established pattern (Q2.3).
- Prior art to cite in the issue: Code Review Pyramid (leverage ordering),
  risk-based/trigger-based review (Caliper lenses, RADAR, Grabowski, GitHub
  required-reviewer), Stage-Gate (gates with kill points), 1-10-100 (economics).

## Source list

- https://www.cortex.io/post/risk-based-code-review (fetched in full)
- https://arxiv.org/abs/2605.30208 (Meta RADAR, abstract)
- https://getcaliper.dev/lenses.html (fetched in full)
- https://arxiv.org/abs/2606.27045 (Grabowski, abstract)
- https://stevemcconnell.com/articles/an-ounce-of-prevention/ (fetched in full)
- https://www.morling.dev/blog/the-code-review-pyramid/ + SVG (fetched in full)
- https://v8.dev/docs/design-review-guidelines (search snippets only; fetch failed)
- https://swehb.nasa.gov/display/SWEHBVB/SWE-143+-+Software+Architecture+Review (snippet)
- https://aws.amazon.com/blogs/architecture/build-and-operate-an-effective-architecture-review-board/ (snippet)
- https://www.toolshero.com/innovation/stage-gate-process/ + Cooper PDFs (snippets)
- Test pyramid: https://martinfowler.com/articles/practical-test-pyramid.html,
  https://www.outsystems.com/forums/discussion/100256/ (snippet),
  https://testomat.io/blog/testing-pyramid-role-in-modern-software-testing-strategies/ (snippet)
