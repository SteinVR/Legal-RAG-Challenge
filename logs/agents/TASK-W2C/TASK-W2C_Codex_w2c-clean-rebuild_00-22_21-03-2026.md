# [TASK-W2C] [w2c-clean-rebuild]

## Metadata + Exact Request
- Logged at: 21-03-2026 00:22
- Agent identity: Codex
- Task: TASK-W2C
- Branch / worktree: main workspace `/home/xeliaray/Projects/Agentic-RAG-Challenge`
- Scope: Rebuild W2C around a unified ingestion contract, strict artifact completeness, and invariant-based tests.
- Exact user request or delegated objective:
  > Implement the approved W2C clean-rebuild plan, fix the architecture drift, update the task SSOT, add exhaustive tests, and finish with a verified quality gate.

## Task Setup
- Context used:
  - `memory_bank/ARCHITECTURE.md`
  - `memory_bank/TASKS.md`
  - `memory_bank/tasks/TASK-W2C.md`
  - current `src/ingestion/` implementation and W2C tests
- Constraints:
  - Do not revert unrelated dirty worktree changes.
  - Update Memory Bank only where explicitly requested.
  - Use `.venv` for verification.
- Planned approach:
  - Lock the contract in `TASK-W2C.md` and `src/common/schemas.py`.
  - Rebuild parser/serializer/builder/service around that contract.
  - Rewrite W2C tests as invariant-based specifications.
  - Re-verify with targeted and full checks.

## Implementation Log
1. Updated `memory_bank/tasks/TASK-W2C.md` with unified runtime contract, invariants, acceptance criteria, delegation boundaries, and quality-gate sequence.
2. Promoted `src/common/schemas.py` to the ingestion SSOT by extending `RawTableRecord` and `ParsedPage`, plus compatibility aliases for old table field names during the transition.
3. Reworked `src/ingestion/pdf_parser.py`, `src/ingestion/ocr_engine.py`, `src/ingestion/page_triage.py`, `src/ingestion/table_serializer.py`, `src/ingestion/corpus_builder.py`, `src/ingestion/service.py`, and `src/ingestion/__init__.py` to remove contract drift and enforce exact provenance plus artifact completeness.
4. Rewrote W2C tests under `tests/` around parser/source-mode, table-header behavior, row provenance, artifact completeness, and CLI surface.

## Verification
- `.venv/bin/pytest -q tests/test_ingestion_page_triage.py tests/test_ingestion_pdf_parser.py tests/test_ingestion_table_serializer.py tests/test_ingestion_corpus_builder.py tests/test_ingestion_service.py`
- `.venv/bin/pytest -q tests/test_main.py`
- `.venv/bin/pytest -q`
- `.venv/bin/python -m compileall src tests`
- `.venv/bin/ruff check src/common/schemas.py src/ingestion src/main.py tests/test_ingestion_page_triage.py tests/test_ingestion_pdf_parser.py tests/test_ingestion_table_serializer.py tests/test_ingestion_corpus_builder.py tests/test_ingestion_service.py tests/test_main.py`
- Result: all checks passed.

## Issues / Resolutions
- Issue: W2C logic was split across parser-local dataclasses, OCR helpers, and serializer heuristics, which kept reintroducing review regressions.
- Resolution: centralized runtime data in schema models, moved final source/provenance decisions into parser, and made serializer/header detection conservative.
- Issue: existing tests were tied to the old drifted contract.
- Resolution: rewrote W2C test files as invariant-driven specs and kept compatibility aliases only in schemas.
- Residual risk: true `SourceMode.HYBRID` is intentionally rare because current parser resolves to one final text source rather than merging fragments; if hybrid text assembly is introduced later, it needs explicit tests.

## Artifacts
- Files touched:
  - `memory_bank/tasks/TASK-W2C.md`
  - `src/common/schemas.py`
  - `src/ingestion/__init__.py`
  - `src/ingestion/page_triage.py`
  - `src/ingestion/ocr_engine.py`
  - `src/ingestion/pdf_parser.py`
  - `src/ingestion/table_serializer.py`
  - `src/ingestion/corpus_builder.py`
  - `src/ingestion/service.py`
  - `tests/test_ingestion_page_triage.py`
  - `tests/test_ingestion_pdf_parser.py`
  - `tests/test_ingestion_table_serializer.py`
  - `tests/test_ingestion_corpus_builder.py`
  - `tests/test_ingestion_service.py`
- Reports, plots, logs, or other evidence:
  - this activity log
- Verification artifacts:
  - green `pytest`, `compileall`, and targeted `ruff` runs from the current workspace

## Result / Conclusions (Exact Answer to User)
> W2C was rebuilt around a single ingestion contract, strict artifact completeness, and invariant-based tests. The full local verification suite is green.
