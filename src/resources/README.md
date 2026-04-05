# `src/resources/`

This subtree stores non-executable runtime assets rather than Python code. It is still documented here so the local structure is visible next to the executable packages.

## File graph

```text
resources/
├── configs/
│   └── baseline/
│       └── v001/
│           └── config.yaml
```

## File map

- `configs/baseline/v001/config.yaml`: Baseline W1A runtime configuration. It records the default competition phase, API settings, storage layout, ingestion and retrieval knobs, answer-routing policy, logging defaults, and the environment variables that can override them.
