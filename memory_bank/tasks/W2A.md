# Task: W2A Working Journal

**Spec:** [SPEC_W2A.md](../specs/SPEC_W2A.md)

## Working Notes

- Scope is frozen by `../../.apm/worktrees/REF-PLANS/src/ingestion/migration-plan.md`.
- This task keeps ingestion as the canonical upstream stage while separating orchestration, parser workers, and artifact persistence.
- The main risk is changing canonical corpus shape while extracting document-level helpers and artifact writing.
- Verification should include `parse-corpus` smoke checks, artifact inspection, and runtime-log inspection for both success and failure paths.

## Review Findings

- No review findings yet. Start the review loop after implementation lands in `REF-PLANS`.

## Outcome

**Result:** Planned
**Key findings:** Ingestion must preserve canonical corpus and sidecar contracts while narrowing its service and package export surfaces.
**Next action:** Introduce ingestion-local contracts, extract `artifact_writer.py`, and reduce `pdf_parser.py` to document-level orchestration only.
