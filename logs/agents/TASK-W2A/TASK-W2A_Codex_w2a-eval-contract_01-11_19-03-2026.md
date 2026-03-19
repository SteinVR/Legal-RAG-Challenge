# [TASK-W2A] [w2a-eval-contract]

## Metadata + Exact Request
- Logged at: 19-03-2026 01:11
- Agent identity: Codex
- Task: TASK-W2A
- Branch / worktree: `main`
- Scope: Implement local submission validation and scoring for the challenge contract
- Exact user request or delegated objective:
  > "$apm-co-founder Кай, возьми в работу W2A."

## Task Setup
- Context used:
  - `memory_bank/TASKS.md`
  - `memory_bank/STATE.md`
  - `memory_bank/ARCHITECTURE.md`
  - `memory_bank/tasks/TASK-W2A.md`
  - `docs/about_challenge/about_challenge_EVALUATION.md`
  - `docs/about_challenge/about_challenge_API.md`
  - `docs/Initial Roadmap.md`
- Constraints:
  - do not update Memory Bank files without explicit request
  - keep W2A scoped to local evaluator/validator and proxy-friendly free-text workflow
  - respect the documented unanswerable retrieval ambiguity
- Planned approach:
  - add evaluation contracts, validator, scorer, and CLI entrypoints
  - make unanswerable retrieval policy configurable
  - verify with focused tests, then full test suite

## Implementation Log
1. Grounded the task in Memory Bank and starter-kit docs to freeze the actual submission/evaluation contract.
2. Implemented `src/evaluation/contracts.py`, `src/evaluation/validator.py`, and `src/evaluation/scorer.py` with deterministic scoring, grounding F-beta, telemetry factor handling, and TTFT proxy handling.
3. Extended config and CLI with `evaluation.unanswerable_retrieval_policy`, `validate-submission`, and `score-submission`.
4. Added W2A docs artifacts for manual free-text review and explicit ambiguity tracking.
5. Added focused validator/scorer tests and CLI integration coverage, then ran full repository verification.

## Verification
- `UV_CACHE_DIR=/tmp/uv-cache uv run --no-sync pytest tests/test_evaluation_validator.py tests/test_evaluation_scorer.py tests/test_main.py`
- `UV_CACHE_DIR=/tmp/uv-cache uv run --no-sync ruff check src/evaluation src/main.py src/common/config.py tests/test_evaluation_validator.py tests/test_evaluation_scorer.py tests/test_main.py`
- `UV_CACHE_DIR=/tmp/uv-cache uv run --no-sync pytest`
- Result:
  - targeted tests passed
  - lint passed
  - full test suite passed (`20 passed`)

## Issues / Resolutions
- Public docs conflict on unanswerable retrieval (`[]` vs non-empty telemetry requirement).
- Resolved locally with configurable policy and warning-based default (`allow_empty`).
- Public docs do not define the exact TTFT function above 3000 ms.
- Resolved locally with an explicit linear proxy and documentation.

## Artifacts
- Files touched:
  - `src/evaluation/contracts.py`
  - `src/evaluation/validator.py`
  - `src/evaluation/scorer.py`
  - `src/evaluation/__init__.py`
  - `src/main.py`
  - `src/common/config.py`
  - `src/common/__init__.py`
  - `configs/baseline/v001/config.yaml`
  - `src/resources/configs/baseline/v001/config.yaml`
  - `tests/test_evaluation_validator.py`
  - `tests/test_evaluation_scorer.py`
  - `tests/test_main.py`
  - `docs/evaluation/free_text_review_template.md`
  - `docs/evaluation/ambiguities.md`
- Reports, plots, logs, or other evidence:
  - `logs/project/reports/2026-03-19_W2A_evaluation-validation_test-report.md`
- Verification artifacts:
  - full `pytest` pass
  - targeted `ruff` pass

## Result / Conclusions (Exact Answer to User)
> W2A закрыт: в репо теперь есть локальный validator/scorer контур с CLI-командами `validate-submission` и `score-submission`, конфигурируемая policy для unanswerable retrieval, manual/proxy путь для `free_text`, и весь тестовый контур проходит.
