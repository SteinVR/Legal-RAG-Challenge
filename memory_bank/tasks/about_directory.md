# About This Directory
Purpose: Task-scoped execution records for the work tracked in the Memory Bank.
Contains: One markdown file per formal task. Waves 1-3 are complete. Wave 4 tasks are planned and ready for execution.
Start Here: Find the task id in `memory_bank/TASKS.md`, then open the matching task file here.
Key Files/Dirs:
  - Complete (Waves 1-3): `TASK-W1A.md`, `TASK-W2A.md`, `TASK-W2B.md`, `TASK-W2C.md`, `TASK-W3A.md`, `TASK-W3B.md`, `TASK-W3C.md`, `TASK-W3D.md`
  - Post-baseline analysis: `TASK-BASELINE.md` (warmup100 postmortem; Done)
  - Wave 4 -- Baseline Recovery & Structural Upgrade (Planned, ready to execute):
    - `TASK-W4A.md` -- Page attribution precision & validation policy (starts immediately; no dependencies)
    - `TASK-W4B.md` -- Typed extraction, confidence calibration & legal prefilters (starts immediately; no dependencies)
    - `TASK-W4C.md` -- Structural parser branch, normalization & table enrichment (starts immediately; no dependencies)
    - `TASK-W4D.md` -- Retrieval upgrade, chunk calibration & asymmetric tuning (depends on W4A+W4B+W4C)
    - `TASK-W4E.md` -- Cross-case decomposition & multi-document orchestration (depends on W4A+W4B+W4D)
Notes: Use these files to understand why the code looks the way it does; they are not a substitute for reading the implementation.
