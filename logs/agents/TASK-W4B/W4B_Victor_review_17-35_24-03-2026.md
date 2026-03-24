# W4B review

## Metadata + Exact Request
- Logged at: 24-03-2026 17:35
- Agent identity: Victor
- Task: W4B
- Branch / worktree: wave/TASK-W4B / .apm/worktrees/TASK-W4B
- Scope: Independent quality-gate review for TASK-W4B implementation
- Exact user request or delegated objective:
  > TASK_ID: W4B

## Task Setup
- Context used:
  - `memory_bank/ARCHITECTURE.md`
  - `memory_bank/TASKS.md`
  - `memory_bank/tasks/TASK-W4B.md`
  - W4B diffs in `src/`, `tests/`, `tools/`, and baseline configs
- Constraints:
  - Review-only role (no feature edits)
  - No Memory Bank modifications
- Planned approach:
  - Compare implementation against W4B acceptance criteria
  - Run independent regression suite
  - Produce severity-ranked findings with exact file anchors

## Implementation Log
1. Verified W4B worktree state and reviewed changed modules in answering/provider/pipeline contracts.
2. Ran independent regression slice:
   - `PYTHONPATH=. .venv/bin/pytest tests/test_answering_service.py tests/test_retrieval_service.py tests/test_retrieval_components.py tests/test_retrieval_qdrant_backend.py tests/test_answering_retrieval_integration.py tests/test_submission_pipeline.py tests/test_codex_provider.py tests/test_config.py tests/test_operator_context.py tests/test_build_submission_script.py tests/test_answering_w4b_contracts.py -q`
3. Performed code-level requirement audit against `TASK-W4B.md` and identified contract drift points.

## Verification
- Checks run:
  - Combined W4B-adjacent regression slice (11 test modules)
  - Targeted source review with line anchors in `src/submission/pipeline.py`, `src/answering/service.py`, and `tests/test_submission_pipeline.py`
- Result:
  - Tests: `119 passed`
  - Review verdict: changes required due to requirement/behavior mismatch

## Issues / Resolutions
- Issue 1: Pipeline disables schema-first structured solving for the default Codex provider path.
  - Evidence: `src/submission/pipeline.py:321-323`, `_is_default_codex_provider` at `src/submission/pipeline.py:791-795`.
  - Impact: Typed questions on the default runtime path can bypass provider-backed schema solving and fall back to deterministic-only behavior, which conflicts with W4B target behavior.
- Issue 2: A legacy test explicitly enforces deterministic-only no-credential behavior for typed runs.
  - Evidence: `tests/test_submission_pipeline.py:949-990`.
  - Impact: Test suite codifies behavior that contradicts W4B acceptance criteria and may prevent correcting Issue 1.
- Issue 3: Query metadata extraction is implemented but not wired into retrieval calls.
  - Evidence: metadata extraction in `src/answering/service.py:434-496`, answer path uses `self._retriever.retrieve(question)` directly at `src/answering/service.py:569`, retrieval interface has no metadata input in `src/retrieval/service.py`.
  - Impact: Legal-entity and multi-document signals are not actually exposed to retrieval as soft guidance, leaving part of W4B scope unimplemented.

## Artifacts
- Files touched:
  - `logs/agents/TASK-W4B/W4B_Victor_review_17-35_24-03-2026.md`
- Verification artifacts:
  - Local pytest run (11 modules) in W4B worktree

## Result / Conclusions (Exact Answer to User)
> TASK_ID `W4B` reviewed. Verdict: `CHANGES REQUIRED`. No runtime test regressions were found, but there are requirement-level mismatches: default pipeline path still disables structured typed solving, deterministic-only typed behavior is still asserted by tests, and query metadata extraction is not wired to retrieval guidance.
