# Task: W2B Working Journal

**Spec:** [SPEC_W2B.md](../specs/SPEC_W2B.md)

## Working Notes

- Scope is frozen by `../../.apm/worktrees/REF-PLANS/src/indexing/migration-plan.md`.
- The target split is service orchestration plus dedicated chunking, embedding, sparse encoding, persistence, and manifest modules.
- The highest risk is silent drift in chunk-family behavior or artifact compatibility while moving code out of the current monolith.
- Verification should compare chunk counts, artifact presence, manifest shape, and at least one downstream retrieval smoke query.

## Review Findings

- No review findings yet. Start the review loop after implementation lands in `REF-PLANS`.

## Outcome

**Result:** Planned
**Key findings:** Indexing should become modular without changing retrieval-facing artifact and metadata semantics.
**Next action:** Extract contracts and paths first, then move chunking, model loading, persistence, and manifest generation behind typed seams.
