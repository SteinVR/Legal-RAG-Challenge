# [INGESTION-SYNTHESIS] wave-4-source-map-corrections

## Metadata + Exact Request
- Logged at: 23-03-2026 23:57
- Agent identity: Codex
- Task: INGESTION-SYNTHESIS
- Branch / worktree: current workspace
- Scope: Correct Wave 4 task-spec source references and adaptation maps after review of the latest spec commit.
- Exact user request or delegated objective:
  > Поправь

## Task Setup
- Context used:
  - `docs/Wave_4_task_specifications_review.md`
  - latest committed Wave 4 spec diff
  - `docs/unified_document_processing_architecture.md`
  - current `src/`
  - `external/opendataloader-pdf`
  - `external/RAG-Challenge-2`
- Constraints:
  - Keep changes limited to correcting spec accuracy and architectural alignment.
  - Do not expand Wave 4 scope beyond the reviewed issues.
- Planned approach:
  - Fix hard factual mismatch in `TASK-W4C`.
  - Reframe misleading `RAG-Challenge-2` references in `TASK-W4A` and `TASK-W4B`.
  - Repair temporal inconsistency in `TASK-W4E`.

## Implementation Log
1. Re-reviewed the latest Wave 4 spec additions against current code and vendor references.
2. Corrected `TASK-W4C` hybrid integration text to use the documented `docling-fast` hybrid mode and corrected the `options.json` value list.
3. Rewrote the `TASK-W4A` reference to `_validate_page_references()` as a partial/negative guardrail reference rather than a positive minimal-evidence pattern.
4. Reframed `TASK-W4B` prompt references as schema/extraction-discipline references only, and explicitly blocked prompt-centric runtime drift and company-style hard routing.
5. Reworked `TASK-W4E` page recomposition guidance so final minimization obeys the W4A final-attribution contract instead of incorrectly re-running Pass A after sub-answer recomposition.
6. Tightened decomposition trigger examples to avoid using baseline nulls as an escalation rule.

## Verification
- Checked `git diff` for:
  - `memory_bank/tasks/TASK-W4A.md`
  - `memory_bank/tasks/TASK-W4B.md`
  - `memory_bank/tasks/TASK-W4C.md`
  - `memory_bank/tasks/TASK-W4E.md`
- Re-checked source truth in:
  - `external/opendataloader-pdf/python/opendataloader-pdf/src/opendataloader_pdf/convert_generated.py`
  - `external/opendataloader-pdf/options.json`
  - `external/RAG-Challenge-2/src/questions_processing.py`
  - `docs/unified_document_processing_architecture.md`
- Result:
  - corrected spec text now matches the documented `opendataloader-pdf` API;
  - adaptation notes no longer contradict extraction-first / minimal-evidence architecture;
  - decomposition flow no longer violates the two-pass grounding timeline.

## Issues / Resolutions
- Issue: `TASK-W4C` used unsupported `hybrid="docling"` in the integration example.
- Resolution: replaced with `hybrid="docling-fast"` and updated the options list accordingly.
- Issue: `TASK-W4A` and `TASK-W4B` described some `RAG-Challenge-2` patterns too positively, despite architectural conflicts.
- Resolution: kept them as bounded references and made the non-port rules explicit.
- Issue: `TASK-W4E` mixed pre-answer and post-answer attribution semantics.
- Resolution: changed recomposition guidance to a final-attribution/minimization step consistent with W4A.

## Artifacts
- Files touched:
  - `memory_bank/tasks/TASK-W4A.md`
  - `memory_bank/tasks/TASK-W4B.md`
  - `memory_bank/tasks/TASK-W4C.md`
  - `memory_bank/tasks/TASK-W4E.md`
- Reports, plots, logs, or other evidence:
  - this activity log
- Verification artifacts:
  - local `git diff`
  - local source inspection in `src/` and `external/`

## Result / Conclusions (Exact Answer to User)
> Поправил Wave 4 спеки в четырёх местах: убрал неверный `opendataloader-pdf` hybrid contract, перевёл два misleading references из `RAG-Challenge-2` в bounded/negative references и выровнял `W4E` под двухпроходный grounding flow. После перепроверки diff новые формулировки совпадают и с реальным кодом, и с канонической архитектурой.
