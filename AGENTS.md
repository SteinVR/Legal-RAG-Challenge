## Terminology
- **RAPID:** fast product delivery with tight feedback loops.

## Memory Bank (SSOT)
- Directory name is `memory_bank/`.
- `TASKS.md`: grouped high-level tasks in priority order.
- `{TASK_ID}.md`: per-task execution plan and working notes in each task file.
- `STATE.md`: compact operational status and deviations.
- Do not update Memory Bank files unless the user explicitly asks.
- Keep main headers from templates intact; add sub-sections only when needed.

## Project map
- `memory_bank/` — architecture source of truth, state, and task board.
- `src/` — implementation.
- `tests/` — tests.
- `logs/` — split into `logs/project/` for project logs and `logs/agents/` for agent-session logs.

## Directory navigation
- Before reading a directory broadly or searching through it chaotically, first look for that directory's `about_directory.md`.
- Use `about_directory.md` to decide which child files and subdirectories are actually relevant, and only then descend deeper.
- Treat `about_directory.md` as the default memory-saving navigation layer for this repo; only skip it when the directory truly has no such file or the task explicitly requires raw artifact inspection.
- If you create a new stable first-party directory that agents or humans are expected to navigate, create its `about_directory.md` in the same task.
- If you significantly change a stable first-party directory's role, key files, or child directories, update the affected `about_directory.md` before finishing the task.
- Treat a missing or stale `about_directory.md` in a maintained navigation directory as a documentation defect to fix, not as optional cleanup.
- This maintenance rule applies to stable first-party navigation directories, not to hidden/tooling directories, caches, raw artifact leaves, or run-specific log leaves.

## Workflow
- Core loop: plan -> implement -> verify.

## Skills paradigm
- Skills are self-contained capability modules that define step-by-step workflows, conventions, and guardrails for specific task types.
- Proactively load the relevant skill at the start of a task — do not wait to be explicitly asked.
- Match the task to a skill using the skill's `description` ("Use when..." trigger); if it fits, load and follow it.
- A loaded skill's workflow is authoritative for its domain; follow it instead of improvising.

## Subagent paradigm
- For complex tasks, decompose work into independent subtasks and delegate to subagents.
- Parallelize only tasks with low file overlap and explicit ownership boundaries.
- Define each delegation with expected output format and acceptance checks.
- Use skill `apm-subagent` to form role-appropriate delegation requests.
- Before final integration, reconcile outputs and run verification.

## Activity log
- If project structure or code was modified, load and follow the skill `apm-report` to form the Activity log after completing the assigned task.

## Notes
- If instructions conflict, prefer the closest (most specific) AGENTS.md.
- Use the pre-built uv environment (.venv).
