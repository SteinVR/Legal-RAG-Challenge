## Terminology
- **RAPID:** fast product delivery with tight feedback loops.

## Memory Bank
- Directory name is `memory_bank/`.
- `TASKS.md`: grouped high-level tasks in priority order (lives directly in `memory_bank/`, not inside `tasks/`).
- `specs/SPEC_{TASK_ID}.md`: frozen task specification — goal, pipeline, contracts, DoD. **Read-only during execution. Do not modify.**
- `tasks/{TASK_ID}.md`: working journal — notes, review findings, outcome.
- `STATE.md`: compact operational status and deviations.

## Project map
- `memory_bank/` — architecture, state, and task board.
- `src/` — implementation.
- `tests/` — tests.
- `logs/` — for project logs.

## Workflow
- Core loop: investigate -> plan -> implement -> verify.
- Use the harness internal todo list proactively.

## Subagent paradigm
- For complex tasks, decompose work into independent subtasks and delegate to subagents.
- Parallelize only tasks with low file overlap and explicit ownership boundaries.
- Define each delegation with expected output format and acceptance checks.
- Use skill `apm-subagent` to form role-appropriate delegation requests.
- Wait for the sub-agents to finish and don't rush them. Don't do their work.

## Glossary
- **Quality Gate** — post-implementation verification: simplify, review, contract compliance, fix, accept. Defined in skill `apm-quality-gate`. 
- **Wave Integration Gate** — post-merge verification: build, typecheck, tests, dependency/environment audit. Defined in skill `apm-git-taskflow`.
- **Worktree Protocol** — task-scoped branch and worktree isolation for parallel work. Defined in skill `apm-git-taskflow`. 
- **Wave Protocol** — task grouping described in `memory_bank/TASKS.md`. Waves execute sequentially; tasks within a wave execute in parallel.
- **Activity Log** — structured agent session log. Defined in skill `apm-report`. 
- **Delegation Contract** — minimal framing for specialist subagent requests. Defined in skill `apm-subagent`. 
- **Runtime Escalation** — if you discover contradictions between specifications, instructions, and actual project state during work, stop and escalate immediately. Do not silently work around inconsistencies.
- **Review Loop** — when requesting a review agent run, this implies the full review loop: address and resolve all review findings of severity P0, P1, and P2, then spawn a new review agent to re-verify. Repeat this process until no P0, P1, or P2 issues remain; only then is the review loop considered complete.

## Context conventions
- `memory_bank/` files, active task specs, and loaded skill files — always read directly. These are compact, known-path files that form your working context.
- Codebase exploration — searching for files, understanding unfamiliar modules, tracing dependencies, scanning directory trees, reading implementation code for orientation — delegate to **Explorer subagents** (when available).
- Web research — investigating libraries, APIs, error messages, best practices, documentation, or any external information — delegate to **Web-Explorer subagents** (when available).
- Decision rule: known path, need content for current action → read directly. Searching or orienting in codebase → spawn Explorer (when available). Need external/web information → spawn Web-Explorer (when available).

## Code conventions
- All code must be **modular, typed and simple**. Each logical step (loading, preprocessing, inference, scoring, etc.) is a self-contained module with explicit input/output types. `main.py` composes modules into a pipeline — no business logic lives there.
- **File size support:** Scripts must not exceed 500 lines of code. Extension up to 600 lines is allowed only to preserve logical boundaries, but exceeding 500 lines triggers a strong recommendation for decomposition and refactoring. If a file grows over 500 lines: refactor and split.
- **Mandatory function documentation:** Every function must have a docstring accurately describing its purpose, arguments, and return values. Docstrings are required for all functions, without exception.
- **Runtime logging** at key pipeline boundaries is mandatory: module entry/exit, data shape transitions, metric computations, error conditions. Without runtime logs, failures are opaque and the feedback loop breaks. Keep logs concise — structured one-liners (`key=value`), not verbose prose. Follow skill `apm-logs` for format and placement.

## Test policy
- Canonical pytest suite is a compact smoke suite: keep total test count `<10` unless explicitly approved otherwise.
- Primary layout is one smoke test per core stage (`ingestion`, `indexing`, `retrieval`, `answering`) plus optional focused integration smoke.
- Tests must assert factual outcomes (written artifacts, grounded pages, typed answers), not private helper internals.
- Do not reintroduce broad granular unit/regression suites by default; add fine-grained tests only for high-risk regressions that cannot be covered by stage smoke.
- OpenAI/API-backed generation is forbidden in tests; use local deterministic stubs for provider paths.
- Model-backed smoke checks are GPU-only: no CPU fallback. If CUDA is unavailable or a model does not load on CUDA, fail fast with a clear error.
- After every smoke/e2e run, inspect runtime logs and validate observed outputs, not only process exit codes.

## Self-review gate
Before reporting work as done, perform structured self-review. Fix anything found before handoff.

1. **Re-read** all changed files. Check for bugs, logical errors, off-by-one errors, unhandled edge cases.
2. **Spec compliance** (if exists): verify implementation matches `SPEC_{TASK_ID}.md` — goal, pipeline steps, contracts table (signatures and types), DoD items.
3. **Type correctness**: confirm type annotations are present and consistent across function boundaries.
4. **Logging**: confirm runtime logging exists at key pipeline boundaries per skill `apm-logs`.

Report self-review outcome in the handoff (steps performed, issues found and fixed, residual concerns).
