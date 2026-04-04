# Task: W1D Working Journal

**Spec:** [SPEC_W1D.md](../specs/SPEC_W1D.md)

## Working Notes

- Scope is frozen by `../../.apm/worktrees/REF-PLANS/src/evaluation/migration-plan.md`.
- This task must keep local validation and scoring semantics stable while removing loader IO from `contracts.py`.
- Import churn matters here because submission, CLI, benchmark tooling, and operator helpers currently reach into evaluation loaders through broad entrypoints.
- Verification should compare one known validation output and one known score report before and after the split.

## Review Findings

- No review findings yet. Start the review loop after implementation lands in `REF-PLANS`.

## Outcome

**Result:** Planned
**Key findings:** Evaluation is the acceptance oracle for the rest of the pipeline, so this refactor must preserve report semantics while improving internal layering.
**Next action:** Extract `loaders.py`, split benchmark helpers, and migrate every import site that still depends on loader behavior inside `contracts.py`.
