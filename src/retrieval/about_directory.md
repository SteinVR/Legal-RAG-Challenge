# About This Directory
Purpose: Hybrid evidence retrieval and page-grounding layer.
Contains: Qdrant hybrid search, reranking, evidence compression, page lifting, and the composed retrieval service, including optional query-metadata guidance handoff from answering.
Start Here: `service.py` for orchestration, then `hybrid_search.py`, `reranker.py`, `evidence_compressor.py`, and `page_lifter.py`.
Key Files/Dirs: `service.py`, `hybrid_search.py`, `reranker.py`, `evidence_compressor.py`, `page_lifter.py`.
Notes: This directory assumes indexing artifacts already exist under `data/{phase}/index/`; query metadata is soft guidance only and must not hard-filter away multi-document retrieval breadth.
