# Task: TASK-W3A

## 1. Summary

**Title**: Chunking & hybrid indexing  
**Description**: Chunk canonical corpus respecting legal document structure; build BM25 + dense + metadata indices.  
**Status**: Done (baseline merged; runnable-completeness closed by W3D integration)
**Wave**: Wave 3 -- Parallel Baseline Build

## 2. Scope

- **In scope**:
  - Hierarchical chunking: page -> section -> clause -> microchunk + serialized table blocks
  - Each chunk preserves: page span, parent section/clause, neighboring headings, chunk_type
  - Qwen3-Embedding-0.6B batch embedding
  - Qdrant collection with named vectors: dense (Qwen3) + sparse (BM25)
  - Qdrant payload: doc_id, page_span, chunk_type, section, entities, dates
  - Page-parent map (chunk -> page mapping for evidence attribution)
- **Out of scope**: retrieval ranking logic, reranking, evidence compression
- **Dependencies**: TASK-W2C (canonical corpus)

## 3. Implementation Plan

- Implemented `src/indexing/service.py` as the Wave 3A service surface for chunking/index preparation.
- Added indexing-focused tests and post-merge verification for the service contract.
- Merged task branch into `main` after quality-gate review and final integrated verification.
- The integrated W3D submission path now reuses persisted index artifacts end-to-end after restart.
- No corrective follow-up remains inside W3A; full pipeline orchestration lives in W3D.

## 4. Working Notes

Chunking levels: page chunks for broad context, clause/heading chunks for precision, table blocks as independent units.
Critical invariant: every chunk must resolve to exact physical PDF page(s).
Qdrant embedded mode: no Docker, in-process, persistent storage. Named vectors for dense + sparse hybrid.
The original Wave 3A baseline used a custom sparse-encoding path that proved incomplete as a restartable runtime contract. The W3D runnable pipeline now treats any custom sparse state as compatibility-only, not target architecture.

## 5. Outcome

**Result**: Completed on 2026-03-21 as a baseline indexing layer and merged to `main`; the W3D runnable pipeline now confirms restartable reuse of the persisted artifacts.  
**Next action**: None for W3A; use as a stable baseline for post-baseline tracks.
