## Skill
- Use **apm-test** for test strategy, execution, and reporting only where it does not conflict with the project-specific rules below.

## Expected structure
- `tests/` is a compact smoke suite (target `<10` tests total).
- Keep one smoke test per core stage: `ingestion`, `indexing`, `retrieval`, `answering`.
- Keep shared deterministic fixtures/helpers in `tests/support/` (for example `smoke_harness.py`).
- Optional integration smoke can validate real warmup runtime on a fixed small slice (5 questions).
- Reports go to `logs/project/reports/` using apm-test templates.

## Conventions
- Assert factual outputs: stage artifacts, grounded page references, typed answers, and manifest integrity.
- Do not anchor tests to private helper internals when a stage-level observable can be validated instead.
- OpenAI/API-backed generation calls are not allowed in tests; provider paths must use deterministic local stubs.
- Model-backed smoke checks are GPU-only: no CPU fallback, no auto-downgrade. Missing CUDA/model readiness must fail fast.
- Prefer synthetic deterministic fixtures for stage smoke and a minimal real-data integration slice for runtime validation.
- Name test files to mirror source: `test_{module}.py` or `{module}.test.ts`.
- Reference covered task ids in test notes when relevant.

## Guardrails
- Do not place test reports in this directory (use `logs/project/reports/`).
- Do not implement application logic here.
- Do not silently skip required model/runtime smoke checks due to missing GPU or model cache; fail with explicit diagnostics.
- Remove stale helpers from `tests/support/` when the owning pytest suite is deleted.
