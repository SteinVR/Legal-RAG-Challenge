# `scripts/`

Operational helper scripts used for environment bootstrap and smoke/audit workflows.

## File graph

```text
scripts/
├── 01b_install_opendataloader_runtime.sh
├── 02_download_models.sh
├── 06_build_submission.sh
├── audit_challenge_corpus.py
├── autoresearch_grounding_runner.py
├── autoresearch_keep.py
├── e2e_resume.py
├── postprocess_grounding_ledger.py
└── smoke_test_w4e.py
```

## File map

- `01b_install_opendataloader_runtime.sh`: Install OpenDataLoader runtime prerequisites.
- `02_download_models.sh`: Pull required local model artifacts for offline execution.
- `06_build_submission.sh`: Run submission build workflow wrapper.
- `audit_challenge_corpus.py`: Corpus audit utility for data/coverage sanity checks.
- `autoresearch_grounding_runner.py`: Retrieval-only grounding benchmark runner for autoresearch loops.
- `autoresearch_keep.py`: Decision logger for autoresearch runs; records agent-selected status and snapshots configs on explicit `keep`.
- `e2e_resume.py`: Checkpointed warmup/final E2E runner that writes one structured run bundle per execution.
- `postprocess_grounding_ledger.py`: Per-question grounding ledger and bucket summary generator from `submission.json`.
- `smoke_test_w4e.py`: Smoke test harness for the W4E pipeline flow.

## Warmup Run Bundles

Canonical warmup analysis outputs now live under `artifacts/warmup_runs/`. This replaces the old tracked `data/warmup/submission_*` run directories; because `artifacts/` is ignored, these bundles are local or externally archived evidence, not committed repo contents.

```text
artifacts/warmup_runs/
├── summary_runs.tsv
├── top_failures.tsv
└── runs/
    └── <run_id>/
        ├── submission/
        ├── eval/
        ├── grounding/
        └── manifest.json
```

- `submission/`: `submission.json`, `qa_checkpoint.json`, `trace_manifest.json`, `traces/`, `code_archive.zip`
- `eval/`: benchmark/validation outputs and score checkpoints
- `grounding/`: per-run grounding ledger plus extended summary metrics
- `summary_runs.tsv` / `top_failures.tsv`: cross-run warmup tables for comparisons and persistent failures

Grounding-only postprocess bundles may omit `submission/` and `eval/`; in that case `manifest.json` marks `run_kind="grounding_only"` and points to the source `submission.json` used for postprocessing.

## Autoresearch Decision Log

Use this command immediately after each autoresearch runner execution:

```bash
PYTHONPATH=. .venv/bin/python scripts/autoresearch_keep.py \
  --run-id apr06-grounding \
  --status keep \
  --run-log run.log \
  --config-path configs/baseline/v001/config.yaml \
  --metric-key grounding_mean \
  --keep-ref 0a8446d \
  --promote-config-path configs/baseline/v001/config.yaml \
  --description "case budget sweep candidate"
```

Tracked outputs:
- `analysis/grounding/keep_state.json`
- `analysis/grounding/keep_history.tsv`
- `analysis/grounding/kept_configs/<run_id>/*.yaml` (only for `status=keep`)
