# `src/answering/`

This package owns answer routing, grounding, and cross-case decomposition. Package initializers and cache directories are intentionally omitted from the map.

## File graph

```text
answering/
├── decomposition.py
├── page_attribution.py
└── service.py
```

## File map

- `decomposition.py`: Cross-case decomposition and recomposition for comparative multi-document questions. It detects case references, decides when to decompose, builds subquestions, merges evidence pages, and turns subanswers back into a final answer with a decomposition trace.
- `page_attribution.py`: Two-pass page attribution helpers for grounding precision. It builds candidate pages from retrieval hits, prunes boilerplate and title pages, finalizes page references, and emits page attribution traces.
- `service.py`: Main answering service and routing layer. It defines the answer schemas and metadata models, extracts query metadata, performs deterministic extraction, calls the provider layer, validates grounding, and applies typed guardrails for booleans, numbers, names, dates, and free-text answers.
