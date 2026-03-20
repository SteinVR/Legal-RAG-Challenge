# TASK-W2C w2c-clean-rework

## Metadata + Exact Request
- Logged at: 20-03-2026 23:06
- Agent identity: Codex
- Task: TASK-W2C
- Branch / worktree: `main` / `/home/xeliaray/Projects/Agentic-RAG-Challenge`
- Scope: Clean rework of W2C ingestion contracts after repeated review findings.
- Exact user request or delegated objective:
  > "Implement the plan."

## Task Setup
- Context used:
  - `memory_bank/ARCHITECTURE.md`
  - `memory_bank/TASKS.md`
  - `memory_bank/tasks/TASK-W2C.md`
  - post-review findings for table provenance, OCR lifecycle, OCR-backed tables, and metadata recomputation
- Constraints:
  - Do not modify Memory Bank files.
  - Use the project `.venv`.
  - Fix root causes, not only review-line symptoms.
- Planned approach:
  - Refactor table serialization to preserve source-page provenance per serialized row.
  - Upgrade OCR path to structured page output and shared run-level engine lifecycle.
  - Rewire parser/service/builder and add regressions that specifically cover the previously missed invariants.

## Implementation Log
1. Extended ingestion contracts so serialized table rows carry physical page provenance and corpus emission filters table blocks by their true source page.
2. Reworked OCR path around structured `OcrPageResult`/`OcrTableExtraction`, including OCR-derived text blocks/table candidates and first-page metadata recomputation from resolved text.
3. Moved OCR engine construction to `CorpusParseService` so one engine is reused across the full `parse-corpus` run.
4. Added regressions for merged multi-page tables, OCR-backed table emission, shared OCR engine reuse, and first-page metadata recovery from OCR.
5. Used explorer subagents for sidecar audits; closed them after local implementation and verification completed.

## Verification
- `./.venv/bin/python -m pytest tests/test_ingestion_service.py tests/test_ingestion_pdf_parser.py tests/test_ingestion_corpus_builder.py tests/test_ingestion_table_serializer.py`
- `./.venv/bin/python -m pytest tests/test_main.py tests/test_config.py`
- `./.venv/bin/python -m pytest`
- `./.venv/bin/ruff check src/common/schemas.py src/ingestion/__init__.py src/ingestion/ocr_engine.py src/ingestion/pdf_parser.py src/ingestion/service.py src/ingestion/table_serializer.py src/ingestion/corpus_builder.py tests/test_ingestion_pdf_parser.py tests/test_ingestion_table_serializer.py tests/test_ingestion_corpus_builder.py tests/test_ingestion_service.py tests/test_main.py tests/test_config.py`
- `./.venv/bin/python -m compileall src tests`
- Result:
  - targeted ingestion regressions passed
  - full suite passed: `49 passed`
  - targeted `ruff` passed
  - `compileall` passed

## Issues / Resolutions
- Issue: prior fixes addressed symptoms but left broken data contracts.
- Resolution: elevated W2C invariants into schemas and parser/service wiring so exact page attribution and OCR-structured recovery are first-class.
- Issue: service/parser/test files experienced conflicting local rewrites during the rework.
- Resolution: reconciled the final file state locally and re-verified from a clean full-suite run.

## Artifacts
- Files touched:
  - `src/common/schemas.py`
  - `src/ingestion/__init__.py`
  - `src/ingestion/ocr_engine.py`
  - `src/ingestion/pdf_parser.py`
  - `src/ingestion/service.py`
  - `src/ingestion/table_serializer.py`
  - `src/ingestion/corpus_builder.py`
  - `tests/test_ingestion_pdf_parser.py`
  - `tests/test_ingestion_table_serializer.py`
  - `tests/test_ingestion_corpus_builder.py`
  - `tests/test_ingestion_service.py`
- Reports, plots, logs, or other evidence:
  - prior review findings supplied by the user
  - this activity log
- Verification artifacts:
  - local `pytest`, `ruff`, and `compileall` runs

## Result / Conclusions (Exact Answer to User)
> W2C was reworked at the contract level: merged table rows now preserve physical page attribution, OCR is reused across the whole corpus run, OCR-selected pages can emit table candidates into the canonical corpus, and first-page metadata is recomputed from OCR-resolved text. Verification: `49 passed`, targeted `ruff` green, `compileall` green.
