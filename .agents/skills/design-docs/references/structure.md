# Document Structure

Section-by-section specification. Each entry gives what the section answers, what belongs in it, and how it characteristically fails.

**Contents:** [Section map](#section-map) · [Front matter](#0-front-matter) · [Summary](#1-summary) · [Context](#2-context-and-scope) · [Goals](#3-goals-and-non-goals) · [Constraints](#4-constraints-and-assumptions) · [Quality scenarios](#5-quality-attribute-scenarios) · [Solution strategy](#6-solution-strategy) · [Views](#7-architecture-views) · [Decisions](#8-key-design-decisions) · [Alternatives](#9-alternatives-considered) · [Data](#10-data-lifecycle-and-ownership) · [Failure modes](#11-failure-modes-and-degradation) · [Cross-cutting](#12-cross-cutting-concerns) · [Rollout](#13-rollout-migration-and-backout) · [Risks](#14-risks-and-technical-debt) · [Validation](#15-validation) · [Open questions](#16-open-questions) · [Glossary](#17-glossary) · [Degree of constraint](#appendix-degree-of-constraint)

## Section map

**R** = required above mini size. **C** = include when the trigger applies. Delete inapplicable sections rather than leaving empty headings, and note in one line why.

| # | Section | Req | Trigger |
|---|---|---|---|
| 0 | Front matter | R | — |
| 1 | Summary | R | — |
| 2 | Context and scope | R | — |
| 3 | Goals and non-goals | R | — |
| 4 | Constraints and assumptions | R | — |
| 5 | Quality attribute scenarios | R | — |
| 6 | Solution strategy | R | — |
| 7 | Architecture views | R | — |
| 8 | Key design decisions | R | — |
| 9 | Alternatives considered | R | — |
| 10 | Data lifecycle and ownership | C | System stores or moves persistent data |
| 11 | Failure modes and degradation | C | System has availability or correctness requirements |
| 12 | Cross-cutting concerns | R | — |
| 13 | Rollout, migration, backout | C | Replaces or modifies something already running |
| 14 | Risks and technical debt | R | — |
| 15 | Validation | R | — |
| 16 | Open questions | R | — |
| 17 | Glossary | C | Doc introduces five or more domain terms |
| 18 | References | R | — |

---

## 0. Front matter

Machine-readable YAML. Reviewers key off it; implementing agents use it to detect staleness.

```yaml
title: <noun phrase, not a verb phrase>
status: draft | in-review | accepted | superseded | withdrawn
authors: [...]
reviewers: [...]
created: YYYY-MM-DD
updated: YYYY-MM-DD
supersedes: [<doc-id>]
superseded_by: <doc-id | null>
related_adrs: [ADR-0007]
scope_level: system | service | component | feature
```

## 1. Summary

Three to six sentences: the problem, the chosen shape in one clause, and the principal trade-off accepted.

A reader who reads only this should be able to state one thing the design gives up.

*Fails as:* a table of contents ("This document describes the architecture of..."). That opening tells the reader nothing and is a reliable signal the rest will be descriptive too.

## 2. Context and scope

Objective background only — what exists today, what forces are acting, what is changing. Assume domain knowledge but not knowledge of this particular corner; link rather than re-explain.

Every non-obvious claim about the *existing* system carries a provenance marker. This is the section where confident fabrication does the most damage, because everything downstream inherits it.

*Fails as:* smuggling in solution content or goals. If a sentence here contains "we will" or "should," it belongs in a later section.

## 3. Goals and non-goals

Bulleted and ID'd (`G-1`, `NG-1`). Goals are outcomes, not features or activities.

**Non-goals carry the most value and get botched the most often.** A non-goal is something that could reasonably have been a goal and was deliberately excluded — not a negated goal, and not something nobody would have expected anyway.

- Good: "Multi-region active-active writes." Someone might reasonably have wanted it; we chose not to.
- Not a non-goal: "The system should not lose data." That is a negated goal — restate it as a goal or a quality scenario.
- Not a non-goal: "Rewriting the frontend," unless someone might plausibly have expected that.

Each non-goal gets a half-sentence on why not now and what would change the answer. That clause is what stops the same debate recurring every quarter.

## 4. Constraints and assumptions

**Constraints** (`C-n`) are externally imposed and non-negotiable — regulatory, organizational, technical, budgetary, schedule. Cite the source of each; an uncited constraint is usually someone's preference in disguise.

**Assumptions** (`A-n`) are believed but unverified. Each needs to be falsifiable and carry impact-if-wrong. Unverified assumptions are the primary source of design failure and the thing a fluent draft most readily hides.

| ID | Assumption | Confidence | If false | How to verify |
|---|---|---|---|---|
| A-1 | Peak write rate stays under 2k/s through FY27 | Medium | Sharding becomes required; §6 strategy invalid | Query existing metrics |

## 5. Quality attribute scenarios

Replace vague quality words — fast, scalable, secure, reliable — with measurable scenarios. Six parts, table form:

| ID | Source | Stimulus | Environment | Response | Measure |
|---|---|---|---|---|---|
| QA-1 | End user | Submits an order | Normal load, p95 | Order accepted and durably recorded | < 300 ms, ≥ 99.9% monthly |
| QA-2 | Upstream service | Sends malformed event | Any | Event quarantined, alert raised, pipeline continues | 0 stalls; alert < 60 s |

Every quality word used anywhere in the doc should trace to a scenario here, or come out. If a target is not yet known, write `TBD` and file an open question — inventing a plausible-looking figure is far worse than admitting the gap, because the invented number gets designed against.

## 6. Solution strategy

The bridge from goals to structure, and the section most often skipped. Skipping it produces the "draw two circles, then draw the rest of the owl" defect: an overview, then sudden detail, nothing connecting them.

In prose:

- The central organizing idea, one or two sentences. ("We treat X as an append-only log and derive everything else from it.")
- The two to four principles that eliminated most of the solution space, and what each eliminated.
- The degree-of-constraint mode — see the [appendix](#appendix-degree-of-constraint).
- An explicit mapping: for each `G-n`, the strategic move that serves it.

## 7. Architecture views

Diagrams plus prose, never code. See `views.md`. Order outside-in: context → building blocks → runtime scenarios → state → data → deployment. Omit any view carrying no contested claim.

## 8. Key design decisions

Each significant decision gets a compact record. The one-line form:

> In the context of **\<use case\>**, facing **\<concern\>**, we chose **\<option\>** over **\<rejected options\>** to achieve **\<quality\>**, accepting **\<downside\>**, because **\<rationale\>**.

Then two to five sentences of elaboration, including the negative consequences — a decision recorded without its costs is advocacy, not a record.

Decisions that are large, expensive, risky, or contentious deserve extraction into standalone ADRs (title, status, context, decision, consequences, confirmation), linked from here with a one-line summary. An accepted ADR is immutable: a change of mind produces a new one that supersedes it and updates the old status.

## 9. Alternatives considered

At least two alternatives a competent engineer would actually have proposed. Include "do nothing" or "extend the existing system" whenever a system already exists.

For each: what it is in two or three sentences, **what it does better than the chosen design**, what it costs, and the specific goal or constraint that ruled it out.

The "does better" clause is mandatory and is the integrity check on the whole section. Every real alternative wins on something. An alternative dismissed in one clause was a strawman, and its presence weakens the doc rather than strengthening it — it signals the author was performing diligence rather than doing it.

A comparison table scored against goals and quality scenarios by ID belongs alongside the prose.

## 10. Data lifecycle and ownership

Prose plus an ER view. Cover: source of truth for each entity, who may write it, how records are created and destroyed, retention and deletion, consistency model and where staleness is tolerable, classification of sensitive fields, and what happens to in-flight data during failure.

No DDL, no column types, no indexes.

## 11. Failure modes and degradation

The section that most separates a real design doc from a plausible-sounding one, and the one a fluent draft is most likely to omit entirely.

| ID | Failure | Trigger | Blast radius | Detection | Designed response | Residual risk |
|---|---|---|---|---|---|---|
| F-1 | Ledger unavailable | Deploy or partition | Order writes blocked | Write-path error rate | Queue and retry; reads unaffected | Queue bounded — past 10 min, read-only |

State in prose what the system does when it cannot do its job — fail closed, fail open, degrade, or queue — and why that is right *for this domain*. Every external dependency named in the context view should appear here.

## 12. Cross-cutting concerns

Short subsections, two to five sentences each: security, privacy, observability, operability, cost, compatibility, and accessibility or internationalization where user-facing.

Each names what changes about that concern **because of this design** — the new attack surface, the new signals needed, the new cost driver. "We will follow security best practices" is worse than saying nothing, because it occupies the space where the real answer belongs and lets a reviewer's eye slide past.

For observability specifically: name the questions an on-call engineer will need to answer at 3am, and the signal that answers each. The questions, not the metric names.

## 13. Rollout, migration, and backout

A prose narrative of the sequence of states production passes through, and the compatibility guarantee at each. Include the backout condition — "we revert if X" — and whether backout remains possible after each step. Irreversibility is a design property and belongs on the record.

Not a task list. Not a schedule.

## 14. Risks and technical debt

Prioritized. Distinguish **risk** (might happen) from **debt** (definitely incurred, deliberately). For debt, state the interest rate: what gets harder, and when it comes due.

| ID | Item | Type | Impact | Likelihood | Mitigation or repayment trigger |
|---|---|---|---|---|---|

## 15. Validation

Rarely included, disproportionately valuable. The observable evidence that would confirm the design achieved its goals — and, critically, the evidence that would show it did not. Tie each to a `G-n` or `QA-n`.

This is what makes the document falsifiable, and it is what an implementing agent checks its own work against.

| ID | Claim | Evidence of success | Evidence of failure | Traces to |
|---|---|---|---|---|

## 16. Open questions

`OQ-n`, each with the question, why it is unresolved, who or what resolves it, and whether it blocks implementation.

A draft with no open questions is either trivial or dishonest. If a document genuinely has none, state why the space is fully closed.

## 17. Glossary

Domain and technical terms as stakeholders use them. A term table is cheap and prevents the most common silent review failure: two readers agreeing on a sentence while meaning different things by a word in it.

---

## Appendix: degree of constraint

Declare which mode the design is in, in one sentence in Solution Strategy. The doc's emphasis should match.

**Greenfield / wide-open.** Many solutions possible. The first job is to *narrow*: state the constraints and principles that eliminate most of the space, then design within the remainder. Spend words on the narrowing criteria — a wide-open doc that jumps to one solution has hidden its most important reasoning.

**Boxed-in / legacy.** The available moves are enumerable but no combination is clean. The job is *selection*: lay out the moves, show why the chosen combination is least-bad, and be explicit that all options are compromised. A boxed-in doc that presents its choice as elegant is misleading the reader about what they are inheriting.
