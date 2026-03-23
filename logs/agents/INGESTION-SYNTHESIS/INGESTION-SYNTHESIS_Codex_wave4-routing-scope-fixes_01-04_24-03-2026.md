# [INGESTION-SYNTHESIS] [wave4-routing-scope-fixes]

## Metadata + Exact Request
- Logged at: 24-03-2026 01:04
- Agent identity: Codex
- Task: INGESTION-SYNTHESIS
- Branch / worktree: `main` / primary worktree
- Scope: Fix Wave 4 spec contradictions in parser batching, decomposition routing, and annex/schedule scope.
- Exact user request or delegated objective:
  > Review agreed issues and patch the affected specs and architecture.

## Task Setup
- Context used:
  - `memory_bank/tasks/TASK-W4C.md`
  - `memory_bank/tasks/TASK-W4E.md`
  - `docs/unified_document_processing_architecture.md`
  - `memory_bank/tasks/TASK-W4B.md`
  - `memory_bank/tasks/TASK-W4D.md`
  - `memory_bank/TASKS.md`
- Constraints:
  - Keep edits aligned with Wave 4 soft-prefilter and non-decomposition baseline rules.
  - Remove scope drift rather than broadening Wave 4 implicitly.
- Planned approach:
  - Replace mixed-batch parser wording with route-homogeneous batching.
  - Remove hard single-document routing from decomposition spec.
  - Remove annex/schedule as an explicit Wave 4 decomposition target and sync architecture language.

## Implementation Log
1. Validated the review comments against current Wave 4 specs and the canonical architecture.
2. Updated `TASK-W4C` so parser arbitration happens before `opendataloader_pdf.convert()` and batching is allowed only within homogeneous route/option sets.
3. Updated `TASK-W4E` so entity count is only a decomposition or retrieval-breadth hint, not a hard single-document router.
4. Removed annex/schedule from explicit Wave 4 decomposition targets and aligned the canonical architecture by downgrading annex/schedule handling to marker preservation rather than a required Wave 4 chunk family.

## Verification
- Ran targeted search checks for the removed contradictory phrases and the replacement wording.
- Ran `git diff -- memory_bank/tasks/TASK-W4C.md memory_bank/tasks/TASK-W4E.md docs/unified_document_processing_architecture.md`.
- Result: expected edits present; old contradictory phrases removed from the touched files.

## Issues / Resolutions
- Issue: `opendataloader-pdf` batching wording conflicted with per-document parser arbitration.
- Resolution: specified per-route batching after arbitration.
- Issue: `W4E` still implied single-document routing from entity count.
- Resolution: reduced entity count to a soft hint only.
- Issue: annex/schedule was still presented as a Wave 4 deliverable in decomposition/architecture text.
- Resolution: removed it from decomposition targets and reframed architecture around marker preservation only.

## Artifacts
- Files touched:
  - `memory_bank/tasks/TASK-W4C.md`
  - `memory_bank/tasks/TASK-W4E.md`
  - `docs/unified_document_processing_architecture.md`
- Reports, plots, logs, or other evidence:
  - this activity log
- Verification artifacts:
  - targeted `rg` checks
  - targeted `git diff`

## Result / Conclusions (Exact Answer to User)
> Fixed the three contradictions: parser batching is now route-homogeneous instead of corpus-wide, `W4E` no longer hard-routes one-entity questions into a single-document path, and annex/schedule is no longer specified as an explicit Wave 4 decomposition target. The canonical architecture was synced so Wave 4 preserves annex/schedule markers without requiring annex/schedule-specific chunk families.
