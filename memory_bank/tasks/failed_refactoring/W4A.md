# Task: W4A Working Journal

**Spec:** [SPEC_W4A.md](../specs/SPEC_W4A.md)

## Working Notes

- Scope is frozen by `../../.apm/worktrees/REF-PLANS/src/submission/migration-plan.md`.
- Submission is the final composition layer for the refactor and should consume stable stage entrypoints rather than reimplementing stage internals.
- The highest risk is breaking end-to-end orchestration while extracting artifact reuse, runtime dependency wiring, question execution, and trace writing out of `pipeline.py`.
- Verification must include `build-submission`, artifact inspection, trace inspection, validation output review, and runtime-log review.
- Implementation now lives in dedicated submission seams: `artifact_reuse.py`, `runtime_dependencies.py`, `question_runner.py`, and `trace_writer.py`.
- `src/main.py` now dispatches build-submission through `src.submission` root exports and no longer wires provider internals directly.
- Smoke verification covers artifact creation, trace manifest creation, and runtime-log inspection for the required `submission.*` events.
- W4A review follow-up restored `--env-file` propagation into submission provider construction and added regression coverage for the provider factory receiving a custom env-file path.
- W4A review follow-up also replaced the smoke shortcut with a real `build-submission` run that uses the actual `artifact_reuse.check_submission_artifact_reuse` and `build_submission_runtime_dependencies` seams.
- Manual smoke evidence was written under `/tmp/w4a-smoke-refpl/` so the artifact and runtime-log paths could be inspected directly.

## Review Findings

- P1 resolved: `env_file` is forwarded from `BuildSubmissionService` into submission runtime provider creation, and `tests/test_submission_regressions.py` now proves the provider factory receives the custom `tmp_path / "custom.env"` path.
- P2 resolved: a real smoke run completed without monkeypatching the core submission seams. It produced `submission.json`, `trace_manifest.json`, a trace file under `traces/`, and a JSONL runtime log with the expected reuse and build events.
- Review loop completed with no remaining P0/P1/P2 findings after the final verification pass.

## Outcome

**Result:** Completed
**Key findings:** Submission orchestration now delegates artifact reuse, runtime wiring, question execution, and trace writing to explicit modules; `pipeline.py` is reduced to orchestration and validation/packaging ordering. The review fixes are closed: env-file propagation is restored and the smoke evidence now comes from a real submission build path.
**Verification:** `python -m py_compile` on touched submission/test files passed. `uv run pytest -q /home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/REF-PLANS/tests/test_submission_regressions.py` passed (`6 passed`). `uv run ruff check /home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/REF-PLANS/src/submission /home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/REF-PLANS/src/main.py /home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/REF-PLANS/tests/test_submission_regressions.py` passed. Manual smoke command: `uv run python - <<'PY'` using the smoke helpers from `tests/test_submission_regressions.py` and writing outputs to `/tmp/w4a-smoke-refpl/`. Evidence from that run: `/tmp/w4a-smoke-refpl/output/submission.json` (`answer_count=1`, answer `The answer is 42.`), `/tmp/w4a-smoke-refpl/output/trace_manifest.json` (`trace_count=1`), `/tmp/w4a-smoke-refpl/output/traces/q-1__8a3e90ba8a51.json`, and `/tmp/w4a-smoke-refpl/logs/warmup/20260405T111203Z_build-submission_074aa084eea54c6888d3227d09574935.jsonl` containing `submission.artifacts.corpus.reuse`, `submission.artifacts.index.reuse`, `submission.runtime_dependencies.build`, `submission.question.complete`, and `submission.build.complete`.
**Next action:** None for W4A; closure-ready unless a later integration pass introduces new submission regressions.
