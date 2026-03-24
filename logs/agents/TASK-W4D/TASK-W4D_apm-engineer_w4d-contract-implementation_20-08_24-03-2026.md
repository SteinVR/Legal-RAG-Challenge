# TASK-W4D w4d-contract-implementation

## Metadata + Exact Request
- Logged at: 24-03-2026 20:08
- Agent identity: apm-engineer
- Task: TASK-W4D
- Branch / worktree: wave/TASK-W4D / /home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/TASK-W4D
- Scope: Implement W4D runtime changes to satisfy pre-written failing contracts in config, indexing, retrieval, and telemetry.
- Exact user request or delegated objective:
  > The W4D tests are already written in this worktree and currently fail on five contracts: config indexing/retrieval settings, token-aware microchunk splitting, enabled chunk family filtering, parent-page expansion in retrieval, and additive retrieval diagnostics in telemetry. Implement the task to satisfy those tests and keep changes scoped to W4D. Do not update memory_bank. Do not introduce a new permanent QuestionRecord/query-metadata contract for W4B-dependent behavior yet. Run the relevant tests and report changed files plus verification results.

## Task Setup
- Context used:
- `memory_bank/ARCHITECTURE.md` constraints already reflected in task spec and existing code paths.
- Existing red-state from TDD tests in `tests/test_config.py`, `tests/test_indexing_service.py`, `tests/test_retrieval_service.py`, and `tests/test_submission_pipeline.py`.
- Constraints:
- No `memory_bank` edits.
- No new permanent `QuestionRecord` metadata contract for W4B dependencies.
- Keep implementation scoped to W4D contracts only.
- Planned approach:
- Add config models for indexing/retrieval settings.
- Wire indexing chunk builder for family toggles and token-aware microchunking.
- Add retrieval parent-page expansion and diagnostics.
- Extend telemetry payload with optional diagnostics and wire retrieval settings into pipeline.

## Implementation Log
1. Reproduced red-state (5 failing contracts) on target test suite.
2. Implemented `IndexingSettings` and `RetrievalSettings` in `src/common/config.py` and attached them to `AppConfig`.
3. Updated indexing flow:
- `HybridIndexService.build_indices()` now passes token and family settings into `build_index_chunks()`.
- `build_index_chunks()` now supports `enabled_chunk_families`, `token_chunk_size`, and `token_chunk_overlap`.
- `_split_microchunks()` switched to token-budget + overlap logic with optional token counter.
4. Updated retrieval flow:
- Added `diagnostics` to `RetrievalResult`.
- Added `parent_page_expansion_enabled` and `parent_page_expansion_limit` to `RetrievalService`.
- Added post-rerank parent-page expansion before compression.
- Added selected-evidence reconciliation so expansion survives compressor outputs keyed by `chunk_id`.
- Added diagnostics: chunk family participation, rerank effect, parent-page expansion effect.
5. Updated telemetry and orchestration:
- `build_answer_telemetry()` now emits `retrieval.diagnostics` when present.
- `BuildSubmissionService._run_qa_pipeline()` now constructs `RetrievalService` from `config.retrieval`.

## Verification
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_config.py tests/test_indexing_service.py tests/test_retrieval_service.py tests/test_submission_pipeline.py`
- Result: 63 passed, 1 warning.
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_config.py tests/test_indexing_service.py tests/test_retrieval_service.py tests/test_retrieval_components.py tests/test_retrieval_qdrant_backend.py tests/test_answering_retrieval_integration.py tests/test_submission_pipeline.py`
- Result: 74 passed, 1 warning.
- `PYTHONPATH=. .venv/bin/ruff check src tests`
- Result: All checks passed.

## Issues / Resolutions
- Issue: Parent-page expansion initially did not survive compressor stubs that returned original payloads.
- Resolution: Added post-compression reconciliation by `chunk_id` to apply expanded `page_span`/metadata to selected evidence.
- Issue: Parent-page metadata was initially attached too broadly and broke existing metadata contract tests.
- Resolution: Attach `parent_page_numbers` metadata only for chunks actually expanded.

## Artifacts
- Files touched:
- src/common/config.py
- src/indexing/service.py
- src/retrieval/service.py
- src/submission/pipeline.py
- src/submission/telemetry_packer.py
- tests/test_config.py
- tests/test_indexing_service.py
- tests/test_retrieval_service.py
- tests/test_submission_pipeline.py
- Reports, plots, logs, or other evidence:
- Test command outputs from the verification section.
- Verification artifacts:
- `ruff` and `pytest` runs listed above.

## Result / Conclusions (Exact Answer to User)
> TASK-W4D implementation is complete for the five requested failing contracts, scoped to W4D, without memory bank edits and without introducing a new permanent W4B query-metadata contract. Target and extended relevant test suites pass.
