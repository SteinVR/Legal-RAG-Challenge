# TASK-W1A review-fixes

## Metadata + Exact Request
- Logged at: 19-03-2026 00:25
- Agent identity: Codex
- Task: TASK-W1A
- Branch / worktree: main
- Scope: Analyze the post-implementation review comments for W1A and fix the ones that are real defects.
- Exact user request or delegated objective:
  > Проанализируй и возьми в исполнения найденные проблемы (если они действительно проблемы)

## Task Setup
- Context used:
  - reviewer findings for `src/common/config.py`, `src/submission/api_client.py`, `src/submission/sync.py`, and `pyproject.toml`
  - current W1A implementation and tests
  - existing W1A activity logs under `logs/agents/TASK-W1A/`
- Constraints:
  - keep changes scoped to real defects only
  - preserve the working uv-based W1A foundation
  - do not update Memory Bank files
- Planned approach:
  - validate each review comment against the actual code path
  - patch only confirmed issues
  - add regression tests for every accepted bug
  - rerun `ruff` and targeted `pytest`

## Implementation Log
1. Verified all four review comments against the implementation and accepted them as real issues:
   - env-file stickiness across repeated loads
   - stale extracted PDFs under `--no-extract`
   - unsafe ZIP extraction in `CompetitionApiClient.download_documents()`
   - default config path failing outside a source checkout
2. Reworked config loading in `src/common/config.py` so `.env` values are read as per-load snapshots instead of mutating global process state, added packaged-config path resolution, and exposed `default_config_path()` for regression coverage.
3. Hardened `src/submission/api_client.py` by replacing raw `extractall()` with validated member-by-member extraction.
4. Fixed `src/submission/sync.py` so `--no-extract` removes stale `pdfs/` before writing the manifest.
5. Added/expanded regression coverage in:
   - `tests/test_config.py`
   - `tests/test_api_client.py`
   - `tests/test_sync.py`
6. Added packaged fallback config at `src/resources/configs/baseline/v001/config.yaml` and included it in wheel builds through `pyproject.toml`.

## Verification
- `env UV_CACHE_DIR=/tmp/uv-cache uv run --no-sync ruff check src tests`
- `env UV_CACHE_DIR=/tmp/uv-cache uv run --no-sync python -m pytest tests/test_config.py tests/test_api_client.py tests/test_main.py tests/test_sync.py`
- Result:
  - `ruff`: passed
  - `pytest`: 14 passed

## Issues / Resolutions
- Issue, blocker, or risk:
  - Previous config loading relied on `load_dotenv(..., override=False)`, which made repeated loads depend on earlier process mutations.
- How it was resolved or what remains open:
  - Switched to explicit `.env` parsing plus per-load env merging; the loaded config now snapshots the API key instead of relying on global process state.
- Issue, blocker, or risk:
  - Direct client extraction path was less safe than the sync path.
- How it was resolved or what remains open:
  - Reused the same containment rule at the client layer, so malformed archive members now fail closed before extraction.
- Issue, blocker, or risk:
  - Console entry point assumed a repo-relative config file.
- How it was resolved or what remains open:
  - Added a packaged fallback config under `src/resources/` and wheel include rules so installed entrypoints can resolve a default YAML config outside the repo.

## Artifacts
- Files touched:
  - `src/common/config.py`
  - `src/common/__init__.py`
  - `src/submission/api_client.py`
  - `src/submission/sync.py`
  - `pyproject.toml`
  - `src/resources/configs/baseline/v001/config.yaml`
  - `tests/test_config.py`
  - `tests/test_api_client.py`
  - `tests/test_sync.py`
  - `logs/agents/TASK-W1A/TASK-W1A_Codex_review-fixes_00-25_19-03-2026.md`
- Reports, plots, logs, or other evidence:
  - this post-review activity log
- Verification artifacts:
  - green `ruff`
  - green `pytest` with 14 tests

## Result / Conclusions (Exact Answer to User)
> Все четыре замечания подтвердились как реальные дефекты. Я их исправил, добавил регрессионные тесты под каждое направление и прогнал локальный gate: `ruff` зелёный, `pytest` зелёный, 14 тестов passed.
