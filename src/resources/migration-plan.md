# Migration Plan: `src/resources`

## Goal and non-goals

### Goal
- Remove `src/resources` as a configuration source of truth.
- Move baseline config ownership to repo-root `configs/` and align all loaders, packaging rules, and documentation to that single location.
- Preserve `src/resources` only for true package artifacts that must ship with the Python package; if no such artifacts remain, the directory becomes removable.

### Non-goals
- Do not introduce dual-source config support.
- Do not keep any fallback from repo-root `configs/` to `src/resources`.
- Do not treat missing config as recoverable; this migration follows fail-fast behavior.

## Current boundary map
- `src/resources/configs/baseline/v001/config.yaml` is the packaged baseline config artifact.
- `common.config` currently knows how to resolve packaged config copies and fallback behavior.
- Packaging and archive composition may still implicitly depend on the config being under `src/`.

## Target module split
- `src/resources/` should own only non-config package assets, if any remain after migration.
- Repo-root `configs/baseline/v001/config.yaml` becomes the sole baseline config location.
- If `src/resources` becomes empty after the move, delete it in the implementation phase rather than preserving a dead package.

## Migration steps
1. Move canonical config authority to repo-root `configs/baseline/v001/config.yaml`.
2. Update config loading so all default path resolution points only to `configs/...`.
3. Remove any packaged fallback path resolution, importlib resource lookup, or archive assumptions that require config under `src/resources`.
4. Update packaging rules so `configs/` is intentionally included when needed and `src/resources/configs/...` is no longer referenced.
5. Audit docs, scripts, tests, and operator references to remove any mention of packaged fallback config behavior.
6. Delete `src/resources/configs/...` once all call sites and tests are aligned.

## Contracts to preserve and change

### Preserve
- The effective config schema and values remain unchanged during the move unless another module plan explicitly changes them.
- CLI users still pass `--config` or rely on the canonical default path; they do not need to know about packaging internals.

### Change
- Repo-root `configs/...` is the only supported default location.
- Missing config now fails immediately with a clear error.
- `src/resources` no longer participates in configuration discovery.

## Logging and typing checklist
- Config path resolution logs must include the resolved path and fail-fast reason on error.
- No raw fallback warnings; resolution is either valid or fatal.
- Any helper kept in `src/resources` must remain data-only, not executable logic.

## Verification
- Run config-loading smoke checks with the repo-root config present.
- Run the same smoke checks with the repo-root config removed and confirm the command fails immediately.
- Inspect archive composition logic to confirm config inclusion/exclusion matches the new single-source policy.

## Acceptance criteria
- There is exactly one baseline config source of truth: repo-root `configs/...`.
- No code path references `src/resources/configs/...`.
- Any remaining `src/resources` content is package-asset-only and explicitly justified.

## Risks and rollback
- The main risk is hidden packaging or test references to the old path. Roll back by restoring the file location temporarily only if it is needed to unblock active verification, then complete the call-site cleanup before reattempting removal.
