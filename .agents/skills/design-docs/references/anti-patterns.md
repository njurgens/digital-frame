# Anti-Pattern Catalog

Named failures with their tell and their fix. Cite by name in reviews so authors and reviewers share vocabulary — "this is the owl" lands faster than three sentences of description.

| Anti-pattern | Tell | Fix |
|---|---|---|
| **Implementation manual** | Describes how to build it; nothing contestable; no alternatives | Surface the real trade-offs, or conclude no doc is needed (Gate 0) |
| **Code smuggling** | Fenced blocks in a non-Mermaid language; schemas labeled "for illustration only" | Move up the abstraction ladder |
| **The owl** | Overview paragraph, then sudden full detail, no bridge | Write the Solution Strategy section properly |
| **Task list in a trench coat** | "Phase 1: create the service. Phase 2: add the endpoint." | Delete — design docs do not decompose work |
| **Strawman alternatives** | Every alternative dismissed in one clause; none wins on anything | Find the alternative a competent skeptic would actually champion |
| **Symmetric hedging** | Pros and cons listed for each option, no choice made | Choose, and state what you accept by choosing |
| **Confident confabulation** | Specific numbers, versions, or behaviors of existing systems with no source | Add provenance markers; downgrade to `[assumed]` or `[unknown]` |
| **Vacuous cross-cutting** | "Security: we will follow industry best practices" | Name what changes about the concern *because of this design* |
| **Diagram sprawl** | Ten diagrams, several restating each other, some purely decorative | One diagram per contested claim; delete the rest |
| **Diagram as sole carrier** | A structural claim appears only inside a Mermaid block | State it in prose; the diagram illustrates, never substitutes |
| **Code-preview class diagram** | Getters, DI wiring, `*Impl`, `*Repository`, framework base classes | Model the domain, not the codebase |
| **Negated non-goals** | "Non-goal: the system should not crash" | Convert to a goal or quality scenario; find the real non-goals |
| **Requirements restatement** | The design section paraphrases the goals section | Delete; add the structural claim that serves each goal |
| **Silent scope creep** | The doc quietly redesigns adjacent systems | Move to non-goals, or split into a parent doc |
| **Fake completeness** | Empty open questions; every section confident | Nothing is fully known at design time — find the three real unknowns |
| **Bullet mush** | 80% bullets, no paragraphs | Reasoning goes in prose; bullets are for parallel items |
| **Premature naming** | Names files, classes, and endpoints that do not exist yet | Name responsibilities; let implementation choose spellings |
| **Length as diligence** | 8,000 words restating context | Cut to the argument; split if genuinely large |
| **Happy path only** | No runtime view shows a timeout, rejection, or partial failure | Add the failure scenario; it usually changes the design |
| **Orphan goal** | A goal appears in §3 and is never mentioned again | Either a decision serves it, or it was not really a goal |

## Banned phrases

Each is a finding when it carries the weight of a claim:

- "industry best practices", "state of the art", "robust and scalable", "seamless", "leverage"
- "as needed", "as appropriate", "where necessary" — used in place of making a decision
- "simply", "just", "obviously", "of course" — these reliably sit on top of the contested part
- "we will consider" or "may be explored" with no open-question ID attached
- "This document describes..." as an opening
- Symmetric hedging: pros and cons for two options, then no choice
