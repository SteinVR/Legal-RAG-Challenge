## Terminology
- **RAPID:** fast product delivery with tight feedback loops.

## Memory Bank (SSOT)
- Directory name is `memory_bank/`.
- `TASKS.md`: grouped high-level tasks in priority order (lives directly in `memory_bank/`, not inside `tasks/`).
- `specs/SPEC_{TASK_ID}.md`: frozen task specification — goal, pipeline, contracts, DoD. **Read-only during execution. Do not modify.**
- `tasks/{TASK_ID}.md`: working journal — notes, review findings, outcome.
- `STATE.md`: compact operational status and deviations.
- Do not update Memory Bank files unless the user explicitly asks.
- Keep main headers from templates intact; add sub-sections only when needed.

## Project map
- `memory_bank/` — architecture source of truth, state, and task board.
- `src/` — implementation.
- `tests/` — tests.
- `logs/` — split into `logs/project/` for project logs and `logs/agents/` for agent-session logs.

## Workflow
- Core loop: investigate -> plan -> implement -> verify.
- Use the harness internal todo list proactively.

## Skills paradigm
- Proactively load the relevant skill at the start of a task — do not wait to be explicitly asked.

## Subagent paradigm
- For complex tasks, decompose work into independent subtasks and delegate to subagents.
- Parallelize only tasks with low file overlap and explicit ownership boundaries.
- Define each delegation with expected output format and acceptance checks.
- Use skill `apm-subagent` to form role-appropriate delegation requests.
- Wait for the sub-agents to finish and don't rush them. Don't do their work.

## Protocol glossary
- **Quality Gate** — load skill `apm-quality-gate`. Post-implementation verification: simplify, review, contract compliance, fix, accept.
- **Wave Integration Gate** — post-merge verification: build, typecheck, tests, dependency/environment audit. Defined in skill `apm-git-taskflow`.
- **Worktree Protocol** — load skill `apm-git-taskflow`. Task-scoped branch and worktree isolation for parallel work.
- **Wave Protocol** — task grouping described in `memory_bank/TASKS.md`. Waves execute sequentially; tasks within a wave execute in parallel.
- **Activity Log** — load skill `apm-report`. Structured agent session log written after meaningful work.
- **Delegation Contract** — load skill `apm-subagent`. Minimal framing for specialist subagent requests.
- **Runtime Escalation** — if you discover contradictions between specifications, instructions, and actual project state during work, stop and escalate immediately. Do not silently work around inconsistencies.

## Self Context management
- `memory_bank/` files, active task specs, and loaded skill files — always read directly. These are compact, known-path files that form your working context.
- Codebase exploration — searching for files, understanding unfamiliar modules, tracing dependencies, scanning directory trees, reading implementation code for orientation — delegate to Explorer subagents. Do not manually traverse or bulk-read source files for orientation purposes.
- Web research — investigating libraries, APIs, error messages, best practices, documentation, or any external information — delegate to Web-Explorer subagents. Do not consume your own context window on web fetches, search results parsing, and page reading.
- Decision rule: known path, need content for current action → read directly. Searching or orienting in codebase → spawn Explorer. Need external/web information → spawn Web-Explorer.

## Code conventions
- All code must be **modular and typed**. Each logical step (loading, preprocessing, inference, scoring, etc.) is a self-contained module with explicit input/output types. `main.py` composes modules into a pipeline — no business logic lives there.
- Prioritize readability and hot-swappability: any module can be replaced or updated without touching the rest of the pipeline.
- **Runtime logging** at key pipeline boundaries is mandatory: module entry/exit, data shape transitions, metric computations, error conditions. Without runtime logs, failures are opaque and the feedback loop breaks. Keep logs concise — structured one-liners (`key=value`), not verbose prose. Follow skill `apm-logs` for format and placement.

## Self-review gate
- Before reporting work as done, **always** perform self-review and verification: re-read changed code, check for bugs, spec/contract mismatches, type errors, and edge cases. Fix anything found before returning to the user.