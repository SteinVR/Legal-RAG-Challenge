# About This Directory
Purpose: Corpus-to-index transformation layer.
Contains: `service.py`, which owns chunk generation, dense embedding, BM25 sparse encoding, Qdrant persistence, and index manifests.
Start Here: Open `service.py`; the current indexing implementation is concentrated there.
Key Files/Dirs: `service.py`.
Notes: Older architecture notes may mention separate chunker or embedder modules, but the current repo keeps those responsibilities in one file.
