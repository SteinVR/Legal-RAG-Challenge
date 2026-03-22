# TASK-W3D w3d-quality-gate-fixes

## Metadata + Exact Request
- Logged at: 22-03-2026 13:26
- Agent identity: Leo
- Task: TASK-W3D
- Branch / worktree: TASK-W3D / /home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/TASK-W3D
- Scope: Apply mandatory quality-gate fixes and add regression coverage.
- Exact user request or delegated objective:
  > Fix quality-gate findings: wall-clock telemetry timing, corpus reuse integrity checks with stale PDF invalidation, secret exclusion in code archive, policy propagation for unanswerable retrieval mode; add regression tests and return verified handoff.

## Task Setup
- Context used:
  - reviewer findings from quality-gate message
  - `src/submission/pipeline.py`, `src/submission/submit_gate.py`, `src/submission/packager.py`
  - `tests/test_submission_pipeline.py`
- Constraints:
  - Stay in TASK-W3D worktree and preserve SDET contract intent.
  - Do not revert unrelated changes.
- Planned approach:
  - Implement each mandatory fix directly in submission runtime modules.
  - Add targeted regression tests for all four findings.
  - Re-run targeted suite and full suite.

## Implementation Log
1. Updated telemetry timing semantics in pipeline:
   - per-question wall-clock measurement from question receipt using `time.perf_counter()`.
   - non-streaming telemetry now sets `ttft_ms == total_time_ms` from elapsed time.
2. Strengthened corpus reuse validation:
   - `_corpus_artifacts_complete(...)` now verifies per-PDF SHA256 and page_count against manifest records.
   - `_ensure_corpus(...)` now forces `overwrite=True` on re-parse when integrity check fails to avoid stale internal skip logic.
3. Added secret exclusion in archive packager:
   - `.env` and `.env.*` are excluded from `code_archive.zip`.
4. Propagated unanswerable policy through runtime:
   - `BuildSubmissionService` uses `config.evaluation.unanswerable_retrieval_policy` for both local validation and `SubmitGate`.
   - `SubmitGate` now accepts and applies configurable unanswerable retrieval policy.
5. Added regression tests:
   - wall-clock timing semantics.
   - corpus cache invalidation after in-place PDF content change.
   - `.env` / `.env.*` exclusion from code archive.
   - policy propagation for configured `require_non_empty` mode (both submit-gate level and build-submission path).
   - adjusted restart assertion to avoid brittle full-payload equality now that timing is real-time.

## Verification
- Checks run:
  - `PYTHONPATH=. ./.venv/bin/ruff check src/submission/pipeline.py src/submission/submit_gate.py src/submission/packager.py tests/test_submission_pipeline.py`
  - `PYTHONPATH=. ./.venv/bin/pytest -q tests/test_submission_pipeline.py`
  - `PYTHONPATH=. ./.venv/bin/pytest -q tests/test_main.py tests/test_submission_pipeline.py`
  - `PYTHONPATH=. ./.venv/bin/pytest -q`
- Result:
  - `ruff`: passed.
  - `tests/test_submission_pipeline.py`: 12 passed.
  - `tests/test_main.py + tests/test_submission_pipeline.py`: 27 passed.
  - Full suite: 178 passed.

## Issues / Resolutions
- Issue: Existing restart test compared full payload equality, which became invalid under real elapsed timing.
- Resolution: Updated assertion to compare stable semantic fields while allowing timing variance.

## Artifacts
- Files touched:
  - src/submission/pipeline.py
  - src/submission/submit_gate.py
  - src/submission/packager.py
  - tests/test_submission_pipeline.py
- Reports, plots, logs, or other evidence:
  - This activity log.
- Verification artifacts:
  - Green test runs listed above.

## Result / Conclusions (Exact Answer to User)
> All mandatory quality-gate findings were fixed in TASK-W3D, regression coverage was added for each finding, and the updated suite is fully green.
