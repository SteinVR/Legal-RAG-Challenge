# Task Board (RAPID): [Project Name]

> Frozen specs in `memory_bank/specs/SPEC_{TASK_ID}.md`. Working notes in `memory_bank/tasks/{TASK_ID}.md`.

## Wave Protocol

Tasks are organized in **waves**. Waves execute sequentially; tasks within a wave execute in parallel.

- **Naming:** `W1A`, `W1B`, `W1C` (Wave 1, tasks A–C), `W2A` (Wave 2, task A), etc.
- **Backlog items:** `BL-001`, `BL-002`, etc.
- A wave is complete when all its tasks pass the quality gate and are integrated.
- The next wave starts only after the current wave is fully integrated.
- New tasks discovered mid-wave go into the next wave or backlog — never into the active wave.
- **SPEC freeze:** No SPEC changes after delegation begins.

## 1. Active Plan (Ordered)

### Wave 1: Architecture
- [ ] [W1A](./specs/SPEC_W1A.md) Define MVP architecture and delivery boundaries.

**Wave DoD:**
- [ ] [Wave-specific completion criteria]

### Wave 2: Core Implementation
- [ ] [W2A] Implement core user flow in `src/`.
- [ ] [W2B] Add core tests and failure handling.

**Wave DoD:**
- [ ] [Wave-specific completion criteria]

## 2. Backlog

- [ ] [BL-001] [Future feature title]: [short description]
- [ ] [BL-002] [Future improvement title]: [short description]

## 3. Review Findings (Cross-Module)

> Findings from quality gate reviews that span multiple tasks or affect shared architecture. Task-specific findings stay in `{TASK_ID}.md`.

| ID | Source | Severity | Summary | Status |
|----|--------|----------|---------|--------|

### Error Patterns

> Recurring issues identified across multiple reviews. Agents must proactively check for these patterns during implementation and review.

| Pattern | Occurrences | Example Tasks | Guidance |
|---------|-------------|---------------|----------|
