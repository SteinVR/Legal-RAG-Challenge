# TASK-W2C w2c-review-fixes

## Metadata + Exact Request
- Logged at: 20-03-2026 18:24
- Agent identity: Codex
- Task: TASK-W2C
- Branch / worktree: `main` / `/home/xeliaray/Projects/Agentic-RAG-Challenge`
- Scope: Fix three post-review defects in W2C corpus parsing flow.
- Exact user request or delegated objective:
  > "Внеси исправления."

## Task Setup
- Context used:
  - `memory_bank/ARCHITECTURE.md`
  - `memory_bank/TASKS.md`
  - `memory_bank/tasks/TASK-W2C.md`
  - review findings for `service.py`, `pdf_parser.py`, `table_serializer.py`
- Constraints:
  - Do not modify Memory Bank files.
  - Keep fixes scoped to reviewed defects.
  - Use project venv and verify locally.
- Planned approach:
  - Inspect the three failing code paths.
  - Patch the corpus flow, OCR degraded semantics, and table row preservation.
  - Add regression tests for each finding and rerun verification.

## Implementation Log
1. Inspected `src/ingestion/service.py`, `src/ingestion/pdf_parser.py`, `src/ingestion/table_serializer.py`, plus ingestion/CLI tests.
2. Fixed the main parse flow to pass `serialized_tables_by_doc` into `CorpusBuilder`, fixed `serialize_document_tables()` to read parser `cells`, and marked OCR-disabled scan pages as `degraded` when no text is recovered.
3. Added targeted regressions in `tests/test_ingestion_pdf_parser.py`, `tests/test_ingestion_table_serializer.py`, and new end-to-end service coverage in `tests/test_ingestion_service.py`.
4. Used narrow explorer subagents for bug confirmation; closed later simplifier/reviewer agents after timeout because local verification had already completed cleanly.

## Verification
- `./.venv/bin/python -m pytest tests/test_ingestion_pdf_parser.py tests/test_ingestion_table_serializer.py tests/test_ingestion_service.py`
- `./.venv/bin/python -m pytest tests/test_main.py tests/test_ingestion_corpus_builder.py`
- `./.venv/bin/ruff check src/ingestion tests/test_ingestion_pdf_parser.py tests/test_ingestion_table_serializer.py tests/test_ingestion_service.py tests/test_main.py`
- `./.venv/bin/python -m compileall src tests`
- `./.venv/bin/python -m pytest`
- Result:
  - all targeted tests passed
  - full suite passed: `45 passed`
  - `ruff` passed
  - `compileall` passed

## Issues / Resolutions
- Issue: `parse-corpus` built canonical pages without serialized table payloads.
- Resolution: serialized tables are now generated per parsed document before corpus assembly and passed through `serialized_tables_by_doc`.
- Issue: scan pages with OCR disabled could be reported as `parsed` with empty text.
- Resolution: added explicit degraded handling for `SCAN` pages with no recovered text and no OCR engine.
- Issue: `serialize_document_tables()` dropped parser row data by reading nonexistent `rows`.
- Resolution: added row extraction fallback that preserves parser `cells`.

## Artifacts
- Files touched:
  - `src/ingestion/service.py`
  - `src/ingestion/pdf_parser.py`
  - `src/ingestion/table_serializer.py`
  - `tests/test_ingestion_pdf_parser.py`
  - `tests/test_ingestion_table_serializer.py`
  - `tests/test_ingestion_service.py`
- Reports, plots, logs, or other evidence:
  - reviewer findings from user message
  - this activity log
- Verification artifacts:
  - local `pytest`, `ruff`, and `compileall` runs

## Result / Conclusions (Exact Answer to User)
> Исправления внесены: таблицы теперь попадают в canonical corpus, scan-страницы без OCR помечаются как degraded, а row-level table serialization больше не теряет данные parser `cells`. Проверка: `45 passed`, `ruff` green, `compileall` green.
