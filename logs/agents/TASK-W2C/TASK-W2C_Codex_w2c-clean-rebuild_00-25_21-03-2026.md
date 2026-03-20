# [TASK-W2C] [w2c-clean-rebuild]

## Metadata + Exact Request
- Logged at: 21-03-2026 00:25
- Agent identity: Codex
- Task: TASK-W2C
- Branch / worktree: current workspace `/home/xeliaray/Projects/Agentic-RAG-Challenge`
- Scope: Rebuild W2C around one schema-level SSOT, repair parser/serializer/builder/service contracts, and expand invariant-based tests.
- Exact user request or delegated objective:
  > Implement the W2C clean rebuild plan, update `memory_bank/tasks/TASK-W2C.md`, establish a single source of truth, add real invariant-based tests, and run final verification / quality gate.

## Task Setup
- Context used:
  - `memory_bank/ARCHITECTURE.md`
  - `memory_bank/TASKS.md`
  - `memory_bank/tasks/TASK-W2C.md`
  - current ingestion implementation and failing review findings
- Constraints:
  - do not revert unrelated dirty-worktree changes
  - update Memory Bank only where explicitly requested
  - keep W2C page attribution exact and artifact completeness explicit
- Planned approach:
  - fix task-level SSOT first
  - move parser/runtime contract to `src/common/schemas.py`
  - rebuild parser, serializer, builder, and service around that contract
  - expand tests from example regressions to invariant classes
  - verify with targeted and full checks

## Implementation Log
1. Updated `memory_bank/tasks/TASK-W2C.md` with SSOT rules, unified runtime contract, invariants, delegation, and acceptance criteria.
2. Extended `src/common/schemas.py` to own the parsed document/page/table contracts, added compatibility aliases, and made `ParsedPage`/`RawTableRecord` the ingestion SSOT.
3. Reworked `src/ingestion/ocr_engine.py`, `src/ingestion/page_triage.py`, and `src/ingestion/pdf_parser.py` so final page resolution, provenance, metadata, and parse status are determined in one parser path.
4. Rebuilt `src/ingestion/table_serializer.py` around explicit header semantics, headerless safety, positional blank headers, conservative merge rules, and row-level provenance.
5. Simplified `src/ingestion/corpus_builder.py` to consume parsed pages directly and compute `table_ids` from emitted blocks only.
6. Hardened `src/ingestion/service.py` with artifact-completeness-aware skip logic, debug artifact regeneration, and one OCR engine per run.
7. Expanded W2C tests across parser, serializer, builder, service, and CLI, including debug rebuild and `--doc-id` subset rebuild behavior.

## Verification
- `.venv/bin/pytest -q tests/test_ingestion_pdf_parser.py tests/test_ingestion_table_serializer.py tests/test_ingestion_corpus_builder.py tests/test_ingestion_service.py tests/test_main.py`
- `.venv/bin/pytest -q`
- `.venv/bin/python -m compileall src tests`
- `.venv/bin/ruff check src/common/schemas.py src/ingestion src/main.py tests/test_ingestion_pdf_parser.py tests/test_ingestion_table_serializer.py tests/test_ingestion_corpus_builder.py tests/test_ingestion_service.py tests/test_main.py`
- `git diff --check -- memory_bank/tasks/TASK-W2C.md src/common/schemas.py src/ingestion src/main.py tests/test_ingestion_pdf_parser.py tests/test_ingestion_table_serializer.py tests/test_ingestion_corpus_builder.py tests/test_ingestion_service.py tests/test_main.py`
- Result:
  - targeted W2C tests passed
  - full `pytest` passed (`57 passed`)
  - `compileall` passed
  - targeted `ruff` passed
  - diff hygiene check passed

## Issues / Resolutions
- Issue: W2C had drift between schema models and parser-local dataclasses.
  - Resolution: parser/runtime state now flows through `src/common/schemas.py`; local compatibility is kept only at the schema boundary.
- Issue: table serialization corrupted headerless and blank-leading-header tables.
  - Resolution: conservative header inference and generic `column_n` fallback removed first-row loss and header shift.
- Issue: skip-path claimed success with missing debug outputs.
  - Resolution: service now validates the full artifact set and rebuilds when any declared output is missing.
- Issue: test fixtures still used old field names.
  - Resolution: compatibility aliases were added in schema validators so tests and transitional call-sites can map old names safely.

## Artifacts
- Files touched:
  - `memory_bank/tasks/TASK-W2C.md`
  - `src/common/schemas.py`
  - `src/ingestion/__init__.py`
  - `src/ingestion/corpus_builder.py`
  - `src/ingestion/ocr_engine.py`
  - `src/ingestion/page_triage.py`
  - `src/ingestion/pdf_parser.py`
  - `src/ingestion/service.py`
  - `src/ingestion/table_serializer.py`
  - `tests/test_ingestion_corpus_builder.py`
  - `tests/test_ingestion_pdf_parser.py`
  - `tests/test_ingestion_service.py`
  - `tests/test_ingestion_table_serializer.py`
  - `tests/test_main.py`
- Reports, plots, logs, or other evidence:
  - this activity log
- Verification artifacts:
  - local pytest / compileall / ruff / diff-check runs described above

## Result / Conclusions (Exact Answer to User)
> W2C was rebuilt around a schema-level single source of truth, parser provenance was centralized, table canonicalization was hardened, artifact completeness is now explicit, and the expanded W2C regression suite is green.
