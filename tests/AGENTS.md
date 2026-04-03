## Skill
- Use **apm-test** for test strategy, execution, and reporting only where it does not conflict with the project-specific rules below.

## Expected structure
- `tests/` -- minimal unit tests only.
- Smoke and e2e validation lives primarily in project scripts and runtime-log review, not in large pytest integration suites.
- Reports go to `logs/project/reports/` using apm-test templates.

## Conventions
- Project-specific local policy overrides generic `apm-test` defaults around layered coverage and `>80%` targets.
- Keep unit coverage to the smallest high-signal surface: pure logic, config parsing, runtime logging, and other stable low-mock boundaries.
- Do not add new orchestration-heavy pytest tests for CLI flows, submission pipeline, retrieval/index assembly, or provider integration/ unless explicitly requested.
- Prefer smoke/e2e runs plus runtime-log inspection for real pipeline validation.
- Name test files to mirror source: `test_{module}.py` or `{module}.test.ts`.
- Reference covered task ids in test notes when relevant.

## Guardrails
- Do not place test reports in this directory (use `logs/project/reports/`).
- Do not implement application logic here.
- Remove stale helpers from `tests/support/` when the owning pytest suite is deleted.
