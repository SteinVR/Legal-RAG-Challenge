# `src/indexing/`

Hybrid index construction lives here. Package initializers and cache directories are intentionally omitted from the map.

## File graph

```text
indexing/
└── service.py
```

## File map

- `service.py`: Hybrid indexing service for canonical legal corpora. It builds chunk families, dense embedder wrappers, sparse encoders, manifest metadata, and the chunk serialization logic used to produce retrieval-ready indices.
