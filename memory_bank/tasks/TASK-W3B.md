# Task: TASK-W3B

## 1. Summary

**Title**: Retrieval, reranking & evidence selection  
**Description**: Hybrid search + reranking + support-page validation/compression. Core grounding module.  
**Status**: Planned
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
- **Dependencies**: TASK-W3A interface contract (indices); implementation may proceed in parallel with mocks/stubs once the contract is frozen

## 3. Implementation Plan



## 4. Working Notes

Grounding is F-beta with beta=2.5: recall >> precision, but precision still matters.
Search broadly, report narrowly. Internal candidate set can be large; final evidence set must be minimal.
Qdrant hybrid query: fuse dense + sparse scores via RRF or custom weights; filter by payload (doc_id, chunk_type) where needed.

## 5. Outcome

**Result**: [Pending]  
**Next action**: freeze retrieval/index contract, then implement in Wave 3 with stubs or against TASK-W3A outputs
