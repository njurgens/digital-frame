# Review Rubric

## Stance

Review the **argument**, not the wording. The question is whether this is the right design and whether the case for it is sound — not whether you would have phrased it differently.

Produce findings; do not rewrite the document. Rewriting takes the design away from its author, and an agent that rewrites rather than questions tends to smooth over exactly the weak joints a review exists to expose.

State the question the author failed to answer, not the fix you would apply. "What does ALT-2 do better than the chosen design?" is a review. "Change ALT-2 to say X" is authorship.

Reward a document that admits uncertainty. Penalize one that reads smoothly and commits to nothing — fluency is not evidence of thought, and a fluent document with no contestable claim is the specific failure this whole discipline exists to catch.

**Absence of disagreement is not agreement.** If you cannot find a single claim worth contesting, that is a blocking finding in itself: the document is a manual, and Gate 0 should have caught it.

Never approve a document whose central claim rests on an unmarked assumption.

## Passes

Run in order. Earlier passes gate later ones — there is no point evaluating the soundness of an argument in a document that is missing half its sections.

Passes 1, 2, and much of 5 are handled by `scripts/lint_design_doc.py`. Run it first so your attention goes to the reasoning.

| Pass | Looks for |
|---|---|
| **1. Structural** | Required sections present; front matter complete; within size ceiling; conditional sections either included or their omission justified |
| **2. Abstraction** | Implementation smuggled in — code fences, schemas, file paths, task lists, endpoint listings, exceptions over budget |
| **3. Argument** | Trade-offs stated; alternatives genuine rather than strawmen; every decision carries a because and a cost; non-goals well-formed; the goals → strategy → structure chain intact |
| **4. Views** | Claim, caption, and surrounding prose for each figure; size limits; a failure path present; Mermaid parses; the diagram type actually answers the question asked |
| **5. Consistency** | The ten invariants in `views.md`; ID references resolve; terminology uniform |
| **6. Honesty** | Provenance markers; numbers with units and sources; assumptions falsifiable; open questions present; no fabricated citations or metrics |
| **7. Coverage** | Cross-cutting sections specific rather than vacuous; failure modes cover every external dependency; validation criteria falsifiable; backout addressed |

## Severity

| Severity | Meaning | Typical instances |
|---|---|---|
| **Blocking** | Cannot be accepted — a core rule is violated or the design is unsound | Code or schemas in the doc; no alternatives, or only strawmen; fabricated metric; central assumption unmarked; Mermaid that will not render; no trade-off stated anywhere; nothing contestable in the document |
| **Major** | The design is probably right but the case is incomplete | Vacuous cross-cutting section; no failure path in any runtime view; a goal with no decision serving it; unquantified quality target; missing backout condition |
| **Minor** | Reduces clarity or reusability | Diagram over its size limit; unlabeled edge; inconsistent terminology; missing ID |
| **Nit** | Cosmetic | Caption phrasing; table column order |

Do not mark a document accepted while a blocking finding is open.

## Output format

Findings as a table, then a verdict. Reference by section and ID. One finding per row.

```
| # | Severity | Location | Finding | What would resolve it |
|---|----------|----------|---------|-----------------------|
| 1 | Blocking | §7.5     | ER view carries column types and index definitions — implementation-level content. | Reduce to entities, relationships, and design-bearing attributes; link the schema instead. |
| 2 | Blocking | §9       | Both alternatives are dismissed in a single clause each; neither is credited with doing anything better. | Name the property each alternative wins on, and the goal or constraint that overrides it. |
| 3 | Major    | §4 A-1   | "Traffic will roughly double" has no provenance and no falsification path. | Mark provenance; state the measurement that would confirm or refute it. |
| 4 | Major    | §12      | Observability subsection lists metric names but no questions they answer. | State what an on-call engineer needs to know at 3am and which signal answers it. |
| 5 | Minor    | Figure 4 | Sequence diagram has 11 participants, past the limit of 8. | Split into the happy path and the reconciliation scenario. |
```

**Verdict**: one of `accept`, `accept-with-minors`, `revise`, or `reject-scope` (the document should not exist — see Gate 0), plus one sentence of rationale and the count by severity.

Close with the single most important question the document has not answered. That one line is usually worth more to the author than the whole table.

## Reviewing an updated document

When a revision comes back:

- Check that IDs were retired in place rather than renumbered — renumbering silently invalidates every external reference.
- Check that findings were addressed rather than deleted. A section removed to clear a finding is a finding of its own.
- Do not raise new minor findings on a revision that resolved all blocking ones unless something material changed. Review that expands to fill available attention stops being useful.
