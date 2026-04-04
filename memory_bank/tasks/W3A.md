# Task: W3A Working Journal

**Spec:** [SPEC_W3A.md](../specs/SPEC_W3A.md)

## Working Notes

- Scope is frozen by `../../.apm/worktrees/REF-PLANS/src/retrieval/migration-plan.md`.
- Retrieval must keep hybrid search, reranking, compression, and page grounding behavior stable while making budgets and fusion explicit modules.
- Hidden ranking drift is the main risk, especially when splitting backend access from rank fusion and rerank orchestration.
- Verification should inspect candidate ordering, grouped references, and the mandatory non-debug retrieval logs from a normal run.

## Review Findings

- No review findings yet. Start the review loop after implementation lands in `REF-PLANS`.

## Outcome

**Result:** Planned
**Key findings:** Retrieval is the main downstream consumer of the refactored index artifacts and the upstream producer of page-grounded answering inputs.
**Next action:** Establish retrieval-local contracts, extract backend and fusion layers, then narrow budget policy and grounding behind typed seams.
