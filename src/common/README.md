# `src/common/`

Shared config, logging, and schema models live here. Package initializers and cache directories are intentionally omitted from the map.

## File graph

```text
common/
├── config.py
├── runtime_logging.py
└── schemas.py
```

## File map

- `config.py`: YAML configuration loading with environment-aware overrides. It defines the app, API, storage, download, evaluation, ingestion, answering, page attribution, indexing, retrieval, decomposition, runtime, and logging settings models, plus path resolution and config materialization helpers.
- `runtime_logging.py`: Shared runtime logging setup and structured event helpers. It configures console and JSONL output, tracks runtime context, resolves log paths, and exposes one-line event logging helpers for stage boundaries.
- `schemas.py`: Shared typed models for the foundation and ingestion layers. It defines phase, triage, parser route, block, page, corpus, manifest, and question records used across ingestion, indexing, retrieval, evaluation, and submission.
