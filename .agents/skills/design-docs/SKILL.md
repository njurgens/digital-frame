---
name: design-docs
description: Author and review software design documents in Markdown that argue for a design instead of pre-writing its implementation — structured prose plus Mermaid architectural views (context, container, sequence, class/domain, state, ER). Use this skill whenever someone asks for a design doc, technical design, architecture doc, RFC, ADR, tech spec, HLD or LLD, or asks to review, critique, or improve one. Also reach for it when planning a non-trivial system or feature before implementation, when a plan needs to be recorded for other agents or engineers to work from, or when a document under review is full of code, schemas, or task lists where architectural reasoning belongs. Bundles a section template, diagram selection guidance, a review rubric, and a linter script.
---

# Design Docs

A design doc is an **argument**, not a construction artifact. Its job is to make a case a reader can disagree with: given these facts and these goals, why is *this* the right shape, what did it cost, and what would have to be true for it to be wrong.

The dominant failure mode when a model writes one of these is producing an *implementation manual* — a fluent document full of schemas, interfaces, file layouts, and task lists that commits to a hundred decisions without arguing for any of them. Such a document reads as competent, decays the moment code is written, and gives reviewers nothing to push against. Everything below exists to prevent that.

## Pick a mode

| The request | Mode | Go to |
|---|---|---|
| "Write a design doc for X", "spec this out", "how should we build X" | **Author** | [Authoring](#authoring) |
| "Review this design", "critique this doc", "is this design sound" | **Review** | [Reviewing](#reviewing) |
| "Update the doc to reflect Y" | **Author**, but preserve existing IDs and section numbering | [Authoring](#authoring) |

---

## Gate 0 — should this document exist?

Check before writing anything. Producing an unnecessary design doc wastes the reader's attention and trains people to skim the ones that matter.

**Say so and stop** if any of these hold:

- The solution space is unambiguous — one obvious approach, no meaningful trade-off. Write the code instead.
- The document would only say "here is how we will build it," with no contested decision anywhere.
- The work is exploratory prototyping, where the point is to learn by building.
- The change is mechanical: a refactor, a dependency bump, a config change with no structural consequence.

**Proceed** when three or more apply: the right design is genuinely uncertain or contested; the decision is expensive or hard to reverse; it crosses a team, service, or trust boundary; reviewers who will never read the diffs need to weigh in; cross-cutting concerns are likely to be forgotten; a legacy system needs a high-level explanation to exist at all.

When declining, offer the alternative: a short ADR for a single decision, an issue description, or just doing the work.

---

## The abstraction ladder

This is the core discipline. Use the **highest rung that answers the reader's question**, and descend only when the rung above genuinely cannot carry the meaning.

| Rung | Form | When |
|---|---|---|
| **L0** | Prose claim plus rationale | Always. The default. |
| **L1** | Mermaid architectural view | Claims about structure, ordering, state, relationships |
| **L2** | Semantic table — contract, trade-off, failure mode, quality scenario | Claims about a set of parallel cases |
| **L3** | Signature sketch: names and shapes, no bodies | Rare — only when the *shape* of an interface is itself the contested decision. Budget: 8 lines, twice per doc |
| **L4** | Pseudocode | Only for a genuinely novel algorithm whose correctness is the design question. Budget: 15 lines, once, with the invariant it preserves stated |
| **L5** | Real code, schemas, config, manifests | Never. Link to a prototype or spec file |

### Five tests for any candidate passage

A **yes** on any of the first four means cut it or move it up a rung:

1. **Compile test** — could this paste into a source file, schema file, or CI config and be valid there?
2. **Refactor test** — would a behavior-preserving refactor make this text wrong? Design docs describe what must be true, not how it is currently spelled.
3. **Swap test** — would changing language, framework, or library force a rewrite of this passage? (Unless that choice *is* the decision under discussion.)
4. **Disagreement test** — can a competent reader disagree with this? If nothing here is contestable, it is description wearing design's clothes.

And one at document level:

5. **Fork test** — if two competent teams implemented from this doc, would they produce systems satisfying the same invariants and exposing the same contracts? Yes means the altitude is right. *Character-for-character similar code* means too low. *Incompatible systems* means too high, or constraints are missing.

### What to write instead

When the pull toward implementation shows up, this is the substitution:

| Impulse | Write instead |
|---|---|
| Full API spec | Contract table: operation, purpose, caller, idempotency, failure modes, invariant preserved |
| Database schema | ER view plus prose on ownership, source of truth, cardinality rationale, retention, consistency |
| Class or interface files | Domain class diagram of responsibilities and relationships, plus why the boundaries fall there |
| Config manifests | Prose on deployment topology and its constraints; a deployment view if topology is non-obvious |
| Step-by-step algorithm | Sequence diagram or flowchart, plus the invariant maintained at each stage |
| Error-handling code | Failure-mode table: failure, trigger, blast radius, detection, response, residual risk |
| Retry or backoff logic | The policy in prose, with reasoning about idempotency and thundering herd, and parameters with units |
| Migration scripts | Rollout narrative: the sequence of states production passes through, the compatibility guarantee at each, the backout condition |
| A prose walkthrough of a lifecycle | State diagram, plus which transitions are deliberately forbidden and why |

---

## Authoring

### 1. Gather before drafting

Establish what is actually known. The most damaging thing a model can do here is describe an existing system confidently without having looked at it — fabricated behavior in the context section poisons every decision downstream.

Read the code, docs, or dashboards available. For anything that stays unverified, carry it as an explicit assumption rather than smoothing it into the prose.

### 2. Mark provenance on every non-obvious factual claim

Use inline markers while drafting: `[verified: <source>]`, `[reported: <who>]`, `[assumed]`, `[unknown]`.

Rules that matter: never state a metric, rate, cost, version, or capacity figure without one. Never mark something `[verified]` unless it was actually inspected during this task. Anything `[assumed]` and load-bearing also goes in the assumption register. Anything `[unknown]` and needed becomes an open question. If the central argument rests on an assumption, say so in the summary — a design built on unverified ground is a hypothesis, and the reader deserves to know.

Fabricated plausible numbers are the worst failure available here, because they read as authoritative and get built on.

### 3. Draft the sections

Read `references/structure.md` for the section-by-section specification — what each answers, what it must contain, and how each one characteristically fails. Start from `assets/design-doc-template.md`.

Do not skip **Solution Strategy**. That section is the bridge from goals to structure, and omitting it produces the classic defect: an overview paragraph, then sudden full detail, with no reasoning connecting them.

### 4. Choose views deliberately

Read `references/views.md` before drawing anything. It maps reader questions to diagram types, gives per-view rules (a class diagram in a design doc models the *domain*, not the eventual code), covers Mermaid syntax hazards, and lists the cross-artifact consistency invariants.

Three or seven diagrams for a standard doc. One diagram, one question. Every diagram gets prose before it stating its single claim and prose after it saying what is notable or contested — a reader who cannot see the picture still needs the design.

### 5. Assign stable IDs

`G-n` goal, `NG-n` non-goal, `C-n` constraint, `A-n` assumption, `QA-n` quality scenario, `D-n` decision, `ALT-n` alternative, `F-n` failure mode, `R-n`/`TD-n` risk and debt, `V-n` validation criterion, `OQ-n` open question, `Figure n` diagram.

These matter more for agent-to-agent work than for humans: they turn vague commentary into addressable references, and they let an implementing agent check its own work against specific claims. Never renumber — retire an item in place.

### 6. Self-check

Run the linter, then read the output critically — it catches mechanical violations, not weak arguments:

```bash
python scripts/lint_design_doc.py <path-to-doc.md>
```

Then confirm by hand what no script can see:

- The summary names a trade-off.
- At least two genuine alternatives, each with something it does *better* than the chosen design. An alternative dismissible in one clause was never a real alternative.
- Every decision states a negative consequence.
- Non-goals are things that could reasonably have been goals and were excluded — not negated goals like "should not lose data."
- At least one runtime view shows a failure path.
- Open questions is non-empty, or its emptiness is explicitly justified.

### 7. Report honestly

When handing the doc over, name what is weakest in it and which assumptions carry the most weight. A design doc presented as finished and certain is less useful than one that points at its own soft spots.

---

## Reviewing

Read `references/review-rubric.md` for the full seven-pass rubric, severity definitions, and output format. In short:

**Stance.** Review the argument, not the wording. Produce findings; do not rewrite the document. State the question the author failed to answer rather than the fix you would apply. Reward a doc that admits uncertainty; penalize one that reads smoothly and commits to nothing.

**Start with the linter** — it clears the mechanical passes in seconds so attention goes to the reasoning:

```bash
python scripts/lint_design_doc.py <path-to-doc.md>
```

**Then the passes that need judgment:** are the trade-offs real, are the alternatives genuine rather than strawmen, does every goal have a decision serving it, are the cross-cutting sections specific rather than vacuous, are the failure modes complete, is the design actually sound.

**If nothing in the document is contestable, that is itself a blocking finding** — it means the doc is a manual, and Gate 0 should have caught it.

Cite anti-patterns by name from `references/anti-patterns.md` so authors and reviewers share vocabulary.

---

## Sizing

| Scope | Target | Ceiling |
|---|---|---|
| Mini doc — incremental feature, subsystem change | 400–900 words | 1,500 |
| Standard | 1,500–3,500 words | 5,000 |
| Large or greenfield | 3,500–6,000 words | ~8,000 |

Past the ceiling the problem is under-decomposed: split into a parent doc plus children and link them. Never pad to reach a target.

---

## Bundled files

| File | Read when |
|---|---|
| `references/structure.md` | Drafting or reviewing sections — the per-section spec |
| `references/views.md` | Choosing, drawing, or checking any diagram |
| `references/review-rubric.md` | Reviewing a document |
| `references/anti-patterns.md` | Either mode — named failures with tells and fixes |
| `assets/design-doc-template.md` | Starting a new document |
| `scripts/lint_design_doc.py` | Before emitting a draft, and first thing in a review |
