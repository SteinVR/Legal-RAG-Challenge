# About This Directory
Purpose: Hybrid evidence retrieval and page-grounding layer.
Contains: Qdrant hybrid search, reranking, evidence compression, page lifting, and the composed retrieval service.
Start Here: `service.py` for orchestration, then `hybrid_search.py`, `reranker.py`, `evidence_compressor.py`, and `page_lifter.py`.
Key Files/Dirs: `service.py`, `hybrid_search.py`, `reranker.py`, `evidence_compressor.py`, `page_lifter.py`.
Notes: This directory assumes indexing artifacts already exist under `data/{phase}/index/`.
