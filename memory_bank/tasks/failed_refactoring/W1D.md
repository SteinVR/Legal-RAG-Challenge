# Task: W1D Working Journal

**Spec:** [SPEC_W1D.md](../specs/SPEC_W1D.md)

## Working Notes

- Scope is frozen by `../../.apm/worktrees/REF-PLANS/src/evaluation/migration-plan.md`.
- This task must keep local validation and scoring semantics stable while removing loader IO from `contracts.py`.
- Import churn matters here because submission, CLI, benchmark tooling, and operator helpers currently reach into evaluation loaders through broad entrypoints.
- Verification should compare one known validation output and one known score report before and after the split.
- The goldset support split needed a follow-up fix: `GoldShardBundle` now lives in `src/evaluation/goldset_models.py`, so `goldset_support.py` no longer imports `goldset.py` and the cycle is gone.
- Implemented loader separation in `src/evaluation/loaders.py` and routed all evaluation consumers to the layered entrypoints.
- Split benchmark handling into `dev_benchmark/loader.py`, `dev_benchmark/report.py`, and `dev_benchmark/compare.py`.
- Moved gold-set validation and shared helpers into `src/evaluation/goldset_support.py`, with shared bundle models in `src/evaluation/goldset_models.py`, so the goldset code stays modular and cycle-free.
- Updated package façades to stop exporting loader helpers from `contracts.py`-adjacent surfaces.
- Re-ran verification after the review fixes: ruff, before/after compatibility evidence, a goldset smoke, targeted pytest, package import smoke, `py_compile`, and `git diff --check`.

## Verification

- `./.venv/bin/ruff check .apm/worktrees/REF-PLANS/src/evaluation .apm/worktrees/REF-PLANS/src/submission .apm/worktrees/REF-PLANS/src/main.py .apm/worktrees/REF-PLANS/tests/test_evaluation_benchmark.py .apm/worktrees/REF-PLANS/tests/test_submission_regressions.py .apm/worktrees/REF-PLANS/tools/goldset_workflow.py .apm/worktrees/REF-PLANS/tools/operator_context.py` -> `All checks passed!`
- Compatibility smoke with a temporary `HEAD` snapshot for `before_eval.contracts|validator|scorer` and the current `src.evaluation.*` modules -> `VALIDATION_EQUAL True`, `VALIDATION_HASH_BEFORE = VALIDATION_HASH_AFTER = a662775cc913b9acb54aded9444a1c4813573f1243bc4b4740a7ee0422f624b8`, `SCORE_EQUAL True`, `SCORE_HASH_BEFORE = SCORE_HASH_AFTER = dbedc64dd4917560a62f289b039abe6963755d53e00bdfa47a13fd904d98156d`.
- Goldset smoke in the same script using `split_questions_stratified` + `merge_reviewed_shards` on a synthetic 4-question bundle -> `GOLDSET_SHARDS 2`, `GOLDSET_MERGED_REFERENCES 4`, `GOLDSET_MERGED_ASSISTANT_SCORES 2`.
- `./.venv/bin/python -m py_compile src/evaluation/goldset.py src/evaluation/goldset_support.py src/evaluation/goldset_models.py src/evaluation/goldset_constants.py src/evaluation/dev_benchmark/loader.py src/evaluation/dev_benchmark/report.py src/evaluation/dev_benchmark/compare.py src/evaluation/dev_benchmark/__init__.py src/evaluation/__init__.py src/submission/pipeline.py tests/test_evaluation_benchmark.py tests/test_submission_regressions.py tools/goldset_workflow.py tools/operator_context.py` -> passed.
- `./.venv/bin/pytest -q tests/test_evaluation_benchmark.py tests/test_evaluation_scorer.py tests/test_evaluation_validator.py tests/test_submission_regressions.py` -> `13 passed`.
- `git diff --check` -> clean.

## Review Findings

- P1 circular-import finding resolved by moving `GoldShardBundle` into `src/evaluation/goldset_models.py` and keeping `goldset_support.py` free of runtime imports back into `goldset.py`.
- P1 ruff findings resolved. The changed scope is now ruff-clean.
- P2 compatibility-evidence finding resolved. The journal now includes reproducible before/after validation and score report comparisons, plus a goldset smoke run.

## Outcome

**Result:** Ready for closure
**Key findings:** Evaluation now has explicit loader, benchmark, and gold-set helper layers while `contracts.py` remains type-only.
**Next action:** Await integration/closure; the W1D review findings are now addressed.
