# `scripts/`

Canonical operator scripts for local setup, smoke checks, corpus/index builds, submission generation, and warmup analysis.

## Canonical Setup Order

```bash
./scripts/01_install_deps.sh
./scripts/02_download_models.sh
./scripts/00_check_env.sh
./scripts/01b_install_opendataloader_runtime.sh --verify-only
```

For normal structural ingestion with Docling hybrid enrichment, start the backend before `parse-corpus`:

```bash
.venv/bin/opendataloader-pdf-hybrid \
  --host 127.0.0.1 \
  --port 5002 \
  --device cpu \
  --force-ocr \
  --log-level info
```

The baseline config expects `opendataloader_hybrid_url: http://localhost:5002`.

## File Graph

```text
scripts/
├── 00_check_env.sh
├── 00_repair_gpu_runtime.sh
├── 01_install_deps.sh
├── 01b_install_opendataloader_runtime.sh
├── 02_download_models.sh
├── 03_lint_and_test.sh
├── 04_parse_corpus.sh
├── 05_build_indices.sh
├── 06_build_submission.sh
├── 07_validate_submission.sh
├── audit_challenge_corpus.py
├── autoresearch_grounding_runner.py
├── autoresearch_keep.py
├── e2e_resume.py
├── postprocess_grounding_ledger.py
└── smoke_test_w4e.py
```

## File Map

- `00_check_env.sh`: Preflight for `.venv`, `.env`, provider key visibility, GPU/CUDA, model caches, OpenDataLoader/Docling runtime, and warmup data presence.
- `00_repair_gpu_runtime.sh`: Recreate missing NVIDIA device nodes with `nvidia-modprobe`, then verify CUDA from Python.
- `01_install_deps.sh`: Canonical dependency installer. Creates `.venv` if needed, installs project extras, Paddle runtime, OpenDataLoader hybrid extras, and validates imports/CLIs.
- `01b_install_opendataloader_runtime.sh`: Package-based OpenDataLoader/Docling runtime verifier and repair helper. No vendored `external/opendataloader-pdf` build is used.
- `02_download_models.sh`: Download/verify Qwen embedder, Qwen reranker, and PaddleOCR model caches.
- `03_lint_and_test.sh`: Shell syntax, ruff, compileall, and pytest quality gate.
- `04_parse_corpus.sh`: Wrapper for `parse-corpus` with config-aware phase paths and artifact checks.
- `05_build_indices.sh`: Wrapper for `build-indices` with corpus prerequisite and index artifact checks.
- `06_build_submission.sh`: Wrapper for `build-submission`, provider preflight, checkpointing, and submission artifact checks.
- `07_validate_submission.sh`: Wrapper for `validate-submission` against phase-local questions/documents or explicit paths.
- `audit_challenge_corpus.py`: Corpus audit utility for data/coverage sanity checks.
- `autoresearch_grounding_runner.py`: Retrieval-only grounding benchmark runner for autoresearch loops.
- `autoresearch_keep.py`: Decision logger for autoresearch runs; records keep/discard state and config snapshots.
- `e2e_resume.py`: Checkpointed warmup/final E2E runner that writes one structured run bundle per execution.
- `postprocess_grounding_ledger.py`: Per-question grounding ledger and bucket summary generator from `submission.json`.
- `smoke_test_w4e.py`: Smoke test harness for the curated warmup QA slice.

## Pipeline Wrappers

```bash
./scripts/04_parse_corpus.sh --phase warmup --force
./scripts/05_build_indices.sh --phase warmup --force
./scripts/06_build_submission.sh --phase warmup --checkpoint-every 1
./scripts/07_validate_submission.sh --phase warmup
```

Use `--phase warmup-ocr` for the OCR stress-test corpus. The wrapper paths are resolved through `tools/operator_context.py`, so they follow the active config and phase override.

## Warmup Run Bundles

Canonical warmup analysis outputs live under `artifacts/warmup_runs/`. This replaces old tracked `data/warmup/submission_*` run directories; `artifacts/` is ignored, so these bundles are local or externally archived evidence.

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
- `analysis/grounding/kept_configs/<run_id>/*.yaml` only for `status=keep`
