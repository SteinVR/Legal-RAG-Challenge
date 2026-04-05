# Task: W2A Working Journal

**Spec:** [SPEC_W2A.md](../specs/SPEC_W2A.md)

## Working Notes

- Scope is frozen by `../../.apm/worktrees/REF-PLANS/src/ingestion/migration-plan.md`.
- Split ingestion-local contracts into `src/ingestion/contracts.py` and artifact persistence into `src/ingestion/artifact_writer.py`.
- Kept `CorpusParseService` as the entrypoint while making `service.py` orchestration-only and moving raw sidecar/corpus writes behind the writer boundary.
- Narrowed `pdf_parser.py` to a thin compatibility wrapper over the document-level parser support helpers.
- Added stage-boundary logging for parse start, document boundaries, sidecar writes, corpus build, and completion, plus failure logs on sidecar and corpus writes.
- Preserved canonical corpus, page map, manifest, and raw sidecar contracts.
- Preserved the `src.ingestion.pdf_parser.triage_page` monkeypatch seam by re-exporting/injecting triage selection through the wrapper path.
- Verification used `py_compile`, focused pytest coverage, and two `parse-corpus` smoke runs with artifact and runtime-log inspection.
- Final review fix: deferred `successful_documents` bookkeeping until after table serialization, raw sidecar writing, and structural normalization complete so manifest success/failure state stays consistent.
- Added a regression test that forces a post-parse failure and asserts the manifest contains only the failed record for that document.
- Updated `memory_bank/ARCHITECTURE.md` and `memory_bank/component_design.md` so the W2A split and current config entrypoints are reflected consistently.

## Review Findings

- P1: document success was recorded too early and could conflict with a later post-parse failure. Resolved by moving success bookkeeping to the end of the post-parse block.
- P2: architecture/design docs still described the older ingestion/config boundary. Resolved by updating the Memory Bank architecture and design-layer docs.

## Outcome

**Result:** Done
**Key findings:** Ingestion now has explicit local contracts, a dedicated artifact writer boundary, consistent manifest bookkeeping, and refreshed architecture/design docs.
**Next action:** Move to the next wave task after the review loop and integration gate.
