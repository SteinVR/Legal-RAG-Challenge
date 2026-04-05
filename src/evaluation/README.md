# `src/evaluation/`

Local evaluation, validation, and benchmark assembly helpers live here. Package initializers and cache directories are intentionally omitted from the map.

## File graph

```text
evaluation/
├── contracts.py
├── goldset.py
├── scorer.py
└── validator.py
```

## File map

- `contracts.py`: Evaluation and submission contract models. It defines answer types, benchmark metadata, page references, validation reports, score reports, and helpers for loading and normalizing submission, question, reference, and assistant-score records.
- `goldset.py`: Gold-set sharding, review validation, and benchmark assembly utilities. It builds shard manifests, summaries, bundles, validation checks, and combined benchmark datasets from reviewed question sets and reference records.
- `scorer.py`: Deterministic local scoring logic for challenge-style submissions. It computes deterministic, assistant, grounding, and TTFT metrics, then aggregates them into a score report.
- `validator.py`: Local submission validator that mirrors the public challenge contract. It builds corpus registries, validates answer structure and page references, extracts retrieved pairs and TTFT, and returns validation issues and reports.
