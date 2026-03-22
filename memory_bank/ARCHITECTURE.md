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

Detailed implementation notes live in `docs/component_design.md`. This section stays intentionally short so the project has one detailed component document instead of two drifting copies.

### A. Ingestion (`src/ingestion/`)
- **Responsibility**: PDF -> canonical page-level corpus with text, tables, quality metadata, and parse manifests.

### B. Indexing (`src/indexing/`)
- **Responsibility**: structure-aware chunking plus dense/sparse local index construction in embedded Qdrant.

### C. Retrieval (`src/retrieval/`)
- **Responsibility**: hybrid search, reranking, evidence compression, and chunk-to-page grounding.

### D. Answering (`src/answering/`)
- **Responsibility**: deterministic extraction-first answering plus grounded free-text answering.

### E. Evaluation (`src/evaluation/`)
- **Responsibility**: local validation, scoring, dev benchmark slicing, and regression analysis.

### F. Submission (`src/submission/`)
- **Responsibility**: phase sync, pipeline orchestration, telemetry packing, packaging, and submit-time checks.

### G. Providers (`src/providers/`)
- **Responsibility**: free-text provider abstraction and concrete model-backed generation path.

### H. Common (`src/common/`)
- **Responsibility**: shared config and schema contracts used across the full pipeline.

See `memory_bank/component_design.md` for real module ownership, artifact paths, current limitations, and test anchors.

---

## 6. Code Organization Pattern

- `src/main.py` -- CLI entrypoint: orchestrates sync, parse, build-indices, build-submission, validation, scoring, and benchmark commands
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
- **Submission gate**: `build-submission` validates locally before packaging and writes `submission.json`, `code_archive.zip`, and `trace_manifest.json` only after checks pass.
- **Logging**: structured JSON logs to `logs/`; trace ID per pipeline run and per question.
- **Configs**: all tunable parameters in versioned config files, never hardcoded.
- **Known ambiguity**: `retrieved_chunk_pages: []` for unanswerable vs telemetry "non-empty" requirement. Track as open issue; default to `[]` for unanswerable, switchable via config.
