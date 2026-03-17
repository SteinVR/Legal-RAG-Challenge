# Task: TASK-004

## 1. Summary

**Title**: Structure-aware chunking & hybrid index building  
**Description**: Chunk canonical corpus respecting legal document structure; build BM25 + dense + metadata indices.  
**Status**: Planned

## 2. Scope

- **In scope**:
  - Hierarchical chunking: page -> section -> clause -> microchunk + serialized table blocks
  - Each chunk preserves: page span, parent section/clause, neighboring headings, chunk_type
  - Qwen3-Embedding-0.6B batch embedding
  - Qdrant collection with named vectors: dense (Qwen3) + sparse (BM25)
  - Qdrant payload: doc_id, page_span, chunk_type, section, entities, dates
  - Page-parent map (chunk -> page mapping for evidence attribution)
- **Out of scope**: retrieval logic, reranking, evidence compression
- **Dependencies**: TASK-003 (canonical corpus)

## 3. Implementation Plan



## 4. Working Notes

Chunking levels: page chunks for broad context, clause/heading chunks for precision, table blocks as independent units.
Critical invariant: every chunk must resolve to exact physical PDF page(s).
Qdrant embedded mode: no Docker, in-process, persistent storage. Named vectors for dense + sparse hybrid.

## 5. Outcome

**Result**: [Pending]  
**Next action**: implement after TASK-003
