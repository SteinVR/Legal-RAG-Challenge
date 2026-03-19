# [TASK-W2A] [review-fixes]

## Metadata + Exact Request
- Logged at: 19-03-2026 02:06
- Agent identity: Codex
- Task: TASK-W2A
- Branch / worktree: `main`
- Scope: Fix reviewer findings in evaluation/validation flow and lock them with regression tests
- Exact user request or delegated objective:
  > "Возьми агентов и направь их на фиксы этих проблем"

## Task Setup
- Context used:
  - reviewer findings attached in chat
  - `src/evaluation/scorer.py`
  - `src/evaluation/validator.py`
  - `src/main.py`
  - `tests/test_evaluation_validator.py`
  - `tests/test_evaluation_scorer.py`
  - `tests/test_main.py`
- Constraints:
  - do not touch Memory Bank
  - keep fixes scoped to reviewer findings
  - preserve subset scoring semantics while closing raw-validation hole
- Planned approach:
  - tighten validation semantics in scorer/validator/main
  - add direct regression tests for the four findings
  - run targeted and full verification

## Implementation Log
1. Routed the work through agentized implementation/test tracks, then integrated the fixes locally.
2. Extended `SubmissionValidator` with `required_question_ids` so scorer can validate raw answers against a broader question set without requiring full-dataset answer coverage.
3. Updated `score_submission` to accept `validation_question_types`, validate the raw submission, and keep subset scoring intact.
4. Hardened `score-submission` CLI to require both corpus PDFs and question metadata before claiming a corpus-backed validation result.
5. Added regressions for raw extra answers, missing corpus dir, TTFT at exactly 3000 ms, and whitespace-padded `question_id`.

## Verification
- `UV_CACHE_DIR=/tmp/uv-cache uv run --no-sync pytest tests/test_evaluation_validator.py tests/test_evaluation_scorer.py tests/test_main.py`
- `UV_CACHE_DIR=/tmp/uv-cache uv run --no-sync ruff check src/evaluation src/main.py tests/test_evaluation_validator.py tests/test_evaluation_scorer.py tests/test_main.py`
- `UV_CACHE_DIR=/tmp/uv-cache uv run --no-sync pytest`
- Result:
  - targeted regressions passed
  - lint passed
  - full suite passed (`23 passed`)

## Issues / Resolutions
- Raw-validation vs subset-scoring was the main design tension.
- Resolved by separating:
  - `question_types` used to validate raw answers
  - `required_question_ids` used to enforce only the scored subset as mandatory
- This closes the hidden-extra-answer hole without breaking legitimate subset evaluation.

## Artifacts
- Files touched:
  - `src/evaluation/validator.py`
  - `src/evaluation/scorer.py`
  - `src/main.py`
  - `tests/test_evaluation_validator.py`
  - `tests/test_evaluation_scorer.py`
  - `tests/test_main.py`
- Verification artifacts:
  - full `pytest` pass
  - targeted `ruff` pass

## Result / Conclusions (Exact Answer to User)
> Все четыре review findings закрыты: raw submission теперь валидируется корректно, corpus-backed checks через CLI больше не могут “тихо исчезнуть”, TTFT=3000 ms остаётся нейтральным, а `question_id` с окружающими пробелами теперь режется как malformed. Regression tests на эти кейсы добавлены и весь suite проходит.
