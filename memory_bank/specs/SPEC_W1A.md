# SPEC: W1A -- Refactor `src/common`

**Wave:** 1 | **Depends on:** -- | **Blocks:** W1B, W1C, W1D, W2A, W2B, W3A, W3B, W4A

## Goal

Turn `src/common` into the narrow foundation package for shared typed contracts, config loading, minimal path primitives, and runtime logging. The detailed split, sequencing, and verification expectations are defined in `../../.apm/worktrees/REF-PLANS/src/common/migration-plan.md`.

## Pipeline

1. Extract config models and loading into dedicated modules while preserving the canonical `load_app_config` entrypoint.
2. Keep shared schemas and runtime logging as the cross-stage SSOT.
3. Reduce `__init__.py` and remove transitional compatibility exports before the task is accepted.

## Contracts

| Interface | Location | Owner |
|-----------|----------|-------|
| `AppConfig`, `ConfigError`, `load_app_config`, `DEFAULT_CONFIG_PATH` | `src/common/config_models.py`, `src/common/config_loader.py` | W1A |
| `Phase`, `QuestionRecord`, `CanonicalPageRecord`, `PageMapRecord` | `src/common/schemas.py` | W1A |
| Shared runtime logging helpers | `src/common/runtime_logging.py` | W1A |

## Frozen Decisions

| Decision | Value |
|----------|-------|
| Reference plan | `../../.apm/worktrees/REF-PLANS/src/common/migration-plan.md` |
| Package scope | `src/common` owns shared contracts, config loading, path primitives, and runtime logging only |
| Config policy | Repo-root `configs/...` is the canonical default path; packaged fallback behavior is removed during the refactor |

## Output

- `src/common/config_models.py`
- `src/common/config_loader.py`
- `src/common/paths.py`
- `src/common/schemas.py`
- `src/common/runtime_logging.py`
- Narrowed `src/common/__init__.py`

## Definition of Done

- [ ] Module split matches the `src/common` migration plan in `REF-PLANS`
- [ ] Downstream imports target concrete `src/common` modules instead of a broad package facade
- [ ] Config load smoke checks and stage import smoke checks pass from the repo-root config path
- [ ] Shared runtime logging behavior remains intact after the split
- [ ] All contract interfaces implemented and type-checked
- [ ] Verification passing
- [ ] Results committed to git
