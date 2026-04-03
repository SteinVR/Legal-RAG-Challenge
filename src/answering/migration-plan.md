# Migration Plan: `src/answering`

## Goal and non-goals

### Goal
- Break `src/answering/service.py` into a true orchestration layer plus focused modules for structured schemas, query metadata extraction, deterministic guardrails, solver execution, and page-attribution integration.
- Preserve schema-first typed answering, two-pass page attribution, and decomposition behavior while making each concern independently testable and swappable.
- Add explicit runtime logging around solving, attribution, decomposition, and failure paths.

### Non-goals
- Do not weaken page-grounded answering or revert to looser free-text-first behavior.
- Do not fold decomposition into submission orchestration or provider logic.
- Do not keep `service.py` as a god module once migration is complete.

## Current boundary map
- `service.py` currently owns answer schemas, query metadata extraction, deterministic extractors, typed guardrails, provider orchestration, free-text grounding validation, and `answer_question()`.
- `decomposition.py` is distinct but tightly coupled to `AnsweringService`.
- `page_attribution.py` is algorithmically narrower but lacks boundary-level runtime logging.
- `__init__.py` exports a smaller public surface than the internal module actually owns.

## Target module split
- `contracts.py`: `AnswerResult`, answering-local protocols, and stable result shapes.
- `answer_schemas.py`: `ANSWER_SCHEMA_REGISTRY` and Pydantic answer schema classes only.
- `query_metadata.py`: `QueryMetadata`, `LegalEntityMetadata`, and metadata extraction helpers.
- `deterministic.py`: deterministic extractors, typed guardrails, answer equivalence helpers, and validation helpers.
- `solver.py`: provider-facing structured solve flow and free-text fallback flow.
- `page_attribution.py`: keep page attribution logic, but add explicit logging and typed entrypoints.
- `decomposition.py`: keep as a separate subsystem, but depend on `contracts.py` and `solver/service` interfaces instead of intimate internal helpers.
- `service.py`: orchestration only, choosing the correct path and composing the above modules.

## Migration steps
1. Move schema models and registry out of `service.py` into `answer_schemas.py`.
2. Move query metadata models/extraction into `query_metadata.py`.
3. Move deterministic extraction, confidence/grounding guardrails, and answer normalization into `deterministic.py`.
4. Extract provider-facing solve logic into `solver.py`, leaving `service.py` with orchestration only.
5. Update `decomposition.py` to depend on stable public contracts instead of implementation details inside `service.py`.
6. Add explicit logging to `page_attribution.py` and `decomposition.py`.
7. Shrink `__init__.py` to the intended public surface and remove accidental coupling through internal imports.

## Contracts to preserve and change

### Preserve
- `AnsweringService.answer_question` remains the stage entrypoint until submission is migrated.
- Structured answer schemas, canonical unanswerable free-text answer, page attribution trace semantics, and decomposition recomposition behavior remain stable.
- Reasoning-effort-by-answer-type behavior remains provider-facing contract, not an implementation accident.

### Change
- `service.py` stops owning schema definitions, metadata extraction, and deterministic guardrails inline.
- Decomposition depends on a stable answering contract rather than on the full service internals.
- Page attribution gets first-class boundary logging.

## Logging and typing checklist
- Mandatory non-debug logs: `answering.start`, `answering.retrieval.accepted`, `answering.solve.start`, `answering.solve.complete`, `answering.attribution.start`, `answering.attribution.complete`, `answering.decomposition.start`, `answering.decomposition.complete`, `answering.complete`, `answering.failed`.
- Every stage boundary must use typed contracts; avoid passing raw page dictionaries between solving, attribution, and decomposition once stable wrappers exist.
- Fail fast on provider/schema violations rather than silently degrading into weaker answer paths unless that degradation is explicitly defined in the preserved contract.

## Verification
- Run typed-answer smoke checks across boolean, number, name, names, date, and free-text question types.
- Run decomposition smoke coverage on known cross-case questions and inspect recomposed answers plus page traces.
- Inspect runtime logs for normal-run solve, attribution, and decomposition events.
- Run answering-focused tests and at least one downstream submission question-run smoke.

## Acceptance criteria
- `service.py` is orchestration-only.
- Schemas, metadata extraction, deterministic guardrails, and solver logic live in separate modules.
- Page attribution and decomposition are explicit logged subsystems, not sidecar helpers.

## Risks and rollback
- The main risk is changing answer semantics while extracting helpers from `service.py`. Roll back by diffing final `AnswerResult` payloads and page traces against the pre-migration baseline.
- The second risk is creating circular imports between schemas, solver, decomposition, and service. Use `contracts.py` as the stable seam to prevent that drift.
