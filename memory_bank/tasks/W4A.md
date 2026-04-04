# Task: W4A Working Journal

**Spec:** [SPEC_W4A.md](../specs/SPEC_W4A.md)

## Working Notes

- Scope is frozen by `../../.apm/worktrees/REF-PLANS/src/submission/migration-plan.md`.
- Submission is the final composition layer for the refactor and should consume stable stage entrypoints rather than reimplementing stage internals.
- The highest risk is breaking end-to-end orchestration while extracting artifact reuse, runtime dependency wiring, question execution, and trace writing out of `pipeline.py`.
- Verification must include `build-submission`, artifact inspection, trace inspection, validation output review, and runtime-log review.

## Review Findings

- No review findings yet. Start the review loop after implementation lands in `REF-PLANS`.

## Outcome

**Result:** Planned
**Key findings:** Submission is the integration checkpoint for the whole refactor, and `src/main.py` must shrink alongside it to keep the composition boundary clean.
**Next action:** Extract submission-local helper modules, rewire `main.py` to stable entrypoints, and validate the full submission build flow before acceptance.
