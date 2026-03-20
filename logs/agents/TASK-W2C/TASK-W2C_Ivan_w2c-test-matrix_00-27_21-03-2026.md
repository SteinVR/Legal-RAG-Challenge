# [TASK-W2C] [w2c-test-matrix]

## Metadata + Exact Request
- Logged at: 21-03-2026 00:27
- Agent identity: Ivan
- Task: TASK-W2C
- Branch / worktree: current workspace `/home/xeliaray/Projects/Agentic-RAG-Challenge`
- Scope: Expand W2C tests in `tests/` only around runtime invariants and prior review regressions.
- Exact user request or delegated objective:
  > Expand and update tests so they cover invariants rather than isolated examples: parser matrix, metadata recompute, headerless and blank-leading-header tables, no row loss, conservative merges, page attribution, per-page table_ids, complete artifact-set skip logic, subset doc-id handling, one OCR engine per run, and CLI smoke. Do not modify src/ files.

## Task Setup
- Context used:
  - `memory_bank/tasks/TASK-W2C.md`
  - Current W2C parser/serializer/builder/service runtime contract
  - Existing W2C tests and prior review-history regressions
- Constraints:
  - Modify `tests/` only
  - Treat tests as specification
  - Report material defects instead of weakening expectations
- Planned approach:
  - Audit existing W2C tests for invariant gaps
  - Expand parser/table/service/CLI coverage with stable deterministic fixtures
  - Run targeted W2C verification and full `pytest`

## Implementation Log
1. Audited existing W2C tests and identified missing coverage for parser routing matrix, headerless no-row-loss guarantees, subset artifact completeness, and CLI rebuild/skip flows.
2. Expanded `tests/test_ingestion_pdf_parser.py` with a routing/status/source-mode matrix, suspicious-without-OCR degradation, and document-status aggregation checks.
3. Expanded `tests/test_ingestion_table_serializer.py`, `tests/test_ingestion_corpus_builder.py`, `tests/test_ingestion_service.py`, and `tests/test_main.py` with no-row-loss, conservative merge, per-page table-id, subset completeness, and CLI skip/rebuild regressions.

## Verification
- `.venv/bin/pytest -q tests/test_ingestion_pdf_parser.py tests/test_ingestion_table_serializer.py tests/test_ingestion_corpus_builder.py tests/test_ingestion_service.py tests/test_main.py`
- `.venv/bin/pytest -q`
- `.venv/bin/python -m compileall tests`
- Result:
  - Targeted W2C sweep passed: `43 passed`
  - Full suite passed: `72 passed`
  - `compileall` passed

## Issues / Resolutions
- Initial parser matrix fixtures accidentally exercised `suspicious` routing instead of `native_clean` because the synthetic text was still under the effective threshold after PDF rendering.
- Resolved by tightening the fixture config and using routing-appropriate text lengths rather than weakening the invariant.

## Artifacts
- Files touched:
  - `tests/test_ingestion_pdf_parser.py`
  - `tests/test_ingestion_table_serializer.py`
  - `tests/test_ingestion_corpus_builder.py`
  - `tests/test_ingestion_service.py`
  - `tests/test_main.py`
- Reports, plots, logs, or other evidence:
  - This activity log
- Verification artifacts:
  - Local `pytest` and `compileall` runs listed above

## Result / Conclusions (Exact Answer to User)
> TASK-W2C test surface was expanded from example-driven checks to invariant-driven coverage across parser routing/provenance, table serialization, corpus emission, artifact completeness, subset parsing, and CLI smoke. All targeted W2C tests and the full repository pytest suite are green.
