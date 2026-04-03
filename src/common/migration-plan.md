# Migration Plan: `src/common`

## Goal and non-goals

### Goal
- Turn `src/common` into a narrow foundation package that owns only shared typed contracts, config loading, path resolution primitives, and runtime logging.
- Remove "grab bag" behavior so downstream packages depend on explicit modules instead of broad shared helpers.
- Keep `common` as the single source of truth for cross-stage types that must remain stable across ingestion, indexing, retrieval, answering, submission, and evaluation.

### Non-goals
- Do not move stage-specific business logic into `common`.
- Do not let `common` own challenge-specific scoring, retrieval heuristics, or provider behavior.
- Do not preserve convenience exports that weaken package boundaries unless they are required temporarily during migration.

## Current boundary map
- `config.py` mixes config models, environment overrides, default config path resolution, and filesystem/path policy.
- `schemas.py` is the cross-pipeline schema spine and already carries compatibility-sensitive models.
- `runtime_logging.py` is the correct shared home for structured runtime logging and should remain shared infrastructure.
- `__init__.py` is currently too broad for a foundation package and should not stay a façade for unrelated helpers.

## Target module split
- `config_models.py`: typed settings models only.
- `config_loader.py`: YAML loading, env overrides, validation, and `load_app_config`.
- `paths.py`: shared path primitives only when they are truly cross-stage and not submission-owned.
- `schemas.py`: cross-pipeline Pydantic models and enums only.
- `runtime_logging.py`: shared logging context, logger factory, and structured event helpers.
- `compat.py`: temporary alias/re-export layer used only during migration; remove by the end of the refactor if no longer needed.
- `__init__.py`: export only `AppConfig`, `ConfigError`, `load_app_config`, `Phase`, and the minimum schema/logging symbols used across the repo.

## Migration steps
1. Extract config model classes from `config.py` into `config_models.py` without changing field names or validation behavior.
2. Move YAML loading, env override application, and fail-fast validation into `config_loader.py`; keep one temporary import bridge from `config.py`.
3. Remove default packaged config fallback behavior and make config resolution require an explicit repo-root `configs/...` target.
4. Review `schemas.py` and separate true SSOT models from compatibility aliases; keep aliases only where needed to preserve CLI/submission behavior during the migration window.
5. Keep `runtime_logging.py` as the shared logging module, but standardize event naming conventions used by every stage plan.
6. Shrink `__init__.py` to intentional exports only and update downstream imports to target concrete modules instead of package-level wildcard surfaces.
7. Delete `compat.py` and any transitional re-exports before marking the refactor complete.

## Contracts to preserve and change

### Preserve
- `AppConfig`, `ConfigError`, `load_app_config`, and `DEFAULT_CONFIG_PATH` remain the canonical config entrypoints until `main.py` is migrated.
- Shared schemas such as `Phase`, `QuestionRecord`, `CanonicalPageRecord`, `PageMapRecord`, and parse manifest models remain typed SSOTs.
- `runtime_logging.py` remains the only shared logging utility layer.

### Change
- `DEFAULT_CONFIG_PATH` must point to repo-root `configs/...`; missing config is an error, not a fallback to `src/resources`.
- Shared path helpers must be explicit and minimal; package-specific artifact layout should live with the owning package.
- Broad package-level exports are removed unless they are required for temporary migration safety.

## Logging and typing checklist
- Keep full typing on every config loader boundary and schema model.
- Ensure every shared helper returns typed objects, not raw `dict[str, Any]`, unless the target contract is intentionally untyped.
- Document the standard logging event fields required across stages: `stage`, `run_id`, `phase`, `duration_ms`, and stage-specific identifiers.
- Do not add business-stage logging policies here; keep only shared infrastructure and naming conventions.

## Verification
- Run config load smoke tests against the canonical repo-root config path and confirm failure when the file is missing.
- Run import smoke checks for every top-level stage package to confirm no broken imports after shrinking `__init__.py`.
- Run the existing config-focused test coverage and inspect runtime logs from one CLI command to confirm logging context is unchanged.

## Acceptance criteria
- `src/common` is reduced to foundation-only responsibilities with no stage-specific logic.
- Repo-root `configs/...` is the only config source of truth and packaged fallback behavior is gone.
- Downstream packages import concrete modules instead of relying on broad shared façades.

## Risks and rollback
- The main risk is breaking the schema spine used across every stage. Migrate `schemas.py` conservatively and keep temporary aliases only where they preserve active CLI/submission behavior.
- The second risk is path-resolution drift during the config move. Roll back by restoring the previous loader module only if CLI execution is blocked; do not restore fallback behavior as a permanent solution.
