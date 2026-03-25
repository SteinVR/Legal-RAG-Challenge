# Project Architecture: Agentic-RAG-Challenge

> Single source of truth for the project's logic, design, and behavior.
>
> **Wave 4 canonical target architecture**: `docs/unified_document_processing_architecture.md`. This document combines opendataloader-pdf, external/RAG-Challenge-2, and the current project into a unified document processing design. A review is at `docs/Document_Processing_Architecture_Review.md`. The Wave 4 task specs in `memory_bank/tasks/TASK-W4*.md` are the authoritative execution plans derived from that architecture.

---

## 1. Project Idea & Philosophy

Competition-grade legal RAG pipeline for Agentic RAG Legal Challenge 2026.

**Core problem**: given ~300 heterogeneous legal PDFs and 900 questions, produce grounded, accurate answers with telemetry.

**Scoring formula**: `Total = (0.7 * S_det + 0.3 * S_asst) * G * T * F`
- `S_det` -- deterministic accuracy (number/boolean/name/names/date/null)
- `S_asst` -- free-text LLM judge score (5 criteria, max 280 chars)
- `G` -- grounding (F-beta, beta=2.5; **multiplicative** -- most critical)
- `T` -- telemetry factor (0.9 per malformed answer)
- `F` -- TTFT factor (<1s: 1.05, 1-2s: 1.02, 2-3s: 1.00, >3s: penalty to 0.85)

**Philosophy**: grounding-first. Search broadly, report narrowly. Offline preprocessing is free; only per-answer TTFT is scored. The system is an evidence attribution engine, not an "agentic chatbot".

**Submission limits**: 10 warmup, 2 private. Every submission must be validated locally first.

---

## 2. Project Body (Form Factor)

- **Type**: CLI batch pipeline (Python)
- **Interface**: CLI with config path argument; pull-model API interaction
- **Deployment**: local execution on developer machine (RTX 4060 8GB, Ryzen 7 7840H)

---

## 3. User Workflow (Operational Principle)

1. **Download**: fetch documents and questions via competition API client.
2. **Ingest**: parse PDFs (PaddleOCR-VL-1.5 + native text), build canonical corpus with page map.
3. **Index**: build hybrid indices (BM25 + dense embeddings + metadata).
4. **Run pipeline**: for each question -- retrieve candidates -> rerank -> compress evidence -> route by answer_type -> solve/generate -> pack telemetry.
5. **Validate**: run local evaluator and submission validator.
6. **Submit**: upload submission.json + code_archive.zip via API.

---

## 4. Technology Decisions

- **Language**: Python 3.11+
- **OCR / Document Parsing**: PaddleOCR v3 `.predict()` API (primary), PyMuPDF/pdfplumber (native text fast path)
- **Embeddings**: Qwen3-Embedding-0.6B (32K context, instruction-aware, MRL). Uses `prompt_name="document"` at index time (`build_dense_embedder`), `prompt_name="query"` at retrieval time (`build_query_embedder`).
- **Reranker**: Qwen3-Reranker-0.6B loaded as `AutoModelForCausalLM`. Scoring: yes/no next-token probability via `log_softmax(logits[:, -1, [no_id, yes_id]])[:, 1].exp()`. Not a sequence classifier.
- **Lexical search**: BM25 (rank-bm25 or tantivy-py)
- **Vector store**: Qdrant embedded mode (dense + sparse vectors, payload filtering, persistence)
- **Generation backend**: OpenAI API (primary); provider abstraction for fallback. Default model: `gpt-5.4-mini` (reasoning model; `DEFAULT_CODEX_MODEL` in `src/providers/codex_provider.py`). Reasoning effort is configurable per answer type.
- **Canonical data format**: JSONL (structured) + Markdown (debug); raw parse artifacts use JSON sidecars
- **Config management**: versioned YAML configs under `configs/`
- **Competition API client**: `arlc` SDK or custom thin wrapper

---

## 5. Component Design

Detailed implementation notes live in `docs/component_design.md`. This section stays intentionally short so the project has one detailed component document instead of two drifting copies.

### A. Ingestion (`src/ingestion/`) — 10 modules
- **Responsibility**: PDF → canonical page-level corpus with structural provenance, tables, quality metadata, JSON sidecars, and parse manifests.
- **Key modules**: `service.py` (orchestration), `pdf_parser.py` (native + OCR), `parser_routing.py` (W4C route decisions: tagged/hybrid/local_only/baseline_fallback), `opendataloader_adapter.py` (W4C structural parse via Java bridge), `sidecars.py` (JSON sidecar I/O), `structural_normalizer.py` (heading/list/caption normalization), `ocr_engine.py` (PaddleOCR GPU adapter), `page_triage.py`, `table_serializer.py`, `corpus_builder.py`.
- **Parser provenance**: all pages carry `parser_provenance` field (e.g. `opendataloader:tagged`, `pymupdf:native`).

### B. Indexing (`src/indexing/`)
- **Responsibility**: structure-aware chunking plus dense/sparse local index construction in embedded Qdrant.
- Token-aware chunk sizing, multi-level chunking (page, section, clause, microchunk, table).

### C. Retrieval (`src/retrieval/`) — 5 modules
- **Responsibility**: hybrid search, reranking, evidence compression, question-class-aware budget routing, and chunk-to-page grounding.
- **Key modules**: `hybrid_search.py` (Qdrant backend + RRF fusion + soft entity boost from W4B query metadata), `reranker.py` (Qwen3 causal LM scoring), `evidence_compressor.py`, `page_lifter.py`, `service.py`.

### D. Answering (`src/answering/`) — 3 modules
- **Responsibility**: retrieval-first, schema-first typed solving stack:
  1. Retrieval and evidence packaging (solver-ready, page-stable bundles from W4D).
  2. Schema-bound typed solving — structured outputs per Pydantic answer-type schema via provider with reasoning effort controls (W4B).
  3. Two-pass page attribution — Pass A candidate pruning, Pass B post-answer finalization (W4A).
  4. Cross-case decomposition — rule-based trigger, per-case sub-questions, deterministic recomposition (W4E).
- **Key modules**: `service.py` (schema registry, query metadata extraction, structured solver), `page_attribution.py` (Pass A/B, boilerplate suppression), `decomposition.py` (trigger, decompose, recompose).

### E. Evaluation (`src/evaluation/`)
- **Responsibility**: local validation, scoring, dev benchmark slicing, and regression analysis.

### F. Submission (`src/submission/`) — 6 modules
- **Responsibility**: phase sync, pipeline orchestration (with decomposition routing), telemetry packing, packaging, and submit-time checks.
- **Pipeline integration**: `_answer_question()` in `pipeline.py` routes to decomposition when `config.decomposition.enabled=True` and question has 2+ cross-case refs.

### G. Providers (`src/providers/`) — 2 modules
- **Responsibility**: free-text and structured-output provider abstraction.
- **Key**: `codex_provider.py` supports both `generate()` (free-text) and `generate_structured()` (schema-bound with reasoning effort). Uses OpenAI Responses API (`/responses`). Includes `_strict_openai_schema()` post-processor for Pydantic→OpenAI strict mode compatibility.

### H. Common (`src/common/`) — 3 modules
- **Responsibility**: shared config, schema contracts, and runtime logging.
- **Config additions (W4)**: `DecompositionSettings` (W4E), `PageAttributionSettings` (W4A), `IndexingSettings` with token-aware chunking, `RetrievalSettings` with question-class budgets.

### I. Operator Scripts (`scripts/`)
- **Responsibility**: reproducible numbered shell pipeline for full baseline execution on a fresh machine.
- **Scripts**: `00_check_env` → `00_repair_gpu_runtime` → `01_install_deps` → `02_download_models` → `03_lint_and_test` → `04_parse_corpus` → `05_build_indices` → `06_build_submission` → `07_validate_submission`.
- **Smoke test**: `scripts/smoke_test_w4e.py` — 5-question e2e verification with decomposition.
- Each script is idempotent, self-documenting, and exits non-zero on failure.

See `memory_bank/component_design.md` for real module ownership, artifact paths, current limitations, and test anchors.

---

## 6. Code Organization Pattern

- `src/main.py` — CLI entrypoint: sync, parse, build-indices, build-submission, validation, scoring, benchmark
- `src/common/config.py` — config loading; settings: `AnsweringSettings`, `PageAttributionSettings`, `DecompositionSettings`, `IndexingSettings`, `RetrievalSettings`, etc.
- `src/common/schemas.py` — all data models (Pydantic): `CanonicalPageRecord`, `QuestionRecord`, `PageMapRecord`, etc.
- `src/common/runtime_logging.py` — structured JSON logging and event helpers
- `configs/baseline/v001/` — baseline config YAML
- `data/{warmup,final}/` — phase-isolated corpus, index, and raw_parse sidecars
- `data/dev/` — dev gold/silver question sets
- `scripts/` — numbered operator scripts + `smoke_test_w4e.py`
- `tools/` — developer utilities (`operator_context.py`)

---

## 7. Core Data Models

- **Page** (`CanonicalPageRecord`): doc_id, page_number, text, source_mode, parse_status, quality_score, quality_flags, blocks, table_ids, parser_provenance, triage_label
- **Chunk**: chunk_id, text, doc_id, page_span, parent_section, chunk_type, metadata (token count, provenance)
- **Question** (`QuestionRecord`): id, question, answer_type
- **QueryMetadata**: legal_entities (case_id, statute_id), document_title_cues, likely_multi_document
- **AnswerResult**: question_id, answer (typed), confidence, evidence_pages, page_trace, model_name
- **PageAttributionTrace**: raw_retrieved_chunk_pages → pass_a_pages → solver_reported_pages → final_emitted_pages, validation_action, collapsed_answer
- **Structured schemas** (`ANSWER_SCHEMA_REGISTRY`): BooleanAnswerSchema, NumberAnswerSchema, NameAnswerSchema, NamesAnswerSchema, DateAnswerSchema, FreeTextAnswerSchema — each with is_answerable, final_answer, relevant_pages, reasoning_summary, confidence
- **Decomposition** (`SubQuestionResult`, `DecompositionResult`): entity_id, sub-question, sub-answer, recomposed final
- **RetrievalResult**: question_id, query, answer_type, evidence_chunks, retrieved_chunk_pages, diagnostics
- **Telemetry**: timing (ttft_ms, tpot_ms, total_time_ms), retrieval (retrieved_chunk_pages), usage (input/output tokens), model_name
- **Submission**: architecture_summary, answers[]

---

## 8. Key Conventions & Logging

- **Modularity**: each pipeline stage is independently runnable and testable.
- **Page attribution**: every chunk traces back to physical PDF page(s); this is non-negotiable.
- **Submission gate**: `build-submission` validates locally before packaging and writes `submission.json`, `code_archive.zip`, and `trace_manifest.json` only after checks pass.
- **Logging**: structured JSON logs to `logs/`; trace ID per pipeline run and per question.
- **Configs**: all tunable parameters in versioned config files, never hardcoded.
- **Known ambiguity**: `retrieved_chunk_pages: []` for unanswerable vs telemetry "non-empty" requirement. Track as open issue; default to `[]` for unanswerable, switchable via config.
