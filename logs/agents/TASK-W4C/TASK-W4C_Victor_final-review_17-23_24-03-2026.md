# [TASK-W4C] [final-review]

## Metadata + Exact Request
- Logged at: 24-03-2026 17:23
- Agent identity: Victor
- Task: TASK-W4C
- Branch / worktree: `.apm/worktrees/TASK-W4C`
- Scope: Final verification review of W4C implementation against architecture/task spec with severity-focused findings.
- Exact user request or delegated objective:
  > "TASK_ID: TASK-W4C ... Review the final W4C state after the latest fixes. Focus on P0/P1/P2 findings and call out any residual risks separately."

## Task Setup
- Context used:
  - `memory_bank/ARCHITECTURE.md`
  - `memory_bank/TASKS.md`
  - `memory_bank/STATE.md`
  - `memory_bank/tasks/TASK-W4C.md`
  - W4C code/test diffs in `src/common`, `src/ingestion`, `src/providers`, `tests/`
- Constraints:
  - Review-only mode; no feature implementation.
  - Memory bank files not edited.
- Planned approach:
  - Verify task intent vs implementation.
  - Run targeted + full test suites.
  - Report only material P0/P1/P2 findings plus residual risks.

## Implementation Log
1. Loaded project navigation + skill instructions (`apm-review`, `apm-report`) and reviewed architecture/task/state docs.
2. Audited W4C change set across parser routing, sidecars, normalizer, corpus assembly, and table serialization.
3. Executed verification commands and assembled severity-ranked findings with line-level evidence.

## Verification
- Checks run:
  - `PYTHONPATH=. .venv/bin/pytest -q tests/test_ingestion_parser_routing.py tests/test_ingestion_sidecars.py tests/test_ingestion_structural_normalizer.py tests/test_ingestion_pdf_parser.py tests/test_ingestion_table_serializer.py tests/test_ingestion_corpus_builder.py tests/test_ingestion_service.py tests/test_codex_provider.py`
  - `PYTHONPATH=. .venv/bin/pytest -q`
  - `PYTHONPATH=. .venv/bin/ruff check src tests`
  - Focused repro for struct-tree detection using PyMuPDF (`xref_get_key` vs `_has_struct_tree`).
- Result:
  - Tests: `221 passed`.
  - Ruff: `All checks passed!`.
  - Repro: `StructTreeRoot` reported as `('xref', '...')` while `_has_struct_tree` returns `False`.

## Issues / Resolutions
- P1: Structural parser branch is not actually integrated into parse execution path; opendataloader sidecars and structural normalization are unreachable in normal flow.
- P1: Tagged fast-path detection is logically broken (`StructTreeRoot` with `xref` is treated as absent).
- P2: Raw sidecar path and artifact completeness checks are inconsistent with W4C interface expectations and structural sidecar requirements.
- P2: Document-level parser provenance remains hardcoded to `pymupdf:native`, even when route metadata indicates non-baseline paths.

## Artifacts
- Files touched:
  - `logs/agents/TASK-W4C/TASK-W4C_Victor_final-review_17-23_24-03-2026.md`
- Reports, plots, logs, or other evidence:
  - Local command outputs from pytest/ruff/repro checks in this session.
- Verification artifacts:
  - Full-suite pass result and struct-tree mismatch reproduction.

## Result / Conclusions (Exact Answer to User)
> TASK-W4C review status: changes required. No P0 blockers found, but there are P1 gaps against W4C acceptance (structural parser branch not executed in production path; tagged fast-path detection bug) plus P2 contract/cache/provenance mismatches. Final gate decision: CHANGES REQUIRED.
