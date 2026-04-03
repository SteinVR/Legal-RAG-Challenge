# Migration Plan: `src/evaluation`

## Goal and non-goals

### Goal
- Turn `src/evaluation` into a clearly layered package that separates pure contracts, record loading/normalization, validation, scoring, and benchmark analytics.
- Preserve local comparability of validation/scoring outputs while making the package more modular and less coupled internally.
- Keep evaluation strict because it defines what the rest of the pipeline is judged against.

### Non-goals
- Do not let benchmark convenience helpers blur the contract between validation and scoring.
- Do not move challenge-facing answer semantics out of evaluation unless a broader spec change requires it.
- Do not weaken validation semantics to accommodate upstream drift.

## Current boundary map
- `contracts.py` defines core types but also loads and normalizes JSON/JSONL records.
- `validator.py` is large and owns submission structure checks, telemetry checks, and page-reference validation.
- `scorer.py` depends on validator semantics.
- `dev_benchmark/__init__.py` bundles dataset loading, report generation, comparison, and consistency analysis into one package entrypoint.
- `goldset.py` carries reference-answer-oriented helpers and should stay adjacent to benchmark/report logic, not to validation contracts.

## Target module split
- `contracts.py`: enums, typed records, reports, and pure data models only.
- `loaders.py`: JSON/JSONL record loading, coercion, and normalization utilities.
- `validator.py`: validation only.
- `scorer.py`: scoring only, consuming typed validation-compatible inputs.
- `goldset.py`: keep reference-specific helpers, but remove any generic loading logic that belongs in `loaders.py`.
- `dev_benchmark/loader.py`: benchmark dataset loading.
- `dev_benchmark/report.py`: benchmark run report generation.
- `dev_benchmark/compare.py`: report comparison and consistency analysis.
- `__init__.py`: export only the intentional public evaluation surface.

## Migration steps
1. Move record-loading and normalization helpers out of `contracts.py` into `loaders.py`.
2. Keep `contracts.py` as pure types/enums/report models.
3. Audit `validator.py` and split out any non-validation helpers that belong in loaders or report modules.
4. Keep `scorer.py` consuming typed records and validation-compatible shapes only; remove hidden coupling to loader internals.
5. Split `dev_benchmark/__init__.py` into loader/report/compare modules and leave `__init__.py` as a narrow façade.
6. Update imports across CLI and tests to use the new layered entrypoints.

## Contracts to preserve and change

### Preserve
- `AnswerType`, `PageReference`, validation report shapes, score report shapes, and benchmark report semantics remain stable.
- Local validation and scoring behavior stays comparable to pre-migration outputs.
- Evaluation remains the authoritative place for challenge-facing validation semantics.

### Change
- `contracts.py` stops owning IO behavior.
- Benchmark tooling becomes layered instead of living in one package entrypoint.
- Package-level exports become explicit rather than broad convenience surfaces.

## Logging and typing checklist
- Keep evaluation fully typed because it defines cross-stage acceptance behavior.
- Add or preserve logging around validation/scoring entry and completion when invoked through CLI-facing flows.
- Never pass loosely normalized raw dicts from loaders straight into scorer/validator without typed coercion.

## Verification
- Run evaluation-focused tests for validator, scorer, goldset, and benchmark flows.
- Compare one known validation report and one known score report before and after the refactor.
- Run one benchmark summary/compare smoke path and confirm report shapes remain stable.

## Acceptance criteria
- Contracts, loaders, validator, scorer, and benchmark analytics are separate layers.
- `contracts.py` is pure types only.
- Benchmark/report logic no longer depends on hidden loader side effects inside `contracts.py`.

## Risks and rollback
- The main risk is changing local score or validation semantics unintentionally while extracting loaders. Roll back by comparing serialized reports and restoring the previous loader path only until typed coercion matches the original behavior.
- The second risk is import churn in CLI and tests after splitting `dev_benchmark`. Keep a temporary narrow façade in `dev_benchmark/__init__.py` during migration if needed, then shrink it before completion.
