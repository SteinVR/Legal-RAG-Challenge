## Memory Bank (SSOT)
- **TASKS.md:** grouped, ordered high-level tasks only (lives directly in `memory_bank/`, not inside `tasks/`).
- **design/SPEC-{module}.md:** frozen global module specifications -- contracts, ready interfaces, typecheck gates, invariants, data formats. Updated only with approval.
- **specs/SPEC_{TASK_ID}.md:** frozen task specification -- goal, pipeline, contracts, ready interfaces, typecheck automation, DoD. **Read-only during execution. Do not modify.**
- **tasks/{TASK_ID}.md:** working journal -- notes, review findings, outcome.
- **STATE.md:** compact operational status and blockers.
- Keep main headers from templates intact; add sub-sections only when needed.
