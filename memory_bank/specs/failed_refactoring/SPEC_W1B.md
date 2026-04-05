# SPEC: W1B -- Move Config Authority Out of `src/resources`

**Wave:** 1 | **Depends on:** W1A | **Blocks:** W2A, W4A

## Goal

Make repo-root `configs/...` the only supported config source of truth and remove `src/resources` from configuration discovery. The authoritative migration sequence is defined in `../../.apm/worktrees/REF-PLANS/src/resources/migration-plan.md`.

## Pipeline

1. Move baseline config ownership to repo-root `configs/baseline/v001/config.yaml`.
2. Remove packaged fallback lookup and any archive or packaging assumptions that still require config under `src/resources`.
3. Delete legacy `src/resources/configs/...` content once all code paths and docs use the repo-root location.

## Contracts

| Interface | Location | Owner |
|-----------|----------|-------|
| Baseline config path | `configs/baseline/v001/config.yaml` | W1B |
| Config path resolution policy | `src/common/config_loader.py` | W1A + W1B |
| Package asset boundary for `src/resources` | `src/resources/` | W1B |

## Frozen Decisions

| Decision | Value |
|----------|-------|
| Reference plan | `../../.apm/worktrees/REF-PLANS/src/resources/migration-plan.md` |
| Config SSOT | Repo-root `configs/...` only |
| Missing config behavior | Fail fast with a clear error; no fallback to `src/resources` |

## Output

- `configs/baseline/v001/config.yaml`
- Updated config resolution code paths
- Updated packaging and documentation references
- Removed or reduced `src/resources/configs/...`

## Definition of Done

- [ ] Repo-root `configs/...` is the only supported default config location
- [ ] No code path references `src/resources/configs/...` for config discovery
- [ ] Packaging, CLI, tests, and docs are aligned with the single-source config policy
- [ ] Missing-config smoke checks fail immediately with a clear error
- [ ] All contract interfaces implemented and type-checked
- [ ] Verification passing
- [ ] Results committed to git
