# Task: W3B Working Journal

**Spec:** [SPEC_W3B.md](../specs/SPEC_W3B.md)

## Working Notes

- Scope is frozen by `../../.apm/worktrees/REF-PLANS/src/answering/migration-plan.md`.
- This task preserves schema-first typed answering, two-pass page attribution, and decomposition while breaking `service.py` into owned modules.
- The main risk is answer-semantics drift during extraction of schemas, metadata, deterministic guardrails, and solver logic.
- Verification should cover typed answer smokes, decomposition smokes, page-trace comparison, and one downstream submission question-run.

## Review Findings

- No review findings yet. Start the review loop after implementation lands in `REF-PLANS`.

## Outcome

**Result:** Planned
**Key findings:** Answering should end with a small orchestration service and explicit contracts between solving, attribution, and decomposition.
**Next action:** Extract schemas and metadata first, then move solver and deterministic guardrails before reducing `service.py` to composition only.
