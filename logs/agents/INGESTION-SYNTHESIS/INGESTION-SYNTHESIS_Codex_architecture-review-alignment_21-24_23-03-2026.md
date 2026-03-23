# INGESTION-SYNTHESIS architecture-review-alignment

## Metadata + Exact Request
- Logged at: 23-03-2026 21:24
- Agent identity: Codex
- Task: INGESTION-SYNTHESIS
- Branch / worktree: `main`
- Scope: Align the canonical document-processing architecture with the explicit review findings and the baseline-driven comments extracted from the warmup100 postmortem.
- Exact user request or delegated objective:
  > Тогда исправь в соответствие с review-doc и главными замечаниями, которые ты вынес

## Task Setup
- Context used:
  - `memory_bank/tasks/TASK-BASELINE.md`
  - `docs/Document_Processing_Architecture_Review.md`
  - `docs/unified_document_processing_architecture.md`
  - `memory_bank/ARCHITECTURE.md`
  - `memory_bank/STATE.md`
- Constraints:
  - do not touch `memory_bank/`;
  - update the canonical architecture doc instead of creating another parallel note;
  - preserve the project’s grounding-first philosophy while correcting phase priorities and implementation completeness.
- Planned approach:
  - revise the canonical architecture doc around baseline score blockers;
  - make the `opendataloader-pdf` integration spec decision-complete;
  - align table serialization policy with the review caveat without throwing away the enrichment track.

## Implementation Log
1. Re-read the baseline postmortem and architecture review, then cross-checked both against the current canonical architecture doc to identify missing or overly rigid decisions.
2. Updated the top-level design position so the document now explicitly prioritizes page attribution precision, typed extraction, and query-side legal prefilters in addition to parser upgrades.
3. Expanded parser arbitration with broken-font routing, tagged fast path, hybrid-vs-local mode rules, JVM batching implications, required JSON sidecars, and `table_method="cluster"` as the preferred table-extraction experiment.
4. Strengthened normalization and table sections with artifact cleaning, caption linkage, list nesting preservation, benchmark-gated semantic table serialization, and a config-level kill switch for serialized table chunks.
5. Added new architecture material for page attribution precision, typed extraction upgrade, grounding-validation degradation policy, asymmetric retrieval tuning, token-aware chunking, embedding-strategy review, and revised phase ordering to match baseline blockers.
6. Updated the A/B plan so it now covers minimal-evidence selection, calibrated typed extraction, hybrid-vs-local parser mode comparison, and gated table-serialization experiments.

## Verification
- Inspected the updated document sections directly after patching.
- Verified presence of the new decision points via local `rg` search:
  - page attribution precision stage
  - typed extraction upgrade
  - hybrid mode and `table_method="cluster"`
  - JSON-only raw sidecars
  - page-degradation-first grounding validation
- Reviewed the resulting `git diff` for `docs/unified_document_processing_architecture.md` to ensure the phase order and policy changes landed coherently.

## Issues / Resolutions
- The prior architecture doc was strong on upstream parsing and retrieval structure but under-specified on the post-retrieval score blockers exposed by the baseline.
- Resolved by adding explicit architecture stages and rules for evidence-page minimization, answer-type-specific extraction, and validation behavior.
- The prior doc also treated LLM table serialization too categorically.
- Resolved by reframing it as default-on but benchmark-gated, with an explicit kill switch if the legal-domain A/B result is negative.

## Artifacts
- Files touched:
  - `docs/unified_document_processing_architecture.md`
  - `logs/agents/INGESTION-SYNTHESIS/INGESTION-SYNTHESIS_Codex_architecture-review-alignment_21-24_23-03-2026.md`
- Verification artifacts:
  - local `git diff` output for the canonical architecture doc;
  - local search hits confirming the new architecture sections and policies.

## Result / Conclusions (Exact Answer to User)
> Updated the canonical architecture doc so it now aligns with the review and the baseline-driven findings: parser integration is more implementation-complete, table serialization is benchmark-gated instead of dogmatic, and the document now explicitly prioritizes page attribution precision, typed extraction, query-side legal prefilters, and page-degradation-first grounding validation.
