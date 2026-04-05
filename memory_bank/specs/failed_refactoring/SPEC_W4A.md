# SPEC: W4A -- Refactor `src/submission`

**Wave:** 4 | **Depends on:** W1B, W1C, W1D, W2A, W2B, W3A, W3B | **Blocks:** --

## Goal

Turn `src/submission` into an explicit composition layer for artifact reuse, dependency wiring, question execution, trace writing, validation, and packaging while preserving submission-facing outputs and CLI behavior. The detailed migration sequence is frozen in `../../.apm/worktrees/REF-PLANS/src/submission/migration-plan.md`.

## Pipeline

1. Move submission-local result models, reuse checks, runtime dependency wiring, per-question execution, and trace writing into dedicated modules.
2. Reduce `pipeline.py` to high-level orchestration over sync, validation, telemetry, and packaging.
3. Migrate `src/main.py` in lockstep so it depends only on stable stage entrypoints and dispatches submission flows without concrete provider internals.

## Contracts

| Interface | Location | Owner |
|-----------|----------|-------|
| `BuildSubmissionResult` and submission-local orchestration contracts | `src/submission/contracts.py` | W4A |
| Artifact reuse, runtime dependency wiring, question execution, and trace persistence | `src/submission/artifact_reuse.py`, `src/submission/runtime_dependencies.py`, `src/submission/question_runner.py`, `src/submission/trace_writer.py` | W4A |
| Submission-facing artifacts (`submission.json`, `code_archive.zip`, traces) | `src/submission/pipeline.py`, `src/submission/packager.py`, `src/submission/telemetry_packer.py`, `src/submission/submit_gate.py` | W4A |

## Frozen Decisions

| Decision | Value |
|----------|-------|
| Reference plan | `../../.apm/worktrees/REF-PLANS/src/submission/migration-plan.md` |
| Composition boundary | Submission composes refactored stages through stable entrypoints; it does not reimplement stage internals |
| Validation policy | Local validation remains mandatory before packaging is accepted |

## Output

- `src/submission/contracts.py`
- `src/submission/artifact_reuse.py`
- `src/submission/runtime_dependencies.py`
- `src/submission/question_runner.py`
- `src/submission/trace_writer.py`
- Narrowed `src/submission/pipeline.py`
- Updated `src/main.py`

## Definition of Done

- [ ] Submission helper boundaries match the migration plan and `pipeline.py` is orchestration-only
- [ ] `src/main.py` is reduced to dispatch/composition over stable stage entrypoints
- [ ] Submission-facing artifact shapes and validation behavior remain stable
- [ ] End-to-end `build-submission` smoke checks pass with trace and runtime-log inspection
- [ ] All contract interfaces implemented and type-checked
- [ ] Verification passing
- [ ] Results committed to git
