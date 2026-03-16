## Skill
- Follow `apm-logs` for logging taxonomy and conventions.
- Use `apm-report` when the current session needs to write an agent log.

## Expected structure
- `logs/project/runtime/` -- core runtime logs (start/stop, user actions, errors).
- `logs/project/reports/` -- generated reports (test, review, general).
- `logs/agents/{TASK_ID}/` -- task-scoped agent logs.

## Conventions
- Log format: `[YYYY-MM-DD HH:MM:SS] [LEVEL] - Message`.
- Include identifiers when available (request id, task id, file names).
- If work maps to a task, reference the task id in `memory_bank/tasks/{TASK_ID}.md`.
- Keep project logs in `logs/project/...` and agent logs in `logs/agents/...`.

## Guardrails
- Do not store test artifacts here (use `tests/`).
