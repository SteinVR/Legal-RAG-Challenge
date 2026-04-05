# `src/`

This directory is the composition root for the CLI and all pipeline stages. The code is split by stage so each subdirectory can be read independently.

## File graph

```text
src/
├── main.py
├── answering/
├── common/
├── evaluation/
├── indexing/
├── ingestion/
├── providers/
├── resources/
├── retrieval/
└── submission/
```

## File map

- `main.py`: CLI entrypoint. Builds the argparse surface, loads config and environment values, and wires the ingestion, indexing, answering, evaluation, and submission commands.
- `answering/`: Answer routing, typed extraction, page attribution, and cross-case decomposition. See `answering/README.md`.
- `common/`: Shared config, logging, and schema models. See `common/README.md`.
- `evaluation/`: Local validation, scoring, benchmark assembly, and contract models. See `evaluation/README.md`.
- `indexing/`: Hybrid index construction and chunk generation. See `indexing/README.md`.
- `ingestion/`: PDF parsing, OCR, sidecar handling, routing, normalization, and corpus assembly. See `ingestion/README.md`.
- `providers/`: Provider protocols and Codex-backed implementations. See `providers/README.md`.
- `resources/`: Runtime config assets and design notes. See `resources/README.md`.
- `retrieval/`: Hybrid search, reranking, evidence compression, and page grounding. See `retrieval/README.md`.
- `submission/`: Submission packaging, sync, validation gates, telemetry packing, and API client helpers. See `submission/README.md`.
