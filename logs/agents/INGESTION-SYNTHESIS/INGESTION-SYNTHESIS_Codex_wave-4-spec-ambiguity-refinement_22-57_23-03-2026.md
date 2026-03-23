# INGESTION-SYNTHESIS wave-4-spec-ambiguity-refinement

## Metadata + Exact Request
- Logged at: 23-03-2026 22:57
- Agent identity: Codex
- Task: INGESTION-SYNTHESIS
- Branch / worktree: `main`
- Scope: Refine Wave 4 Memory Bank specifications in response to review feedback about ambiguity, missing embedding review, and excess degrees of freedom.
- Exact user request or delegated objective:
  > Хорошо, тогда обнови спеки

## Task Setup
- Context used:
  - `docs/Wave_4_task_specifications_review.md`
  - current `memory_bank/TASKS.md`
  - current `memory_bank/tasks/TASK-W4A.md` through `TASK-W4E.md`
  - prior architectural decisions already recorded earlier in this session
- Constraints:
  - update only the Wave 4 task specs and `TASKS.md`;
  - tighten ambiguous wording without over-constraining real engineering fallbacks;
  - preserve the existing Wave 4 task decomposition.
- Planned approach:
  - accept the review’s hardening pass where it removes genuine ambiguity;
  - keep slightly more engineering-aware wording where the review’s proposal was too absolute;
  - add the missing embedding-quality requirement to `TASK-W4D`.

## Implementation Log
1. Reviewed the Wave 4 spec review against the current `TASK-W4*` files and separated the recommendations into direct accepts versus accepts-with-rewording.
2. Updated `memory_bank/TASKS.md` so the Wave 4 dependency line now says `TASK-W4A`, `TASK-W4B`, and `TASK-W4C` start in parallel, and so `TASK-W4D` depends on the outputs that `TASK-W4C` freezes as accepted.
3. Tightened `TASK-W4A` and `TASK-W4B` wording by removing `may`/`optional` ambiguity around start conditions, retrieval consumption, legal prefilter delivery, and `names` ordering.
4. Tightened `TASK-W4C` with explicit null-behavior for parser-provided fields, required role annotations, required-default hybrid mode and tagged fast path semantics, and `table_method="cluster"` as the required default with explicit regression-based deviation only.
5. Tightened `TASK-W4D` by removing ambiguous dependencies, replacing `optional soft guidance` with `soft (non-blocking) guidance`, specifying question-class retrieval budgets, and adding an explicit embedding-quality acceptance criterion for accepted new chunk families.
6. Tightened `TASK-W4E` by replacing `optional escalation path` with `selective escalation path` and by requiring synthetic amendment-vs-current coverage if the warmup set lacks that slice.

## Verification
- Ran local search for the specific ambiguous phrases called out by the review and confirmed they no longer appear in `TASKS.md` or the `TASK-W4*` files.
- Reviewed the resulting diffs to confirm the spec hardening landed without changing the Wave 4 task breakdown.

## Issues / Resolutions
- The original Wave 4 task specs still had several planning-safe but implementation-ambiguous words such as `may`, `optional`, `when available`, and `preferred`.
- Resolved by converting them to execution-grade semantics, while preserving fallback behavior where hard absolutes would have been too rigid.
- `TASK-W4D` was missing the embedding-quality review requirement present in the canonical architecture doc.
- Resolved by adding an explicit acceptance criterion tied to chunk families frozen by `TASK-W4C`.

## Artifacts
- Files touched:
  - `memory_bank/TASKS.md`
  - `memory_bank/tasks/TASK-W4A.md`
  - `memory_bank/tasks/TASK-W4B.md`
  - `memory_bank/tasks/TASK-W4C.md`
  - `memory_bank/tasks/TASK-W4D.md`
  - `memory_bank/tasks/TASK-W4E.md`
  - `logs/agents/INGESTION-SYNTHESIS/INGESTION-SYNTHESIS_Codex_wave-4-spec-ambiguity-refinement_22-57_23-03-2026.md`
- Verification artifacts:
  - local `rg` check showing the reviewed ambiguous phrases are gone;
  - local `git diff` for the Wave 4 Memory Bank files.

## Result / Conclusions (Exact Answer to User)
> Updated the Wave 4 specs so the reviewed ambiguities are removed, `TASK-W4D` now includes the missing embedding-quality gate, and the wording is tighter without losing necessary fallback semantics for hybrid/local parser behavior.
