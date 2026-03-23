# [INGESTION-SYNTHESIS] schema-first-wave4-rewrite

## Metadata + Exact Request
- Logged at: 24-03-2026 00:39
- Agent identity: Codex
- Task: INGESTION-SYNTHESIS
- Branch / worktree: current workspace
- Scope: Rewrite the canonical architecture and Wave 4 specs from extraction-first typed answering to retrieval-first, schema-first typed solving with deterministic validation.
- Exact user request or delegated objective:
  > Да, так и сделай

## Task Setup
- Context used:
  - `docs/unified_document_processing_architecture.md`
  - `memory_bank/tasks/TASK-W4A.md`
  - `memory_bank/tasks/TASK-W4B.md`
  - `memory_bank/tasks/TASK-W4D.md`
  - `memory_bank/tasks/TASK-W4E.md`
  - `memory_bank/tasks/TASK-BASELINE.md`
  - `src/answering/service.py`
  - `src/submission/pipeline.py`
  - `src/evaluation/goldset.py`
  - `external/RAG-Challenge-2/src/prompts.py`
  - `external/RAG-Challenge-2/src/api_requests.py`
- Constraints:
  - Keep this pass documentation/spec only.
  - Preserve existing challenge answer-shape rules: deterministic unanswerable answers remain `null`; free-text unanswerable remains the canonical sentence.
- Planned approach:
  - Rewrite the architecture section that anchored extraction-first typed answering.
  - Rebuild `W4B` around schema-first typed solving and deterministic validation.
  - Propagate the new `relevant_pages` and solver-contract semantics into `W4A`, `W4D`, and `W4E`.

## Implementation Log
1. Re-checked the current answering flow and baseline results to confirm that the main blocker is post-retrieval typed answering, not retrieval recall or free-text semantics.
2. Rewrote the canonical architecture to define a three-layer answering stack: retrieval/evidence packaging, schema-bound typed solving, deterministic validation/normalization.
3. Updated `TASK-W4B` from a typed-extraction task into a schema-first typed-solving task with:
   - schema registry
   - `is_answerable` / typed `final_answer` / `relevant_pages` / short `reasoning_summary`
   - null policy for deterministic unanswerable answers
   - canonical-sentence policy for free-text unanswerable answers
   - reasoning-effort defaults
   - deterministic validators as post-solver guardrails
   - explicit `RAG-Challenge-2` runtime glue references in `api_requests.py`
4. Updated `TASK-W4A` so Pass B now explicitly consumes solver-reported pages only as a retrieval-backed narrowing signal.
5. Updated `TASK-W4D` so retrieval now owns solver-ready evidence packaging, not just ranking.
6. Updated `TASK-W4E` so decomposition reuses the same schema registry, reasoning defaults, and validator rules from `W4B`.
7. Ran a terminology consistency pass to remove stale `typed extraction` phrasing where it would contradict the new execution model.

## Verification
- Checked targeted consistency with:
  - local `git diff`
  - `rg` searches for stale `extraction-first` / `typed extraction` language
  - cross-check against current answer-shape rules in `src/evaluation/goldset.py`
- Result:
  - architecture and Wave 4 task specs now describe the same answering model;
  - `relevant_pages` is now consistently constrained to Pass B narrowing after retrieval-backed validation;
  - null/canonical-sentence no-answer policies remain aligned with current evaluation rules.

## Issues / Resolutions
- Issue: previous spec state mixed extractor-first architecture with SO/Pydantic additions.
- Resolution: moved to one coherent model: schema-first typed solving + deterministic validation.
- Issue: `relevant_pages` risked becoming a replacement truth source.
- Resolution: constrained it everywhere to subset/intersection-based Pass B narrowing.
- Issue: Wave 4 dependencies (`W4A`, `W4D`, `W4E`) were still phrased around the old typed-extraction model.
- Resolution: synchronized all dependent specs to the new solver contract.

## Artifacts
- Files touched:
  - `docs/unified_document_processing_architecture.md`
  - `memory_bank/tasks/TASK-W4A.md`
  - `memory_bank/tasks/TASK-W4B.md`
  - `memory_bank/tasks/TASK-W4D.md`
  - `memory_bank/tasks/TASK-W4E.md`
- Reports, plots, logs, or other evidence:
  - this activity log
- Verification artifacts:
  - local `git diff`
  - targeted `rg` consistency checks

## Result / Conclusions (Exact Answer to User)
> Переписал архитектуру и связанные Wave 4 спеки под новый принцип: retrieval-first, schema-first typed solving с deterministic validation как guardrail layer. `W4B` теперь описывает schema registry и structured typed solver как primary path, а `W4A/W4D/W4E` синхронизированы под этот контракт, включая retrieval-backed semantics для `relevant_pages`.
