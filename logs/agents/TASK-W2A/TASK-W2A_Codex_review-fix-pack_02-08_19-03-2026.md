# [TASK-W2A] [review-fix-pack]

## Metadata + Exact Request
- Logged at: 19-03-2026 02:08
- Agent identity: Codex
- Task: TASK-W2A
- Branch / worktree: `main`
- Scope: Fix reviewer findings in the local evaluation/validation flow
- Exact user request or delegated objective:
  > "Возьми агентов и направь их на фиксы этих проблем"

## Task Setup
- Context used:
  - reviewer findings for `src/evaluation/scorer.py`, `src/evaluation/validator.py`, `src/main.py`
  - existing W2A evaluator/validator implementation
- Constraints:
  - use subagents for the fix pass
  - keep changes scoped to evaluator/validator flow
  - do not update Memory Bank
- Planned approach:
  - delegate implementation and test tracks
  - integrate the live workspace state
  - verify targeted paths, then run full suite

## Implementation Log
1. Spawned specialist subagent work for implementation and test follow-up per user request.
2. Integrated the live workspace state for `src/evaluation/scorer.py`, `src/evaluation/validator.py`, `src/main.py`, and the regression tests.
3. Closed the remaining coverage bug where whitespace `question_id` still counted toward required-question coverage.
4. Re-verified the evaluator/validator path and then the full repository test suite.

## Verification
- `UV_CACHE_DIR=/tmp/uv-cache uv run --no-sync pytest tests/test_evaluation_validator.py tests/test_evaluation_scorer.py tests/test_main.py`
- `UV_CACHE_DIR=/tmp/uv-cache uv run --no-sync ruff check src/evaluation src/main.py tests/test_evaluation_validator.py tests/test_evaluation_scorer.py tests/test_main.py`
- `UV_CACHE_DIR=/tmp/uv-cache uv run --no-sync pytest`
- Result:
  - targeted tests passed (`12 passed`)
  - lint passed
  - full test suite passed (`24 passed`)

## Issues / Resolutions
- `score_submission` previously validated a filtered payload and could hide invalid extra answers.
- Resolved by validating the raw submission and allowing the scorer to receive a broader validation question set while requiring only reference question ids for scoring coverage.
- CLI previously allowed corpus-backed validation to silently degrade when no documents directory was present.
- Resolved by making the documents directory mandatory for `validate-submission` and `score-submission`.
- Whitespace `question_id` values still satisfied coverage checks.
- Resolved by counting only exact, untrimmed IDs toward required coverage.

## Artifacts
- Files touched:
  - `src/evaluation/scorer.py`
  - `src/evaluation/validator.py`
  - `src/main.py`
  - `tests/test_evaluation_scorer.py`
  - `tests/test_evaluation_validator.py`
  - `tests/test_main.py`
- Verification artifacts:
  - full `pytest` pass
  - targeted `ruff` pass

## Result / Conclusions (Exact Answer to User)
> Все четыре reviewer findings закрыты: raw submission теперь валидируется без скрытия extra answers, corpus-backed telemetry checks больше не деградируют молча, `TTFT == 3000` остаётся нейтральным, а `question_id` с обрамляющими пробелами отклоняется и не закрывает coverage.
