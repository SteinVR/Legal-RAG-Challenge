# `src/submission/`

Submission packaging, sync, validation gates, telemetry packing, and API client helpers live here. Package initializers and cache directories are intentionally omitted from the map.

## File graph

```text
submission/
├── api_client.py
├── packager.py
├── pipeline.py
├── submit_gate.py
├── sync.py
└── telemetry_packer.py
```

## File map

- `api_client.py`: Thin HTTPX-based client for the competition API. It handles document download and submission-status interactions.
- `packager.py`: Submission payload and code-archive packaging utilities. It builds the JSON payload, filters archive contents, and enforces bundle size limits.
- `pipeline.py`: End-to-end submission pipeline orchestration. It validates local artifacts, coordinates providers and retrieval, writes trace artifacts, and formats build results.
- `submit_gate.py`: Pre-submit validation gates for packaged submission bundles. It checks archive size, corpus completeness, and validation-policy compliance before upload.
- `sync.py`: Phase-aware local storage and sync orchestration. It manages metadata, deduplication, file copying, and directory snapshots for competition assets.
- `telemetry_packer.py`: Answer telemetry packing helpers. It serializes retrieval and answer metadata into the payload shape expected by downstream submission artifacts.
