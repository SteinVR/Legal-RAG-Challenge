# Project Architecture: Agentic-RAG-Challenge

> Single source of truth for top-level project logic, design, and behavior.
>
> Memory Bank chain:
> - `memory_bank/ARCHITECTURE.md` - top-level architecture overview
> - `memory_bank/specs/` and `memory_bank/tasks/` - frozen specs and working journals

---

## 1. Project Idea and Scoring

Competition-grade legal RAG pipeline for Agentic RAG Legal Challenge 2026.

Core problem:
- Given approximately 300 legal PDFs and approximately 900 questions
- Produce grounded, accurate answers with complete telemetry

Scoring formula:
- `Total = (0.7 * S_det + 0.3 * S_asst) * G * T * F`
- `S_det`: deterministic answer quality (`number`, `boolean`, `name`, `names`, `date`, `null`)
- `S_asst`: free-text quality
- `G`: grounding score (multiplicative, high impact)
- `T`: telemetry validity factor (local scorer: `0.9` when answer telemetry is malformed, else `1.0`)
- `F`: TTFT factor (local scorer bins: `<1s -> 1.05`, `1-2s -> 1.02`, `2-3s -> 1.00`, `>3s -> local linear proxy from 0.99 down to 0.85`)

Project philosophy:
- Grounding-first system
- Retrieve broadly, emit narrowly
- Treat the system as an evidence attribution engine, not a chatbot
- Operational submission limits: warmup submissions are capped at 10, private submissions at 2

---

## 2. Form Factor

- Type: Python CLI batch pipeline
- Interface: `src/main.py` subcommands with config/env-driven execution
- Deployment: local execution on developer machine
- Runtime profile: phase-local artifacts under `data/{phase}/...`

---

## 3. Operational Workflow

1. Sync phase data (`download-questions`, `download-documents`, `sync`)
2. Parse corpus (`parse-corpus`) into canonical page records plus sidecars
3. Build hybrid index (`build-indices`) with dense+sparse vectors in embedded Qdrant
4. Run QA pipeline (`build-submission`):
- retrieve candidates
- rerank
- compress evidence
- route by answer type
- solve (structured and/or deterministic/free-text)
- pack telemetry
5. Validate locally (`validate-submission`, plus submit gate during build)
6. Optional local scoring/benchmark (`score-submission`, `benchmark-summary`, consistency/compare commands)
7. Submit bundle (`submit`, `submission-status`)

---

## 4. Technology Stack

- Language: Python 3.11+
- PDF parsing: PyMuPDF (`fitz`) with page triage and parser routing
- OCR: PaddleOCR v3 `.predict()` via local adapter (`src/ingestion/ocr_engine.py`)
- Structural extraction: OpenDataLoader adapter for tagged/hybrid routes
- Embeddings: `Qwen/Qwen3-Embedding-0.6B`
- Index-time embedder uses `prompt_name="document"`
- Query-time embedder uses `prompt_name="query"`
- Reranker: `Qwen/Qwen3-Reranker-0.6B` as CausalLM (`AutoModelForCausalLM`)
- Scoring method: yes/no next-token probability
- Lexical sparse retrieval: in-repo `BM25SparseEncoder` (custom BM25 implementation)
- Vector store: embedded Qdrant (`qdrant_client`)
- Generation backend: OpenAI Responses API (`/responses`) via Codex provider
- Default generation model: `gpt-5.4-mini`
- Config management: `src/common/config.py` + `configs/baseline/v001/config.yaml`
- Data formats:
- canonical corpus: JSONL
- manifests/config/reports: JSON/YAML
- debug parse artifacts: Markdown
- raw parser outputs: JSON sidecars
- Competition API integration: custom thin `httpx` client (`src/submission/api_client.py`)

---

## 5. Component Topology

Detailed ownership and low-level behavior live in `memory_bank/component_design.md`.
This section reflects the currently implemented module layout.

### A. Ingestion (`src/ingestion/`)
- Responsibility: PDF to canonical page corpus with parser provenance, structural/table blocks, and manifests
- Main modules:
- `service.py` - parse orchestration, artifact completeness checks, raw sidecar writes
- `pdf_parser.py` - native parse plus OCR fallback plus parser routing
- `ocr_engine.py` - PaddleOCR adapter
- `parser_routing.py` - route decisions (`tagged`, `hybrid`, `local_only`); missing OpenDataLoader is fatal
- `opendataloader_adapter.py` - OpenDataLoader bridge and sidecar construction
- `sidecars.py` - sidecar IO
- `structural_normalizer.py` - structural normalization
- `table_serializer.py` - table serialization to retrieval blocks
- `page_triage.py` - quality signals and triage labels
- `corpus_builder.py` - canonical records, page map, manifest, debug markdown
- Key outputs:
- `corpus.jsonl`
- `page_map.json`
- `corpus_manifest.json`
- `debug/*.md`
- `raw_parse/{parser}/*.json`

### B. Indexing (`src/indexing/`)
- Responsibility: build structure-aware chunks and dense+sparse hybrid index artifacts
- Main implementation: `service.py`
- Supports chunk families: `page`, `section`, `clause`, `microchunk`, `table`
- Persists:
- embedded Qdrant collection
- `index_manifest.json`
- `sparse_encoder_state.json`
- `page_parent_map.json`

### C. Retrieval (`src/retrieval/`)
- Responsibility: hybrid retrieval, rank fusion, reranking, evidence compression, page grounding
- Main modules:
- `hybrid_search.py` - Qdrant backend + RRF fusion + metadata boosts
- `reranker.py` - Qwen reranker backend + lexical fallback
- `evidence_compressor.py` - support-page preserving evidence selection
- `page_lifter.py` - chunk-to-page lifting utilities
- `service.py` - retrieval orchestration, budgets, rerank thresholding, diagnostics
- Runtime controls include:
    - answer-type evidence budgets
    - question-class budgets
    - rerank score threshold
    - optional parent-page expansion

### D. Answering (`src/answering/`)
- Responsibility: retrieval-first answering with schema validation, deterministic extraction, page attribution, decomposition
- Current topology:
    - `service.py` contains:
    - answer schemas and `ANSWER_SCHEMA_REGISTRY`
    - query metadata extraction
    - deterministic typed extraction logic
    - structured-provider and free-text solve flows
    - confidence threshold handling
    - `page_attribution.py` contains two-pass page attribution and trace assembly
    - `decomposition.py` contains cross-case decomposition and deterministic recomposition
- Decomposition trigger:
    - enabled in config
    - answer type in `{boolean, name}`
    - at least 2 DIFC-style case references in question

### E. Evaluation (`src/evaluation/`)
- Responsibility: local contract validation, scoring, benchmark slicing, run-comparison/consistency tools
- Main modules:
    - `contracts.py`
    - `validator.py`
    - `scorer.py`
    - `goldset.py`
    - `dev_benchmark/`

### F. Submission (`src/submission/`)
- Responsibility: phase sync, QA pipeline orchestration, telemetry packing, packaging, submit gate, API submission
- Main modules:
    - `sync.py` - phase-local question/document sync and sync manifest
    - `pipeline.py` - build-submission orchestration
    - `telemetry_packer.py` - answer telemetry payload construction
    - `packager.py` - `submission.json` and `code_archive.zip`
    - `submit_gate.py` - local pre-submit gate (schema+archive constraints)
    - `api_client.py` - remote submission/status client
    - Build outputs:
    - `submission.json`
    - `code_archive.zip`
    - `trace_manifest.json`
    - `traces/*.json`

### G. Providers (`src/providers/`)
- Responsibility: provider protocols and concrete Codex/OpenAI implementations
- Current modules:
    - `base.py` - `AnsweringProvider` and `StructuredOutputProvider` protocols
    - `codex_provider.py` - concrete answering + structured providers, retry/parsing/schema enforcement
    - `__init__.py` - package exports

### H. Common (`src/common/`)
- `config.py` - typed config models, env expansion/overrides, defaults
- `schemas.py` - shared Pydantic models for sync/ingestion contracts
- `runtime_logging.py` - structured runtime logging setup and event helper

### I. Operator Scripts (`scripts/`)
- Numbered pipeline scripts:
    - `00_check_env.sh` - preflight environment check (`.venv/.env`, provider keys, GPU/CUDA, model caches, warmup data)
    - `00_repair_gpu_runtime.sh` - NVIDIA runtime recovery helper (`nvidia-modprobe`, device nodes, CUDA checks in `torch` and `paddle`)
    - `01_install_deps.sh` - Python dependency installer (`uv`), editable package install, `paddlepaddle-gpu` setup, import verification
    - `01b_install_opendataloader_runtime.sh` - manual OpenDataLoader runtime bootstrap (system deps, Maven build, Python wrapper install, smoke parse)
    - `02_download_models.sh` - retrieval model downloader (`Qwen3-Embedding-0.6B`, `Qwen3-Reranker-0.6B`) with optional `--verify` smoke path
    - `03_lint_and_test.sh` - local quality gate (`bash -n`, `ruff`, `compileall`, `pytest`)
    - `04_parse_corpus.sh` - wrapper for `parse-corpus` with phase-aware paths and output artifact validation
    - `05_build_indices.sh` - wrapper for `build-indices` with index artifact validation (`index_manifest.json`, sparse state, `qdrant/`)
    - `06_build_submission.sh` - wrapper for `build-submission` with preflight checks and submission bundle validation
    - `07_validate_submission.sh` - wrapper for `validate-submission`, including fallback discovery of latest local `submission.json`
    - Additional utilities:
    - `smoke_test_w4e.py` - fast end-to-end smoke run on a small question slice to catch retrieval/answering regressions
    - `audit_challenge_corpus.py` - corpus auditing utility (documents/questions/archive coverage and summary report)
    - `download_cuda_wheels.sh` - helper to pre-download CUDA wheel files for faster/offline dependency installation

---

## 6. CLI and Artifact Organization

- Entry point: `src/main.py`
- Commands:
- sync: `download-questions`, `download-documents`, `sync`, `sync-phase`
- pipeline: `parse-corpus`, `build-indices`, `build-submission`
- submission: `submit`, `submission-status`
- local quality: `validate-submission`, `score-submission`
- benchmark: `benchmark-summary`, `compare-benchmark-runs`, `analyze-benchmark-consistency`
- Config:
- primary: `configs/baseline/v001/config.yaml`
- packaged default: `src/resources/configs/baseline/v001/config.yaml` is used only when the repo-root config is unavailable, such as packaged/imported execution
- Warmup run bundles: structured e2e/analysis evidence is written under `artifacts/warmup_runs/runs/<run_id>/`; `artifacts/` is ignored, so `memory_bank/STATE.md` records historical metrics but should not be treated as a committed artifact manifest
- Phase-local data layout:
    - `data/{phase}/questions/`
    - `data/{phase}/documents/`
    - `data/{phase}/corpus/`
    - `data/{phase}/index/`
    - `data/{phase}/manifests/`
    - `data/dev/` for local benchmark/dev reference datasets
    - `tools/operator_context.py` for operator helper context

---

## 7. Core Data Contracts

- `QuestionRecord` (`src/common/schemas.py`)
- `CanonicalPageRecord`, `PageMapRecord`, `CorpusParseManifest`
- `QueryMetadata`, `AnswerResult`, `PageAttributionTrace` (`src/answering/service.py`, `src/answering/page_attribution.py`)
- Structured answer schemas in `ANSWER_SCHEMA_REGISTRY`
- `SubQuestionResult`, `DecompositionResult` (`src/answering/decomposition.py`)
- `RetrievedChunk`, `RetrievalResult` (`src/retrieval/service.py`)
- Telemetry payload (`src/submission/telemetry_packer.py`):
- timing: `ttft_ms`, `tpot_ms`, `total_time_ms`
- retrieval: final and trace-level page references plus diagnostics
- usage: input/output tokens
- model name
- Submission payload:
    - `architecture_summary`
    - `answers[]` with `question_id`, `answer`, `telemetry`

---

## 8. Conventions and Runtime Guarantees

- Every emitted evidence page must map to physical PDF pages
- Build-submission validates locally before final bundle acceptance
- Submission gate enforces schema/coverage/grounding shape and archive constraints
- Runtime logs are structured (JSONL) under `logs/project/runtime/{phase}/`
- Config is centralized and typed; env overrides are explicit in `src/common/config.py`
- Known ambiguity is still configurable:
- default is `allow_empty` (unanswerable answers may emit `retrieved_chunk_pages: []`)
- switch to `require_non_empty` when enforcing non-empty retrieval pages for unanswerable outputs
