# INGESTION-SYNTHESIS page-attribution-ablation-refinement

## Metadata + Exact Request
- Logged at: 23-03-2026 21:50
- Agent identity: Codex
- Task: INGESTION-SYNTHESIS
- Branch / worktree: `main`
- Scope: Refine the canonical architecture doc after review comments about page-attribution flow, ablation design, and cross-case phase overlap.
- Exact user request or delegated objective:
  > "если мы считаем их наиболее перспективными" - этой экспертизы я жду от тебя.
  >
  > Обнови файл.

## Task Setup
- Context used:
  - latest `docs/unified_document_processing_architecture.md`
  - user feedback on Section 8 temporal flow
  - user feedback on A/B test bundling
  - user feedback on Phase 2 vs Phase 7 overlap
- Constraints:
  - keep the canonical file as the single source of architecture truth;
  - make the change decision-complete rather than leaving tradeoffs implicit;
  - preserve the already-applied baseline-driven reprioritization.
- Planned approach:
  - convert page attribution into a two-pass flow;
  - keep both promising page-grounding changes in the target pipeline while splitting them in the ablation matrix;
  - clarify the implementation boundary between baseline multi-document support and full decomposition.

## Implementation Log
1. Reworked Section 8 so page attribution is now explicitly two-pass: pre-answer evidence pruning followed by post-answer final attribution, with empty page lists only emitted in the second pass.
2. Updated Phase 1 to make the intended mainline choice explicit: include both Pass A pruning and page-degradation-first validation because they solve different observed failure modes.
3. Split the prior bundled A/B item into separate ablations for page pruning and validation policy, then added a combined-stack comparison to preserve interaction measurement.
4. Clarified the Phase 2 / Phase 7 boundary: Phase 2 now covers baseline multi-document retrieval plus typed extraction without decomposition, while Phase 7 is reserved for full comparative-question decomposition and orchestration.

## Verification
- Re-read the revised Section 8, phased implementation sequence, and A/B list directly after patching.
- Reviewed `git diff` for `docs/unified_document_processing_architecture.md` to confirm:
  - the two-pass page-attribution flow is explicit;
  - the mainline-vs-ablation distinction is explicit;
  - Phase 2 and Phase 7 no longer overlap semantically.

## Issues / Resolutions
- The previous wording created a chicken-and-egg problem by letting pre-answer page attribution decide a true no-answer state.
- Resolved by splitting page attribution into pruning and finalization passes.
- The previous A/B matrix could not isolate the effect of page pruning vs validation changes.
- Resolved by separating the ablations and adding a combined-stack comparison.

## Artifacts
- Files touched:
  - `docs/unified_document_processing_architecture.md`
  - `logs/agents/INGESTION-SYNTHESIS/INGESTION-SYNTHESIS_Codex_page-attribution-ablation-refinement_21-50_23-03-2026.md`
- Verification artifacts:
  - local `git diff` for the canonical architecture doc;
  - direct inspection of the revised architecture sections.

## Result / Conclusions (Exact Answer to User)
> Updated the canonical architecture doc so page attribution is now two-pass and temporally consistent, the target pipeline explicitly keeps both promising grounding changes while the A/B matrix isolates them cleanly, and Phase 2 vs Phase 7 now have a hard boundary between baseline multi-document support and full cross-case decomposition.
