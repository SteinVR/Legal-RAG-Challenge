# TASK-W4D w4d-src-gap-audit

## Metadata + Exact Request
- Logged at: 24-03-2026 21:54
- Agent identity: apm-engineer
- Task: TASK-W4D
- Branch / worktree: wave/TASK-W4D / /home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/TASK-W4D
- Scope: Audit `src/` only for remaining W4D integration gaps (W4C metadata, W4B query metadata + budgets, W4A telemetry compatibility), implement concrete fix if found.
- Exact user request or delegated objective:
  > TASK_ID: TASK-W4D
  > Worktree path: /home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/TASK-W4D
  > Clarification: W4D has been integrated directly against finished W4A/W4B/W4C contracts and the targeted W4D suite is currently green. Please inspect the current implementation in src/ only for remaining W4D integration gaps against the accepted plan (W4C structural metadata, W4B query_metadata soft boosts and question-class budgets, W4A page-trace-compatible telemetry). If you find a concrete gap, implement the fix in this worktree and list changed files; otherwise report no src gaps.

## Task Setup
- Context used:
  - `src/indexing/service.py`
  - `src/retrieval/hybrid_search.py`
  - `src/retrieval/service.py`
  - `src/answering/service.py`
  - `src/submission/pipeline.py`
  - `src/submission/telemetry_packer.py`
  - `src/common/config.py`
  - `src/common/schemas.py`
- Constraints:
  - Stay inside TASK-W4D worktree.
  - Inspect and modify only `src/`.
  - Keep compatibility with current W4D targeted suite.
- Planned approach:
  - Audit three contract groups (W4C, W4B, W4A).
  - If any concrete implementation gap is found, apply minimal additive fix.
  - Re-run targeted verification to confirm no regressions.

## Implementation Log
1. Audited W4C structural metadata flow in indexing:
   - Confirmed `parser_provenance`, `heading_path`, `source_block_ids` are present in `IndexChunk.payload()` and persisted through `page_parent_map`.
2. Audited W4B flow:
   - Confirmed `QueryMetadata` extraction and forwarding from answering -> retrieval.
   - Confirmed soft-boost logic in `hybrid_search` with non-hard filtering.
   - Found concrete gap: retrieval diagnostics had `question_class` but did not expose effective budgets used by question-class routing.
3. Implemented minimal fix in `src/retrieval/service.py`:
   - Added budget telemetry fields under `diagnostics["prefilter_usage"]`:
     - `candidate_budget`, `rerank_budget`, `evidence_budget`, `budget_source`.
   - Added small hardening for metadata sequence length parsing to avoid `TypeError` on malformed metadata payloads.

## Verification
- `PYTHONPATH=. .venv/bin/ruff check src/retrieval/service.py`
  - Result: passed.
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_retrieval_service.py tests/test_submission_pipeline.py`
  - Result: 37 passed, 1 warning.
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_config.py tests/test_indexing_service.py tests/test_retrieval_service.py tests/test_retrieval_qdrant_backend.py tests/test_answering_retrieval_integration.py tests/test_submission_pipeline.py`
  - Result: 75 passed, 1 warning.

## Issues / Resolutions
- Issue: Missing budget-level diagnostics in W4B question-class routing visibility.
- Resolution: Added additive budget diagnostics in retrieval output while preserving existing schema keys and test behavior.
- Residual: Existing `requests` dependency warning remains (unrelated to this change).

## Artifacts
- Files touched:
  - `src/retrieval/service.py`
- Reports, plots, logs, or other evidence:
  - This activity log.
- Verification artifacts:
  - Passing targeted and full W4D targeted test suite outputs (commands listed above).

## Result / Conclusions (Exact Answer to User)
> Inspected `src/` against W4A/W4B/W4C integration goals. Found one concrete remaining gap in W4B diagnostics visibility (question-class budgets not exposed). Implemented a minimal fix in `src/retrieval/service.py` to include applied candidate/rerank/evidence budgets and budget source in `diagnostics["prefilter_usage"]`, plus defensive metadata-length handling. Re-verified: `ruff` clean, retrieval/submission tests green, and full W4D targeted suite remains green (75 passed).
