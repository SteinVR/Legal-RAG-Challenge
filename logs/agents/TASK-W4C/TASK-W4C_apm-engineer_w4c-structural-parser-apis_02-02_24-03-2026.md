# TASK-W4C structural-parser-apis

## Metadata + Exact Request
- Logged at: 24-03-2026 02:02
- Agent identity: apm-engineer
- Task: TASK-W4C
- Branch / worktree: `wave/TASK-W4C` / `/home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/TASK-W4C`
- Scope: Implement `src/` + `config` APIs required by the pre-written red test suite for W4C.
- Exact user request or delegated objective:
  > TASK_ID: TASK-W4C. Own src/ and config implementation only. The red suite already exists in tests/ for W4C parser routing, raw sidecars, structural normalization, semantic table blocks, corpus builder/service enrichments, and structured provider support. Implement against those tests in the task worktree without editing Memory Bank files.

## Task Setup
- Context used:
  - `memory_bank/ARCHITECTURE.md`
  - `memory_bank/tasks/TASK-W4C.md`
  - Red tests under `tests/test_ingestion_*` and `tests/test_codex_provider.py`
- Constraints:
  - No Memory Bank edits.
  - Implement only `src/` + `configs/`.
  - Preserve backward compatibility of existing ingestion/provider flows.
- Planned approach:
  - Add missing W4C schemas and ingestion modules first.
  - Update table serialization, corpus builder, and parse service to consume new contracts.
  - Add structured provider path and config toggles.
  - Verify via targeted pytest + ruff.

## Implementation Log
1. Added W4C schema contracts:
   - Parser route enum
   - Raw sidecar node/table/sidecar models
   - Structural normalized block model
   - Semantic table block model
   - Additive fields on `TableBlock`, `ParsedDocument`, `CanonicalPageRecord`
2. Added ingestion W4C modules:
   - `parser_routing.py` (route resolution and homogeneous batching)
   - `sidecars.py` (read/write JSON sidecars)
   - `structural_normalizer.py` (heading path carry-over, role tagging, text cleanup, caption linkage)
3. Updated ingestion pipeline:
   - `table_serializer.py` supports semantic blocks with kill switch, keeping row-level serialization authoritative.
   - `corpus_builder.py` accepts structural blocks and projects parser provenance / heading path / block roles / source block ids into canonical pages.
   - `service.py` writes raw parse sidecars to `corpus/raw_parse/{parser}/` and passes normalized structural blocks into builder.
4. Updated providers:
   - Added `CodexStructuredOutputProvider` with schema-bound `/responses` payload.
   - Exported structured provider in `src/providers/__init__.py`.
5. Updated config:
   - Added W4C ingestion toggles and defaults in `src/common/config.py`.
   - Synced baseline config mirrors in `configs/baseline/v001/config.yaml` and `src/resources/configs/baseline/v001/config.yaml`.
6. Updated navigation docs for changed stable directories:
   - `src/common/about_directory.md`
   - `src/ingestion/about_directory.md`
   - `src/providers/about_directory.md`

## Verification
- Ran:
  - `PYTHONPATH=. .venv/bin/pytest -q tests/test_ingestion_parser_routing.py tests/test_ingestion_sidecars.py tests/test_ingestion_structural_normalizer.py tests/test_ingestion_table_serializer.py tests/test_ingestion_corpus_builder.py tests/test_ingestion_service.py tests/test_codex_provider.py`
  - `PYTHONPATH=. .venv/bin/pytest -q tests/test_config.py tests/test_codex_provider.py tests/test_ingestion_parser_routing.py tests/test_ingestion_sidecars.py tests/test_ingestion_structural_normalizer.py tests/test_ingestion_table_serializer.py tests/test_ingestion_corpus_builder.py tests/test_ingestion_service.py`
  - `PYTHONPATH=. .venv/bin/ruff check src/common/config.py src/common/schemas.py src/ingestion src/providers`
- Result:
  - Target test slice green (`50 passed`).
  - Ruff clean for changed source areas.

## Issues / Resolutions
- Observed unexpected concurrent edits in `src/ingestion/ocr_engine.py` and `src/providers/base.py` while implementing.
- Did not revert them; preserved as-is and proceeded because they are non-destructive and aligned with W4C API direction.

## Artifacts
- Files touched (implementation scope):
  - `src/common/config.py`
  - `src/common/schemas.py`
  - `src/common/about_directory.md`
  - `src/ingestion/parser_routing.py`
  - `src/ingestion/sidecars.py`
  - `src/ingestion/structural_normalizer.py`
  - `src/ingestion/table_serializer.py`
  - `src/ingestion/corpus_builder.py`
  - `src/ingestion/service.py`
  - `src/ingestion/pdf_parser.py`
  - `src/ingestion/__init__.py`
  - `src/ingestion/about_directory.md`
  - `src/providers/codex_provider.py`
  - `src/providers/__init__.py`
  - `src/providers/about_directory.md`
  - `configs/baseline/v001/config.yaml`
  - `src/resources/configs/baseline/v001/config.yaml`
- Verification artifacts:
  - Pytest and Ruff command outputs in terminal session.

## Result / Conclusions (Exact Answer to User)
> TASK-W4C src/config implementation is complete against the red suite. New parser routing, sidecar persistence, structural normalization, semantic-table serialization gating, canonical enrichments, and structured provider APIs are implemented and verified on the targeted ingestion/provider/config test slice.
