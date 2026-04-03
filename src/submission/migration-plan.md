# Migration Plan: `src/submission`

## Goal and non-goals

### Goal
- Split `src/submission/pipeline.py` into a real orchestration layer plus explicit modules for artifact reuse checks, question execution, telemetry assembly, trace writing, validation gating, and packaging.
- Preserve external submission-facing artifacts and the current CLI surface while cleaning up internal stage boundaries.
- Make submission the place where stages are composed, not the place where stage internals are reimplemented.

### Non-goals
- Do not change the challenge-facing submission bundle structure.
- Do not embed provider or retrieval implementation details directly in submission orchestration.
- Do not keep lazy/caching helpers hidden inside `pipeline.py` after the migration.

## Current boundary map
- `sync.py` already owns phase-local path layout and sync orchestration.
- `pipeline.py` owns artifact reuse checks, corpus/index rebuild decisions, question loop orchestration, retrieval/provider caching, telemetry packing, trace writing, local validation, archive creation, and architecture summary helpers.
- `telemetry_packer.py`, `packager.py`, `submit_gate.py`, and `api_client.py` are narrower, but `pipeline.py` still knows too much about their internals and about stage construction.

## Target module split
- `contracts.py`: `BuildSubmissionResult` and other submission-local orchestration contracts.
- `artifact_reuse.py`: corpus/index completeness checks and rebuild decisions.
- `runtime_dependencies.py`: explicit construction/factory wiring for retriever, provider, and answering dependencies.
- `question_runner.py`: per-question execution loop, timing, and trace collection.
- `trace_writer.py`: trace file naming and artifact persistence.
- `pipeline.py`: orchestration only, composing sync, artifact reuse, question runner, telemetry, validation, and packaging.
- Keep `sync.py`, `telemetry_packer.py`, `packager.py`, `submit_gate.py`, and `api_client.py`, but narrow their imports and responsibilities where needed.

## Migration steps
1. Move submission-local result models and helpers into `contracts.py`.
2. Extract artifact reuse/completeness checks from `pipeline.py` into `artifact_reuse.py`.
3. Replace `_CachingRetriever` and `_LazyProvider` with explicit dependency/factory modules in `runtime_dependencies.py`.
4. Extract per-question execution, timing, and trace capture into `question_runner.py`.
5. Extract trace artifact writing into `trace_writer.py`.
6. Reduce `pipeline.py` to high-level orchestration, validation ordering, and final result assembly.
7. Keep `sync.py` as the owner of phase layout, and ensure submission code consumes those paths rather than reproducing path logic.
8. Update `main.py` last so it only dispatches into submission orchestration and does not know concrete provider details.

## Contracts to preserve and change

### Preserve
- Submission-facing artifact shapes stay stable: `submission.json`, `code_archive.zip`, and trace outputs remain compatible with current workflow expectations.
- `PhasePaths` remains the owner of phase-local layout.
- Local validation still happens before packaging/final submit output is accepted.

### Change
- `pipeline.py` stops owning helper-heavy internals and lazy dependency wrappers.
- Stage dependency construction becomes explicit and injectable.
- Submission orchestration stops hardcoding provider/retrieval construction details inline.

## Logging and typing checklist
- Mandatory non-debug logs: `submission.build.start`, `submission.artifacts.reuse_check`, `submission.question.start`, `submission.question.complete`, `submission.telemetry.pack`, `submission.validation.start`, `submission.validation.complete`, `submission.package.complete`, `submission.build.complete`, `submission.build.failed`.
- Keep typed contracts for per-question results, trace payloads, and submission build outputs.
- Use fail-fast errors when required artifacts or dependencies are missing instead of hidden rebuild fallbacks beyond the explicitly preserved reuse contract.

## Verification
- Run `build-submission` against an existing phase and inspect produced artifacts and runtime logs.
- Inspect trace outputs after the run, not just exit code.
- Run submission-focused tests and one end-to-end smoke build that exercises retrieval, answering, validation, and packaging together.

## Acceptance criteria
- `pipeline.py` is orchestration-only.
- Artifact reuse, dependency construction, question execution, and trace writing are separate modules.
- CLI behavior and submission artifact shapes remain stable while internal wiring becomes injectable and explicit.

## Risks and rollback
- The main risk is breaking end-to-end orchestration while extracting helpers. Roll back by diffing question-run traces and final submission payloads against the pre-migration baseline.
- The second risk is duplicating phase-path logic across `sync.py` and new helpers. Keep `PhasePaths` authoritative and refuse duplicate path resolution code.
