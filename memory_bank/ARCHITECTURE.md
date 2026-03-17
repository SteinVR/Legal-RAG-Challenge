# Project Architecture: Agentic-RAG-Challenge

> Single source of truth for the project's logic, design, and behavior.

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
- **OCR / Document Parsing**: PaddleOCR-VL-1.5 (primary), PyMuPDF/pdfplumber (native text fast path)
- **Embeddings**: Qwen3-Embedding-0.6B (32K context, instruction-aware, MRL)
- **Reranker**: Qwen3-Reranker-0.6B
- **Lexical search**: BM25 (rank-bm25 or tantivy-py)
- **Vector store**: Qdrant embedded mode (dense + sparse vectors, payload filtering, persistence)
- **Generation backend**: Codex via OAuth (primary); provider abstraction for fallback
- **Canonical data format**: JSONL (structured) + Markdown (debug)
- **Config management**: versioned YAML configs under `configs/`
- **Competition API client**: `arlc` SDK or custom thin wrapper

---

## 5. Component Design

### A. Ingestion (`src/ingestion/`)
- **Responsibility**: PDF -> canonical page-level corpus with text, layout, tables, metadata.
- **Key modules**:
  - `pdf_parser.py` -- native text extraction (PyMuPDF)
  - `ocr_engine.py` -- PaddleOCR-VL-1.5 page-level parsing
  - `page_triage.py` -- rule-based routing (native_clean / scan / suspicious)
  - `table_serializer.py` -- tables into self-contained retrieval blocks (ERC2 pattern)
  - `corpus_builder.py` -- assembles canonical JSONL corpus with page map
- **Output**: `data/{phase}/corpus.jsonl`, `data/{phase}/page_manifest.json`

### B. Indexing (`src/indexing/`)
- **Responsibility**: chunking + index construction via Qdrant embedded.
- **Key modules**:
  - `chunker.py` -- structure-aware chunking (heading/clause/table-level), page span preservation
  - `embedder.py` -- Qwen3-Embedding-0.6B batch embedding
  - `index_builder.py` -- Qdrant collection setup (dense vectors + BM25 sparse vectors + payload metadata), population
- **Output**: Qdrant persistent storage under `data/{phase}/qdrant/`

### C. Retrieval (`src/retrieval/`)
- **Responsibility**: hybrid search via Qdrant, reranking, evidence compression.
- **Key modules**:
  - `hybrid_search.py` -- Qdrant hybrid query (dense + sparse fusion with payload filtering)
  - `reranker.py` -- Qwen3-Reranker-0.6B
  - `evidence_compressor.py` -- support-page validator + pruner (ERC2 pattern)
  - `page_lifter.py` -- chunk-to-page aggregation
- **Output**: candidate pages, final evidence set with page refs

### D. Answering (`src/answering/`)
- **Responsibility**: routing by answer_type, typed extraction, free-text generation.
- **Key modules**:
  - `router.py` -- routes by answer_type + query shape
  - `solvers/` -- typed solvers (number, boolean, name, names, date, null_detector)
  - `free_text_gen.py` -- grounded short-form generator (max 280 chars)
  - `self_check.py` -- answer validation (type, length, contradiction)
- **Output**: structured answer + confidence

### E. Evaluation (`src/evaluation/`)
- **Responsibility**: local scoring mirroring challenge formula.
- **Key modules**:
  - `scorer.py` -- deterministic scoring, grounding F-beta, TTFT factor, telemetry factor
  - `validator.py` -- submission JSON schema + telemetry validation
  - `dev_benchmark.py` -- dev gold/silver set management
- **Output**: evaluation report (JSON/HTML)

### F. Submission (`src/submission/`)
- **Responsibility**: telemetry packing, submission assembly, submit gate.
- **Key modules**:
  - `telemetry_packer.py` -- timing, usage, retrieval page refs
  - `packager.py` -- submission.json + code_archive.zip assembly
  - `submit_gate.py` -- pre-submit sanity checks
  - `api_client.py` -- competition API wrapper (download docs/questions, submit)

### G. Providers (`src/providers/`)
- **Responsibility**: LLM provider abstraction.
- **Key modules**:
  - `base.py` -- abstract interface (generate, extract, embed)
  - `codex_provider.py` -- Codex via OAuth
  - `fallback_provider.py` -- alternative public API backend

### H. Common (`src/common/`)
- **Responsibility**: shared utilities.
- **Key modules**:
  - `config.py` -- config loader, versioned config management
  - `schemas.py` -- Pydantic models (Question, Answer, Telemetry, Submission, Page, Chunk)
  - `tracing.py` -- trace ID generation, per-question logging

---

## 6. Code Organization Pattern

- `src/main.py` -- CLI entrypoint: orchestrates full pipeline or individual stages
- `src/common/config.py` -- config loading and validation
- `src/common/schemas.py` -- all data models (Pydantic)
- `configs/baseline/v001/` -- baseline config YAML files
- `data/{warmup,final}/` -- phase-isolated corpus and index data
- `data/dev/` -- dev gold/silver question sets

---

## 7. Core Data Models

- **Page**: doc_id, page_number, text, source_mode, quality_score, blocks, table_ids
- **Chunk**: chunk_id, text, doc_id, page_span, parent_section, chunk_type, metadata
- **Question**: question_id, text, answer_type
- **Answer**: question_id, answer (typed), telemetry
- **Telemetry**: timing (ttft_ms, tpot_ms, total_time_ms), retrieval (retrieved_chunk_pages), usage (input/output tokens), model_name
- **Submission**: architecture_summary, answers[]

---

## 8. Key Conventions & Logging

- **Modularity**: each pipeline stage is independently runnable and testable.
- **Page attribution**: every chunk traces back to physical PDF page(s); this is non-negotiable.
- **Logging**: structured JSON logs to `logs/`; trace ID per pipeline run and per question.
- **Configs**: all tunable parameters in versioned config files, never hardcoded.
- **Known ambiguity**: `retrieved_chunk_pages: []` for unanswerable vs telemetry "non-empty" requirement. Track as open issue; default to `[]` for unanswerable, switchable via config.
