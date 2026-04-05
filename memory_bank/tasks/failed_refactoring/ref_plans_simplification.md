# Task: REF-PLANS Simplification Program

**Scope:** Repository-wide code simplification across `src/` in `REF-PLANS`
**Worktree:** `/home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/REF-PLANS`
**Goal:** Reduce code volume and cognitive load without cutting canonical pipeline functionality.

## Working Notes

- Program runs only in `REF-PLANS`; no new worktrees are created.
- Simplification may break prior internal/external contracts when that materially reduces complexity.
- Canonical flows remain the acceptance surface: sync/download, parse, build indices, build submission, validation/scoring, benchmark essentials.
- Full reviewer runs cover the entire `src/` tree after each major implementation pass.
- Only `P0`, `P1`, and `P2` findings block acceptance; `P3` is tracked separately.

## Review Findings

### Pass 0

- Not run in this implementation handoff (reviewer loop is orchestrator-owned).

### Pass 1

- No P0/P1/P2 correctness findings remain in the first fresh full-pass review over `REF-PLANS` `src/`.
- P3 lint hygiene still red:
  - `I001`: `src/common/config_loader.py`, `src/ingestion/artifact_writer.py`, `src/ingestion/pdf_parser.py`, `src/ingestion/pdf_parser_sidecars.py`, `src/ingestion/pdf_parser_support.py`
  - `E501`: `src/providers/response_parser.py`
  - `F821`: `tests/test_evaluation_validator.py`
- P3 simplification gaps remain:
  - `src/main.py` still contains command-specific business logic and remains ~806 LOC.
  - Major complexity hotspots still exceed conventions targets:
    - `src/answering/solver.py` ~1283 LOC
    - `src/answering/deterministic.py` ~1020 LOC
    - `src/evaluation/validator.py` ~866 LOC
    - `src/answering/page_attribution.py` ~559 LOC
    - `src/ingestion/table_serializer.py` ~511 LOC
- Full `pytest -q` remains blocked only by the existing environment-dependent `uv build` failure in `tests/test_config.py`.

### Pass 2

- No P0/P1/P2 correctness findings remain in the second fresh full-pass review over `REF-PLANS` `src/`.
- P3 simplification gaps still remain, but they are now narrower and more localized:
  - `src/cli/commands.py` ~507 LOC and still mixes multiple CLI domains.
  - `src/answering/solver.py` ~970 LOC and still concentrates orchestration + structured solve + normalization responsibilities.
  - `src/answering/deterministic.py` ~1020 LOC and still carries a broad heuristic surface.
  - `src/evaluation/validator.py` ~866 LOC and still centralizes multiple validation domains.
  - `src/answering/page_attribution.py` ~559 LOC and `src/ingestion/table_serializer.py` ~511 LOC remain slightly above the target size.
- `main.py` is no longer a simplification blocker; reviewer confirmed it is materially improved as a thin dispatcher at ~138 LOC.
- `ruff check src tests` is green; the remaining full-suite failure is still only the existing environment-dependent `uv build` issue in `tests/test_config.py`.

### Pass 3

- No P0/P1/P2 correctness findings remain in the third fresh full-pass review over `REF-PLANS` `src/`.
- P3 conventions gap remains significant:
  - reviewer reports `152` functions/methods in `src/` still missing docstrings, including newly refactored hotspots and older `common/ingestion/submission` modules.
- P3 simplification gap also remains at the aggregate level:
  - wave 3 brought per-file size down and responsibility boundaries into line, but total `src/` size increased (`20606 -> 21185`) and file count increased (`93 -> 120`), so the codebase is cleaner locally but not yet clearly smaller as a whole.
- The only failing full-suite test remains the existing environment-dependent `uv build` packaging test in `tests/test_config.py`.

### Pass 4

- No P0/P1/P2 correctness findings remain in the final fresh full-pass review over `REF-PLANS` `src/`.
- Strict conventions closeout is effectively complete:
  - `src/ingestion/opendataloader_adapter.py` is now below the threshold at `496 LOC`.
  - local AST scan reports `0` missing function/method docstrings in `src/`.
  - `ruff check src tests` is green.
- Remaining P3 is now limited to:
  - aggregate simplification gap: `src/` is still cleaner and more modular but not smaller than the pre-wave baseline;
  - the environment-dependent `uv build` packaging test in `tests/test_config.py`.

## Outcome

**Result:** Review Loop In Progress
**Key findings:**
- `src/main.py` was simplified into a registry-driven dispatcher (single command-definition table + runner map) while preserving canonical command execution paths and telemetry boundaries.
- `src/answering/solver.py` removed a large dead legacy constant block and an unused helper (`_parse_iso_date_parts`), reducing hotspot size without changing active solving flow.
- `src/answering/deterministic.py` removed unused boolean constants/patterns and dead phrase hints.
- `src/answering/service.py` reduced unnecessary compatibility exports; only symbols still required by canonical tests/scripts were retained.
- `src/answering/__init__.py` export wiring was tightened after service export cleanup.
- Fresh full-pass reviewer found no remaining `P0/P1/P2` correctness issues, but the simplification objective is still incomplete because `main.py` and several hotspots remain far above conventions targets.

**Verification performed:**
- `ruff check src/main.py src/answering/solver.py src/answering/deterministic.py src/answering/service.py src/answering/__init__.py` -> passed.
- `python -m compileall src/main.py src/answering` -> passed.
- `pytest -q tests/test_runtime_logging.py tests/test_submission_regressions.py::test_run_build_submission_forwards_env_file_to_service tests/test_submission_regressions.py::test_build_submission_smoke_writes_expected_artifacts tests/test_answering_service_regressions.py::test_answering_service_uses_structured_provider_path_and_logs_boundaries` -> `7 passed`.
- `pytest -q tests/test_retrieval_service_regressions.py tests/test_ingestion_service_regressions.py tests/test_evaluation_benchmark.py tests/test_providers.py` -> `9 passed`.

**Observed simplification delta (this pass):**
- `src/` total LOC reduced from `20775` to `20492` (`-283`).
- `src/answering/solver.py`: `1517 -> 1283` (`-234`).
- `src/answering/deterministic.py`: `1041 -> 1020` (`-21`).
- `src/main.py`: `814 -> 806` (`-8`) with flatter control flow and command registry dispatch.

**Residual risks / next action:**
- Largest hotspots remain above conventions target (`solver.py`, `deterministic.py`, `evaluation/validator.py`, `main.py`, `page_attribution.py`, `table_serializer.py`), so follow-up simplification waves are still needed before this program can be considered complete.
- Next mandatory step: run a second `code-simplifier` wave focused on the remaining hotspots and then re-run an independent full reviewer over all `src/` in `REF-PLANS`.

## Wave 2 Update

### Implementation highlights

- `src/main.py` is now a thin composition layer (`138 LOC`) with command parser and command runners extracted to:
  - `src/cli/parser.py`
  - `src/cli/commands.py`
- `src/answering/solver.py` was decomposed by extracting support utilities into:
  - `src/answering/solver_support.py`
- P3 lint findings from Pass 1 were closed:
  - import-order fixes in `src/common/config_loader.py`, `src/ingestion/artifact_writer.py`, `src/ingestion/pdf_parser.py`, `src/ingestion/pdf_parser_sidecars.py`, `src/ingestion/pdf_parser_support.py`
  - long-line fix in `src/providers/response_parser.py`
  - missing `Path` import fix in `tests/test_evaluation_validator.py`
- Compatibility wrappers remained in `src/main.py` for `tests` monkeypatch contracts:
  - `_run_command`
  - `_run_build_submission`

### Verification

- `ruff check src tests` -> passed.
- `pytest -q tests/test_submission_regressions.py::test_run_build_submission_forwards_env_file_to_service tests/test_submission_regressions.py::test_build_submission_smoke_writes_expected_artifacts tests/test_runtime_logging.py tests/test_answering_service_regressions.py::test_answering_service_uses_structured_provider_path_and_logs_boundaries tests/test_retrieval_service_regressions.py tests/test_ingestion_service_regressions.py tests/test_evaluation_benchmark.py tests/test_providers.py tests/test_evaluation_validator.py` -> `20 passed`.
- `python -m compileall src/main.py src/cli src/answering/solver.py src/answering/solver_support.py src/providers/response_parser.py tests/test_evaluation_validator.py` -> passed.

### Quantitative delta after wave 2

- `src/main.py`: `806 -> 138` (`-668`)
- `src/answering/solver.py`: `1283 -> 970` (`-313`)
- new decomposition modules:
  - `src/cli/parser.py` (`206 LOC`)
  - `src/cli/commands.py` (`507 LOC`)
  - `src/answering/solver_support.py` (`375 LOC`)

### Residual risks

- Largest remaining hotspots:
  - `src/answering/deterministic.py` (`1020 LOC`)
  - `src/evaluation/validator.py` (`866 LOC`)
  - `src/answering/page_attribution.py` (`559 LOC`)
  - `src/ingestion/table_serializer.py` (`511 LOC`)
  - `src/cli/commands.py` (`507 LOC`)
- Next step: another simplification wave focused on `cli/commands.py`, `answering`, `evaluation/validator.py`, `page_attribution.py`, and `table_serializer.py`, then another independent full reviewer pass on whole `src/` in `REF-PLANS`.

## Wave 3 Update

### Implementation highlights

- Final hotspot decomposition completed for the remaining targets from pass 2:
  - CLI dispatch: `src/cli/commands.py` now pure registry/dispatcher (`56 LOC`) with domain runners split into:
    - `src/cli/phase_commands.py`
    - `src/cli/evaluation_commands.py`
  - Solver split into orchestration + focused flow modules:
    - `src/answering/solver.py` (`435 LOC`)
    - `src/answering/solver_structured_flow.py` (`450 LOC`)
    - `src/answering/solver_flows.py` (`214 LOC`)
  - Deterministic heuristics decomposed into domain modules with facade preservation:
    - `src/answering/deterministic.py` (`115 LOC` facade)
    - `src/answering/deterministic_utils.py`
    - `src/answering/deterministic_numbers.py`
    - `src/answering/deterministic_entities.py`
    - `src/answering/deterministic_grounding.py`
    - `src/answering/deterministic_extractors.py`
    - `src/answering/deterministic_types.py`
  - Validator domains split into policy/models/helpers/checks:
    - `src/evaluation/validator.py` (`320 LOC`)
    - `src/evaluation/validator_models.py`
    - `src/evaluation/validator_helpers.py`
    - `src/evaluation/validator_answer_checks.py`
    - `src/evaluation/validator_telemetry_checks.py`
  - Page attribution split by responsibility:
    - `src/answering/page_attribution.py` (`43 LOC` facade)
    - `src/answering/page_attribution_models.py`
    - `src/answering/page_attribution_candidates.py`
    - `src/answering/page_attribution_finalize.py`
    - `src/answering/page_attribution_refs.py`
  - Table serializer split by detection/rows/merge/render:
    - `src/ingestion/table_serializer.py` (`99 LOC` facade)
    - `src/ingestion/table_serializer_models.py`
    - `src/ingestion/table_serializer_rows.py`
    - `src/ingestion/table_serializer_detection.py`
    - `src/ingestion/table_serializer_merge.py`
    - `src/ingestion/table_serializer_render.py`

### Verification

- `python -m compileall src/answering src/evaluation src/ingestion src/cli` -> passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src tests` -> passed.
- Targeted regression suite:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_evaluation_validator.py tests/test_answering_service_regressions.py tests/test_ingestion_table_serializer_smoke.py -q` -> `12 passed`.
- Full suite with one environment-bound packaging test excluded:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q -k "not wheel_build_includes_repo_root_config_yaml"` -> `79 passed, 1 deselected`.
- Full suite without exclusion still has the pre-existing external-network dependency failure:
  - `tests/test_config.py::test_wheel_build_includes_repo_root_config_yaml` fails in this environment because `uv build` cannot resolve `hatchling` from `pypi.org` (DNS/network unavailable).

### Residual risks

- The simplification objective is largely met for hotspot file size and responsibility narrowing, but increased module count means future edits need stronger ownership boundaries to avoid cross-module drift.
- One test remains environment-dependent on live package index access (`uv build` path), so full green in offline sandbox is still not possible without cached/build-system dependencies or network access.

## Wave 4 Update

### Implementation highlights

- Closed the docstring conventions gap across `src/` with a full local AST scan and targeted updates.
  - Missing function/method docstrings: `152 -> 0`.
  - Top reviewer-flagged offenders now covered, including:
    - `src/ingestion/opendataloader_adapter.py`
    - `src/ingestion/ocr_engine.py`
    - `src/submission/sync.py`
    - `src/submission/api_client.py`
    - `src/common/runtime_logging.py`
    - `src/ingestion/corpus_builder.py`
    - `src/answering/page_attribution_candidates.py`
    - `src/answering/solver_structured_flow.py`
    - `src/answering/solver.py`
- Reduced post-wave-3 fragmentation/boilerplate without undoing hotspot decomposition:
  - Removed pass-through wrappers inside `AnsweringService` and routed directly to flow functions in `src/answering/solver.py`.
  - Slimmed public re-export plumbing in `src/answering/deterministic.py`, `src/answering/page_attribution.py`, and `src/ingestion/table_serializer.py`.
  - Merged `deterministic_types` into `deterministic_utils` and removed `src/answering/deterministic_types.py`.
  - Dropped unused compatibility wrapper surface in table serialization:
    - removed `TableSerializer` class from `src/ingestion/table_serializer.py`
    - removed `PageTableAssignments` from `src/ingestion/table_serializer_models.py`
- Aggregate cleanup after docstring insertion pass:
  - `src` Python files: `120 -> 119`
  - `src` Python LOC: `21204 -> 21177`

### Verification

- Docstring compliance scan (AST): `0` missing function/method docstrings in `src/`.
- `python -m compileall src/answering src/evaluation src/ingestion src/submission src/common src/cli` -> passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src tests` -> passed.
- Targeted regressions:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_answering_service_regressions.py tests/test_evaluation_validator.py tests/test_ingestion_table_serializer_smoke.py tests/test_ingestion_service_regressions.py tests/test_submission_regressions.py tests/test_runtime_logging.py -q` -> `23 passed`.
- Broad suite (excluding known network-bound wheel build test):
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q -k "not wheel_build_includes_repo_root_config_yaml"` -> `79 passed, 1 deselected`.

### Residual risks

- Docstring coverage is now complete, but many generated helper docstrings are intentionally compact; a later polish pass can improve narrative quality if needed.
- Full `pytest -q` in this sandbox still depends on external package index access for the wheel-build test path.
- Aggregate LOC/file-count reduction versus the pre-wave baseline is still not achieved, so a future program should focus on deleting behavior and collapsing module surfaces rather than further decomposition.
