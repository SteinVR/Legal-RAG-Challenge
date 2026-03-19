# [TASK-W2A] [review-fixes]

## Metadata + Exact Request
- Logged at: 19-03-2026 02:08
- Agent identity: Codex
- Task: TASK-W2A
- Branch / worktree: `main`
- Scope: fix reviewer findings in evaluator/validator flow and lock them with regression tests
- Exact user request or delegated objective:
  > "Возьми агентов и направь их на фиксы этих проблем"

## Task Setup
- Context used:
  - reviewer findings for `src/evaluation/scorer.py`, `src/evaluation/validator.py`, `src/main.py`
  - current W2A implementation and existing tests
- Constraints:
  - use subagents for this pass
  - keep scope inside evaluator/validator and associated tests
  - do not update Memory Bank files
- Planned approach:
  - delegate source and test tracks
  - integrate the fixes locally
  - run targeted and full verification

## Implementation Log
1. Spawned subagent tracks for source fixes and regression tests.
2. Tightened `score_submission` semantics so validation runs against the raw submission and can expose extra invalid answers while still scoring only the reference subset.
3. Tightened corpus-backed CLI validation by requiring a documents directory for `validate-submission` and `score-submission`.
4. Kept `TTFT == 3000 ms` in the neutral bucket and enforced exact `question_id` matching without surrounding-whitespace normalization.
5. Added regression coverage for extra-answer validation, TTFT boundary behavior, whitespace/duplicate `question_id`, and missing-documents CLI guards.

## Verification
- `UV_CACHE_DIR=/tmp/uv-cache uv run --no-sync pytest tests/test_evaluation_validator.py tests/test_evaluation_scorer.py tests/test_main.py`
- `UV_CACHE_DIR=/tmp/uv-cache uv run --no-sync ruff check src/evaluation src/main.py tests/test_evaluation_validator.py tests/test_evaluation_scorer.py tests/test_main.py`
- `UV_CACHE_DIR=/tmp/uv-cache uv run --no-sync pytest`
- Result:
  - targeted tests passed (`12 passed`)
  - lint passed
  - full suite passed (`24 passed`)

## Issues / Resolutions
- Review exposed that validation and scoring were too loosely coupled, which could hide raw-submission invalidity during scoring.
- Resolved by validating against the raw payload and separating validation question scope from scoring reference scope.
- Review also exposed a gap where corpus-backed telemetry checks could be silently disabled from the CLI.
- Resolved by making the documents directory mandatory for CLI validation/scoring.

## Artifacts
- Files touched:
  - `src/evaluation/scorer.py`
  - `src/evaluation/validator.py`
  - `src/main.py`
  - `tests/test_evaluation_validator.py`
  - `tests/test_evaluation_scorer.py`
  - `tests/test_main.py`
- Verification artifacts:
  - targeted `pytest` pass
  - targeted `ruff` pass
  - full `pytest` pass

## Result / Conclusions (Exact Answer to User)
> Исправил все четыре замечания reviewer'а, прогнал regression-тесты и полный test suite. Сейчас evaluator/validator не скрывает extra invalid answers, не притворяется corpus-validated без `documents_dir`, держит `TTFT == 3000 ms` в нейтральном bucket и отвергает `question_id` с окружающими пробелами.
