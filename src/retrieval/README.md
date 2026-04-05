# `src/retrieval/`

Hybrid search, reranking, evidence compression, and page grounding live here. Package initializers and cache directories are intentionally omitted from the map.

## File graph

```text
retrieval/
├── evidence_compressor.py
├── hybrid_search.py
├── page_lifter.py
├── reranker.py
└── service.py
```

## File map

- `evidence_compressor.py`: Evidence compression and support-page validation for retrieval results. It scores candidate support pages and keeps the compressed evidence list aligned with downstream grounding logic.
- `hybrid_search.py`: Scale-safe rank-fusion hybrid search backend. It wraps Qdrant search, manifest loading, metadata boosts, normalization, and candidate fusion.
- `page_lifter.py`: Chunk-to-page lifting utilities for retrieval grounding. It converts retrieval chunks into page-level references and lifted page summaries.
- `reranker.py`: Qwen3-oriented reranking layer. It covers backend loading, candidate scoring, and lexical fallback behavior when the preferred reranker is unavailable.
- `service.py`: Retrieval service contract and orchestration layer. It ties together search, reranking, evidence compression, page grounding, and question-class budget policy.
