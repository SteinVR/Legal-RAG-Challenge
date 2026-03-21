# Task: TASK-W3A

## 1. Summary

**Title**: Chunking & hybrid indexing  
**Description**: Chunk canonical corpus respecting legal document structure; build BM25 + dense + metadata indices.  
**Status**: Done
**Wave**: Wave 3 -- Parallel Baseline Build

## 2. Scope

- **In scope**:
  - Hierarchical chunking: page -> section -> clause -> microchunk + serialized table blocks
  - Each chunk preserves: page span, parent section/clause, neighboring headings, chunk_type
  - Qwen3-Embedding-0.6B batch embedding
  - Qdrant collection with named vectors: dense (Qwen3) + sparse (BM25)
  - Qdrant payload: doc_id, page_span, chunk_type, section, entities, dates
  - Page-parent map (chunk -> page mapping for evidence attribution)
- **Out of scope**: retrieval logic, reranking, evidence compression
- **Dependencies**: TASK-W2C (canonical corpus)

## 3. Implementation Plan

- Implemented `src/indexing/service.py` as the Wave 3A service surface for chunking/index preparation.
- Added indexing-focused tests and post-merge verification for the service contract.
- Merged task branch into `main` after quality-gate review and final integrated verification.

## 4. Working Notes

Chunking levels: page chunks for broad context, clause/heading chunks for precision, table blocks as independent units.
Critical invariant: every chunk must resolve to exact physical PDF page(s).
Qdrant embedded mode: no Docker, in-process, persistent storage. Named vectors for dense + sparse hybrid.

## 5. Outcome

**Result**: Completed on 2026-03-21. Wave 3A delivered the indexing service layer and dedicated test coverage, then merged to `main` as part of the recorded Wave 3 orchestration flow.  
**Next action**: Expose the merged indexing layer to TASK-W3D pipeline orchestration and any remaining benchmark/regression workflows.
