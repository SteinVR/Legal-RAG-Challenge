# INGESTION-SYNTHESIS wave-4-memory-bank-formalization

## Metadata + Exact Request
- Logged at: 23-03-2026 22:11
- Agent identity: Codex
- Task: INGESTION-SYNTHESIS
- Branch / worktree: `main`
- Scope: Formalize Wave 4 in the Memory Bank by updating `TASKS.md` and creating detailed `TASK-W4*` execution files with explicit `# About` and `# Specification` sections.
- Exact user request or delegated objective:
  > Теперь, на основе этого файла нужно сделать подробные спецификации по обновлению.
  >
  > Это будет Wave 4 - можешь оформить как одну задачу или разбить ее на несколько блоков подзадач (на твое усмотрение).
  >
  > Соответственно, вносишь всю Wave 4 в memory_bank/TASKS.md после ## 2. Post-Baseline Tracks.
  >
  > И оформляешь TASK-ID.md файл(ы), но добавь в них # About и # Specification, где будет подробное описание самой задачи, и ее подробная спецификация по разработке - чтобы снизить дрифт и потенциальные расхождения при разработке.
  >
  > Другие файлы Memory Bank пока не обновляются.

## Task Setup
- Context used:
  - `memory_bank/TASKS.md`
  - existing Wave 3 task files
  - updated `docs/unified_document_processing_architecture.md`
  - warmup baseline postmortem context already established earlier in session
- Constraints:
  - update only `memory_bank/TASKS.md` and the new task files;
  - do not update other Memory Bank files;
  - include exact `# About` and `# Specification` headers in each new task file;
  - reduce implementation drift by making the task specs decision-complete.
- Planned approach:
  - define a multi-task Wave 4 instead of one monolithic task;
  - insert Wave 4 under `## 2. Post-Baseline Tracks`;
  - keep existing backlog buckets as non-authoritative thematic groupings;
  - create `TASK-W4A` through `TASK-W4E` with explicit ownership boundaries and dependencies.

## Implementation Log
1. Reviewed the current `TASKS.md` structure and recent Wave 3 task-file format to keep the new Wave 4 entries stylistically compatible with the existing Memory Bank.
2. Added `### Wave 4 -- Baseline Recovery & Structural Upgrade` directly under `## 2. Post-Baseline Tracks`, including dependency notes and five authoritative task links.
3. Left the existing High Priority / Medium Priority / Exploratory track lists in place, but added an explicit note that they remain thematic backlog buckets while Wave 4 tasks are the execution units.
4. Created five new task files:
   - `TASK-W4A` page attribution precision and validation policy
   - `TASK-W4B` typed extraction and legal prefilters
   - `TASK-W4C` structural parser branch, normalization, and table enrichment
   - `TASK-W4D` retrieval upgrade and chunk/tuning work
   - `TASK-W4E` cross-case decomposition and orchestration
5. Added exact top-level `# About` and `# Specification` sections to every new task file and populated them with implementation-grade requirements, non-goals, dependencies, acceptance criteria, and evaluation expectations.

## Verification
- Checked the updated `memory_bank/TASKS.md` to confirm Wave 4 appears immediately under `## 2. Post-Baseline Tracks`.
- Verified that each new task file contains:
  - `# Task: TASK-W4X`
  - `# About`
  - `# Specification`
- Verified that the five task IDs and links in `TASKS.md` match the created filenames exactly.

## Issues / Resolutions
- The existing post-baseline section only had loose thematic tracks, which would have created ownership drift during implementation.
- Resolved by formalizing Wave 4 as five execution tasks with explicit dependency boundaries.
- The user requested more detailed task contracts than the current Wave 3 style provides.
- Resolved by adding `# About` and `# Specification` while preserving the familiar numbered Summary/Scope/Plan/Notes/Outcome structure below them.

## Artifacts
- Files touched:
  - `memory_bank/TASKS.md`
  - `memory_bank/tasks/TASK-W4A.md`
  - `memory_bank/tasks/TASK-W4B.md`
  - `memory_bank/tasks/TASK-W4C.md`
  - `memory_bank/tasks/TASK-W4D.md`
  - `memory_bank/tasks/TASK-W4E.md`
  - `logs/agents/INGESTION-SYNTHESIS/INGESTION-SYNTHESIS_Codex_wave-4-memory-bank-formalization_22-11_23-03-2026.md`
- Verification artifacts:
  - local inspection of `memory_bank/TASKS.md`
  - local search confirming `# About` / `# Specification` presence in all new task files

## Result / Conclusions (Exact Answer to User)
> Formalized Wave 4 in the Memory Bank as five execution tasks under `memory_bank/TASKS.md` and created detailed `TASK-W4A` through `TASK-W4E` files with exact `# About` and `# Specification` sections. No other Memory Bank files were updated.
