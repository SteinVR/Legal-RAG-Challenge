# SPEC: W1D -- Layer `src/evaluation`

**Wave:** 1 | **Depends on:** W1A | **Blocks:** W4A

## Goal

Turn `src/evaluation` into a layered package that cleanly separates pure contracts, record loading, validation, scoring, and benchmark analytics without changing local validation or scoring semantics. Detailed guidance is frozen in `../../.apm/worktrees/REF-PLANS/src/evaluation/migration-plan.md`.

## Pipeline

1. Keep `contracts.py` as pure types and move JSON/JSONL record loading into `loaders.py`.
2. Split benchmark functionality into dedicated loader, report, and comparison modules.
3. Migrate `src/evaluation/goldset.py` off loader helpers imported from `contracts.py`.
4. Update all submission, CLI, benchmark, tool, and test import sites to use the new layered entrypoints.

## Contracts

| Interface | Location | Owner |
|-----------|----------|-------|
| `AnswerType`, `PageReference`, validation and scoring report models | `src/evaluation/contracts.py` | W1D |
| Record loading and normalization | `src/evaluation/loaders.py` | W1D |
| Goldset reference-answer helpers consuming evaluation loaders | `src/evaluation/goldset.py` | W1D |
| Validation, scoring, benchmark analytics | `src/evaluation/validator.py`, `src/evaluation/scorer.py`, `src/evaluation/dev_benchmark/*` | W1D |

## Frozen Decisions

| Decision | Value |
|----------|-------|
| Reference plan | `../../.apm/worktrees/REF-PLANS/src/evaluation/migration-plan.md` |
| Evaluation role | Evaluation remains the authoritative challenge-facing validation and scoring layer |
| Loader policy | `contracts.py` is pure types only; IO moves into explicit loaders |

## Output

- `src/evaluation/loaders.py`
- Narrowed `src/evaluation/contracts.py`
- Updated `src/evaluation/goldset.py`
- Updated `src/evaluation/dev_benchmark/loader.py`
- Updated `src/evaluation/dev_benchmark/report.py`
- Updated `src/evaluation/dev_benchmark/compare.py`
- Narrowed `src/evaluation/__init__.py`

## Definition of Done

- [ ] `src/evaluation` layering matches the migration plan and `contracts.py` is pure types only
- [ ] `src/evaluation/goldset.py` no longer depends on loader helpers re-exported from `contracts.py`
- [ ] Submission, benchmark, CLI, and tooling import sites stop depending on loader helpers re-exported from `contracts.py`
- [ ] Validation and score report comparisons stay locally compatible with the pre-refactor baseline
- [ ] Benchmark smoke paths and evaluation-focused tests pass
- [ ] All contract interfaces implemented and type-checked
- [ ] Verification passing
- [ ] Results committed to git
