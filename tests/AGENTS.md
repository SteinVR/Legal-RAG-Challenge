## Skill
- Use **apm-test** for test strategy, execution, and reporting.

## Expected structure
- `tests/` -- unit, integration, edge-case, and smoke tests.
- Reports go to `logs/project/reports/` using apm-test templates.

## Conventions
- Target >80% coverage where feasible.
- Treat tests as specifications; change tests only if requirements change.
- Name test files to mirror source: `test_{module}.py` or `{module}.test.ts`.
- Reference covered task ids in test notes when relevant.

## Guardrails
- Do not place test reports in this directory (use `logs/project/reports/`).
- Do not implement application logic here.
