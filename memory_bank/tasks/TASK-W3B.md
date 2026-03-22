# Task: TASK-W3B

## 1. Summary

**Title**: Retrieval, reranking & evidence selection  
**Description**: Hybrid search + reranking + support-page validation/compression. Core grounding module.  
**Status**: Done (baseline merged; corrective runnable-completeness pass open)
**Wave**: Wave 3 -- Parallel Baseline Build

## 2. Scope

- **In scope**:
  - Hybrid search: BM25 + dense score fusion
  - Qwen3-Reranker-0.6B reranking
  - Parent-page lifting (chunk results -> page-level aggregation)
  - Support-page validator: remove pages not confirmed by retrieval (ERC2 pattern)
  - Support-page compressor: deduplicate, greedy prune, separate budgets by answer_type
  - Null/unanswerable detection at retrieval level (no relevant pages -> empty set)
  - Retrieval budgets: candidate count, rerank count, evidence count
- **Out of scope**: answer generation, telemetry packing
- **Dependencies**: TASK-W3A runnable index contract; implementation may proceed in parallel with mocks/stubs only for baseline development, not for final acceptance

## 3. Implementation Plan

- Implemented retrieval pipeline modules and `src/retrieval/service.py` against the Wave 3 indexing contract.
- Added dedicated retrieval component/service tests covering hybrid retrieval and evidence-selection behavior.
- Merged task branch into `main` after quality-gate review and final integrated verification.
- Independent post-merge review later found that the merged baseline stopped at protocol/orchestration layers and did not ship a concrete Qdrant-backed candidate searcher over the persisted W3A index.
- Corrective follow-up for this task is limited to delivering a concrete runnable retrieval backend and its tests; full pipeline orchestration remains outside W3B.

## 4. Working Notes

Grounding is F-beta with beta=2.5: recall >> precision, but precision still matters.
Search broadly, report narrowly. Internal candidate set can be large; final evidence set must be minimal.
Qdrant hybrid query: fuse dense + sparse scores via RRF or custom weights; filter by payload (doc_id, chunk_type) where needed.
The original Wave 3B baseline accepted a protocol-only backend, which is no longer considered sufficient. Final acceptance for this task now requires real retrieval against persisted W3A artifacts, not only mocks/test doubles.

## 5. Outcome

**Result**: Completed on 2026-03-21 as a baseline retrieval service layer and merged to `main`, but later independent review found the runnable backend path incomplete.  
**Next action**: Close the W3B corrective gap by shipping a concrete Qdrant-backed retrieval backend over W3A artifacts, without expanding scope into W3D orchestration.
