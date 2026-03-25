# Component Design

This document expands the high-level component map from `memory_bank/ARCHITECTURE.md` into the current implementation reality of the repository. It is intentionally implementation-aware: file names, artifact paths, and runtime behavior below were verified against the codebase rather than copied from older architecture notes.

## System Entry Points And Artifact Flow

The main operational entrypoint is `src/main.py`. It wires the CLI commands that drive the project lifecycle:

- `download-questions`, `download-documents`, `sync` and `sync-phase` for phase-local data acquisition.
- `parse-corpus` for PDF ingestion and corpus materialization.
- `build-indices` for hybrid chunking and Qdrant index construction.
- `build-submission` for the end-to-end question answering pipeline.
- `validate-submission`, `score-submission`, `benchmark-summary`, `compare-benchmark-runs`, and `analyze-benchmark-consistency` for local evaluation and diagnostics.

Configuration is loaded through `src/common/config.py`. The repository-level default config is `configs/baseline/v001/config.yaml`, with a package fallback copy under `src/resources/configs/baseline/v001/config.yaml`.

Phase-local storage is resolved by `src/submission/sync.py::PhasePaths` and currently follows this layout:

- `data/{phase}/questions/questions.json`
- `data/{phase}/documents/documents.zip`
- `data/{phase}/documents/pdfs/*.pdf`
- `data/{phase}/manifests/sync_manifest.json`
- `data/{phase}/corpus/corpus.jsonl`
- `data/{phase}/corpus/page_map.json`
- `data/{phase}/corpus/corpus_manifest.json`
- `data/{phase}/corpus/debug/*.md`
- `data/{phase}/index/qdrant/`
- `data/{phase}/index/page_parent_map.json`
- `data/{phase}/index/index_manifest.json`
- `data/{phase}/index/sparse_encoder_state.json`

The warmup phase is fully materialized: corpus (590 pages, `opendataloader:tagged`), index (3804 chunks), and raw parse sidecars (pymupdf + opendataloader JSON). Last e2e run: 2026-03-25.

## A. Ingestion (`src/ingestion/`) — 10 modules

### Responsibility

Ingestion turns raw PDFs into a canonical page-level corpus with structural provenance, tables, quality metadata, JSON sidecars, and parse manifests. Wave 4C added routed structural parsing via opendataloader-pdf.

### Primary Files

- `service.py` — orchestrates `parse-corpus`, path resolution, cache reuse, artifact writing, and W4C parser routing integration.
- `pdf_parser.py` — parses one PDF: native text extraction (PyMuPDF), page triage, OCR upgrade for scan/suspicious pages, parser availability checks. Calls `_parser_availability()` and `resolve_parser_route()` to decide the parsing path.
- `parser_routing.py` — W4C: route decisions (`TAGGED`/`HYBRID`/`LOCAL_ONLY`/`BASELINE_FALLBACK`) based on `DocumentStructuralProfile` (struct tree, born-digital, layout complexity) and `ParserAvailability` (opendataloader importable, hybrid backend healthy).
- `opendataloader_adapter.py` — W4C: executes opendataloader-pdf convert via Java bridge. Produces JSON sidecars with typed nodes, bbox, tables. LRU-cached availability check.
- `sidecars.py` — W4C: JSON sidecar read/write helpers for `raw_parse/pymupdf/` and `raw_parse/opendataloader/`.
- `structural_normalizer.py` — W4C: heading hierarchy, list nesting, caption linkage from opendataloader nodes.
- `ocr_engine.py` — GPU OCR adapter (PaddleOCR PP-OCRv5). Config: `ocr_device`, `ocr_model_root_dir`. Validates CUDA via `paddle.device.cuda.device_count()`.
- `page_triage.py` — classifies pages into `native_clean`, `scan`, or `suspicious` via heuristics.
- `table_serializer.py` — rule-based table detection, cross-page merging, row-level serialization.
- `corpus_builder.py` — assembles `CanonicalPageRecord` objects, page maps, manifests, debug markdown.

### Inputs

- PDFs under `data/{phase}/documents/pdfs/*.pdf`.
- Ingestion config from `configs/baseline/v001/config.yaml` (OCR settings, opendataloader settings).
- GPU OCR runtime (PP-OCRv5_server_det + en_PP-OCRv5_mobile_rec).
- Optional opendataloader-pdf Java bridge.

### Outputs

- `corpus.jsonl` — one `CanonicalPageRecord` per page (with `parser_provenance`, `source_mode`, quality metadata).
- `page_map.json` — document-level summaries.
- `corpus_manifest.json` — parse results and failure reporting.
- `debug/*.md` — per-document markdown debug views.
- `raw_parse/pymupdf/*.json` — native parse sidecars.
- `raw_parse/opendataloader/*.json` — structural parse sidecars (typed nodes, bbox, tables).

### `CanonicalPageRecord` fields

`doc_id`, `page_number`, `document_title`, `document_family`, `triage_label`, `source_mode`, `parse_status`, `quality_score`, `quality_flags`, `text`, `blocks[]`, `table_ids[]`, `parser_provenance`.

### Parser routing (W4C)

```
if not opendataloader_available → BASELINE_FALLBACK
else if has_struct_tree → TAGGED (opendataloader with struct tree)
else if born_digital OR layout_complex →
    if hybrid_backend_healthy → HYBRID (docling-fast) else LOCAL_ONLY
else → LOCAL_ONLY
```

Config: `opendataloader_table_method="cluster"`, `opendataloader_reading_order="xycut"`, `opendataloader_hybrid_backend="docling-fast"`, `opendataloader_hybrid_url="http://localhost:5002"`.

### OCR (W4D)

- GPU device: `config.ingestion.ocr_device` (default `gpu:0`).
- Triggered only for `SCAN` or `SUSPICIOUS` triage labels (high image area, low native text).
- Warmup corpus is born-digital → OCR loaded but not triggered.
- Policy: `ocr_unavailable_policy="error"` fails fast if GPU unavailable.

### Tests (9 files)

`test_ingestion_service.py`, `test_ingestion_pdf_parser.py`, `test_ingestion_page_triage.py`, `test_ingestion_table_serializer.py`, `test_ingestion_corpus_builder.py`, `test_ingestion_parser_routing.py`, `test_ingestion_opendataloader_adapter.py`, `test_ingestion_sidecars.py`, `test_ingestion_structural_normalizer.py`, `test_ingestion_ocr_engine.py`.

## B. Indexing (`src/indexing/`)

### Responsibility

Indexing turns the canonical corpus into retrieval chunks, computes dense and sparse representations, and persists the hybrid index to local Qdrant storage.

### Primary Files

- `src/indexing/service.py` owns almost the entire indexing layer: chunk building, dense embedder contract, sparse BM25 encoder, Qdrant persistence, and manifest generation.

### Inputs

- `data/{phase}/corpus/corpus.jsonl`
- `data/{phase}/corpus/page_map.json`
- `data/{phase}/corpus/corpus_manifest.json`

### Outputs

`HybridIndexService` materializes:

- `data/{phase}/index/qdrant/` with the embedded Qdrant collection
- `data/{phase}/index/page_parent_map.json`
- `data/{phase}/index/index_manifest.json`
- `data/{phase}/index/sparse_encoder_state.json`

### Chunking Strategy

Chunking is structure-aware and multi-level rather than fixed-token windowing. `build_index_chunks()` in `src/indexing/service.py` emits:

- page chunks with full page text
- clause chunks for numbered legal provisions
- microchunks split from clause text in two-sentence windows
- section chunks spanning contiguous pages that share heading context
- table chunks for each serialized table row block

The implementation also preserves several legal-document heuristics:

- heading carry-forward across continuation pages
- heading/body paragraph splitting when a heading and first body sentence were fused
- synthetic clause lead-ins for introductory prose before numbered clauses
- paragraph fallback synthesis when numbering is absent
- metadata enrichment with entities, dates, token count, and BM25 terms

### Dense And Sparse Encoding

Dense encoding currently uses `Qwen3DenseEmbedder` in `src/indexing/service.py` with these defaults:

- model: `Qwen/Qwen3-Embedding-0.6B`
- `prompt_name="passage"`
- normalized embeddings
- batch size `16`
- `local_files_only=True`

The model is lazy-loaded through `SentenceTransformer(..., trust_remote_code=True, local_files_only=True)`. If the model is not present locally, indexing fails with a clear runtime error. Sparse encoding is an in-repo BM25 Okapi implementation persisted as `sparse_encoder_state.json`.

### Important Notes

- Dense query encoding and dense passage encoding share the same `encode()` contract. There is no separate query encoder API in the current code.
- Token counts are recorded as metadata and used for sparse encoding context, but token budget is not the primary chunk boundary mechanism.

### Tests

- `tests/test_indexing_service.py`
- `tests/test_retrieval_qdrant_backend.py`

## C. Retrieval (`src/retrieval/`)

### Responsibility

Retrieval loads the persisted index, runs hybrid search, reranks candidates, compresses evidence, and lifts final chunk evidence to page references required by the challenge telemetry format.

### Primary Files

- `src/retrieval/hybrid_search.py` contains the Qdrant backend and RRF rank fusion.
- `src/retrieval/reranker.py` provides the Qwen reranker and lexical fallback.
- `src/retrieval/evidence_compressor.py` selects a compact page-grounded evidence set.
- `src/retrieval/page_lifter.py` aggregates chunk spans into deduplicated `PageReference` objects.
- `src/retrieval/service.py` composes search, rerank, compression, and page lifting into `RetrievalService`.

### Inputs

- `data/{phase}/index/index_manifest.json`
- `data/{phase}/index/qdrant/`
- `data/{phase}/index/sparse_encoder_state.json`
- question text from `QuestionRecord`

### Outputs

`RetrievalService.retrieve()` returns `RetrievalResult` with:

- candidate and reranked counts
- selected `RetrievedChunk` evidence
- grouped `retrieved_chunk_pages`
- an explicit `is_unanswerable` flag when no grounded evidence survives

### Runtime Flow

- `QdrantHybridSearchBackend` encodes the question with the dense embedder and queries the local Qdrant collection.
- If sparse compatibility is enabled, it also loads the persisted BM25 encoder and issues a sparse query.
- `RRFHybridSearch` fuses dense and sparse rankings with reciprocal rank fusion.
- `QwenReranker` rescoring is attempted first. If the reranker backend fails, `LexicalFallbackReranker` takes over.
- `SupportPageEvidenceCompressor` constrains evidence to a compact subset while preserving page-level support.
- `PageLifter` converts chunk page spans into grouped grounding references for telemetry and downstream answering.

### Important Notes

- Retrieval is page-grounding aware all the way through. Evidence compression and lifting are not optional post-processing extras.
- The sparse path is compatibility-aware: retrieval can still run without sparse state if only dense artifacts are available.
- Rank fusion and reranking are separated concerns: RRF stabilizes search recall, while the reranker sharpens the final candidate order.
- W4D additions: question-class-aware budget routing (case/statute precision vs cross_case breadth), soft metadata boosts from W4B query metadata (legal entities as optional payload conditions in Qdrant), parent-page expansion.

### Tests

- `tests/test_retrieval_components.py`
- `tests/test_retrieval_qdrant_backend.py`
- `tests/test_retrieval_service.py`
- `tests/test_answering_retrieval_integration.py`

## D. Answering (`src/answering/`) — 3 modules

### Responsibility

Answering converts grounded retrieval output into final answer payloads. Primary path: schema-first structured solving (W4B). Guardrails: deterministic validation/normalization. Page attribution: two-pass (W4A). Cross-case decomposition: rule-based (W4E).

### Primary Files

- `service.py` — schema registry (`ANSWER_SCHEMA_REGISTRY`), query metadata extraction (`extract_query_metadata()`), structured solver dispatch (`_answer_with_structured_solver()`), deterministic guardrails, confidence thresholding. Contains `AnsweringService`, `AnswerResult`, `QueryMetadata`, `LegalEntityMetadata`, per-type Pydantic answer schemas.
- `page_attribution.py` — W4A: `prune_candidate_pages()` (Pass A: boilerplate/title-page suppression), `finalize_page_attribution()` (Pass B: post-answer narrowing/validation). `PageAttributionConfig`, `PageAttributionTrace`, `build_page_trace()`.
- `decomposition.py` — W4E: `should_decompose()` (trigger: enabled + 2+ case refs + boolean/name type), `decompose_question()` (rule-based per-case sub-question generation), `recompose_answer()` (deterministic: set intersection for boolean, value comparison for name), `answer_with_decomposition()` (orchestrator).

### Key data flow

```
question → extract_query_metadata() → retrieval → Pass A pruning
  → structured solver (schema + reasoning effort) → Pass B finalization
  → AnswerResult with PageAttributionTrace

Cross-case questions (when decomposition enabled):
  question → should_decompose() → decompose_question()
  → [per sub-question: answering_service.answer_question()]
  → recompose_answer() → merged AnswerResult
```

### Schema registry (W4B)

`ANSWER_SCHEMA_REGISTRY` maps answer_type → Pydantic model:
- `BooleanAnswerSchema`, `NumberAnswerSchema`, `NameAnswerSchema`, `NamesAnswerSchema`, `DateAnswerSchema`, `FreeTextAnswerSchema`
- Common fields: `is_answerable`, `relevant_pages`, `reasoning_summary`, `confidence`, typed `final_answer`
- Reasoning effort: high (boolean/name/names), medium (number/date/free_text)

### Decomposition (W4E)

- Disabled by default (`config.decomposition.enabled=False`).
- Triggers on boolean/name questions with 2+ DIFC case references (CFI/SCT/ARB/DEC/TCD/ENF/CA).
- Subject detection: party, judge, date, claim → generates appropriate sub-questions with adjusted answer_type.
- Recomposition: boolean → set intersection; name → value comparison (prefer earlier/lower or later/higher).
- 31/100 warmup questions are cross-case (19 boolean, 12 name).

### Tests (4 files)

`test_answering_service.py`, `test_answering_retrieval_integration.py`, `test_answering_w4b_contracts.py`, `test_answering_page_attribution.py`, `test_answering_decomposition.py`.

## E. Evaluation (`src/evaluation/`)

### Responsibility

Evaluation mirrors challenge-facing validation and local scoring. It also carries the dev benchmark models and comparison helpers used for regression testing.

### Primary Files

- `src/evaluation/contracts.py` defines answer types, page references, validation reports, score reports, and benchmark data models.
- `src/evaluation/validator.py` validates `submission.json` structure, telemetry, question coverage, and page references.
- `src/evaluation/scorer.py` computes deterministic, grounding, telemetry, and TTFT factors.
- `src/evaluation/goldset.py` handles gold/reference-oriented helpers.
- `src/evaluation/dev_benchmark/__init__.py` implements benchmark dataset loading, slicing, report generation, comparison, and consistency analysis.

### Inputs

- question metadata JSON
- submission payloads
- reference answer files
- optional free-text assistant score files
- optional benchmark bundles and metadata

### Outputs

- structured validation reports
- structured score reports
- benchmark run summaries, slice reports, comparisons, and stability reports

### Important Notes

- `src/main.py` exposes evaluation-facing CLI commands directly. This layer is not only a library; it is also part of day-to-day workflow.
- `UnanswerableRetrievalPolicy` is implemented here and propagated into validation and submission building.
- The `dev_benchmark` code is package-based under `src/evaluation/dev_benchmark/__init__.py`, even though the directory looks sparse at first glance.

### Tests

- `tests/test_evaluation_validator.py`
- `tests/test_evaluation_scorer.py`
- `tests/test_evaluation_dev_benchmark.py`
- `tests/test_dev_benchmark.py`
- `tests/test_goldset.py`

## F. Submission (`src/submission/`)

### Responsibility

Submission packages the full pipeline into a competition-ready bundle: sync helpers, pipeline orchestration, telemetry packing, code archive creation, pre-submit validation, and API interaction.

### Primary Files

- `src/submission/sync.py` defines `PhasePaths` and phase-local question/document download orchestration.
- `src/submission/pipeline.py` assembles the full run from corpus/index reuse checks through answering (with decomposition routing) and packaging.
- `src/submission/telemetry_packer.py` formats answer-level telemetry.
- `src/submission/packager.py` writes `submission.json` and produces `code_archive.zip`.
- `src/submission/submit_gate.py` enforces packaging and local validation checks before submission.
- `src/submission/api_client.py` wraps the competition API.

### Inputs

- phase-local config
- `questions.json`
- extracted document directory
- reused or generated corpus/index artifacts

### Outputs

`BuildSubmissionService` writes:

- `submission.json`
- `code_archive.zip`
- a trace manifest for the run

It also validates the bundle locally before the user attempts a remote submit.

### Runtime Flow

- Align the runtime config to the chosen phase-local documents directory.
- Reuse or rebuild corpus artifacts with `CorpusParseService`.
- Reuse or rebuild index artifacts with `HybridIndexService`.
- Load questions, retrieve evidence, answer questions, and pack telemetry.
- Build the final payload, run local validation, write trace artifacts, and archive the code.

### Important Notes

- The submission pipeline is restart-safe in practice because it checks corpus and index completeness before rebuilding.
- `code_archive.zip` intentionally excludes secrets, data, logs, caches, and unrelated tooling state.
- The provider fallback path in `pipeline.py` only applies to free-text provider model failures, not to deterministic extraction.
- `_answer_question()` checks `config.decomposition.enabled` and routes cross-case questions through `answer_with_decomposition()` (W4E).

### Tests

- `tests/test_submission_pipeline.py`
- `tests/test_sync.py`
- `tests/test_api_client.py`
- `tests/test_main.py`

## G. Providers (`src/providers/`) — 2 modules

### Responsibility

Providers abstract free-text and structured-output generation.

### Primary Files

- `base.py` — `FreeTextProvider` protocol and `StructuredProvider` protocol.
- `codex_provider.py` — `CodexFreeTextProvider` (free-text via `/responses`) and structured output support:
  - `generate()` — free-text: question + evidence → answer + confidence.
  - `generate_structured()` — W4B: question + answer_type + evidence + Pydantic schema + reasoning_effort → schema-validated dict.
  - `_strict_openai_schema()` — post-processor: ensures all Pydantic properties in `required` array (OpenAI strict mode compatibility).
  - Response parsing handles OpenAI Responses API format: skips `reasoning` items, extracts `output_text` type content.
  - `max_output_tokens=2048` (reasoning models consume most tokens on thinking).
  - Structured system prompt includes ISO-8601 date format hint.

### Credentials

Resolved via `CODEX_OAUTH_TOKEN`, `OPENAI_API_KEY`, `CODEX_API_KEY`, or explicit constructor argument.

### Tests

- `tests/test_codex_provider.py`

## H. Common (`src/common/`)

### Responsibility

Common contains shared configuration and schema contracts used across ingestion, indexing, retrieval, evaluation, and submission.

### Primary Files

- `src/common/config.py` loads YAML config, applies env overrides, and exposes typed settings.
- `src/common/schemas.py` defines the phase, parse, table, corpus, and question models shared across the pipeline.

### Important Notes

- `AppConfig` is the root runtime configuration object. Wave 4 added: `DecompositionSettings` (W4E), `PageAttributionSettings` (W4A), expanded `IngestionSettings` (OCR device, opendataloader), `RetrievalSettings` (question-class budgets), `IndexingSettings` (token-aware chunking).
- `src/common/schemas.py` is the canonical definition site for ingestion and corpus artifacts such as `CanonicalPageRecord`, `PageMapRecord`, and `CorpusParseManifest`.
- Env overrides: `COMPETITION_DECOMPOSITION_ENABLED`, `COMPETITION_OCR_DEVICE`, `COMPETITION_PASS_A_ENABLED`, `COMPETITION_PAGE_VALIDATION_MODE`, etc.

### Tests

- `tests/test_config.py`
- `tests/test_main.py`
- ingestion, indexing, retrieval, and evaluation tests also exercise these shared contracts indirectly

## Practical Reading Order

If you are new to the repository, the fastest way to orient yourself is:

1. `src/main.py` — CLI entrypoint, all commands
2. `src/common/config.py` — full config model with all Wave 4 settings
3. `src/submission/sync.py` — phase paths and data layout
4. `src/ingestion/service.py` → `src/ingestion/parser_routing.py` — parse orchestration and W4C routing
5. `src/indexing/service.py` — chunking and hybrid index
6. `src/retrieval/service.py` — retrieval with budget routing
7. `src/answering/service.py` → `src/answering/page_attribution.py` — schema-first solving + two-pass attribution
8. `src/answering/decomposition.py` — cross-case decomposition (W4E)
9. `src/providers/codex_provider.py` — structured output provider
10. `src/submission/pipeline.py` — full e2e orchestration with decomposition routing

That sequence follows the actual lifecycle of the system.

## Current Stats (2026-03-25)

- **Test suite**: 342 passed, ruff clean
- **Corpus**: 30 docs, 590 pages, `opendataloader:tagged`, 30 JSON sidecars
- **Index**: 3804 chunks (page, section, clause, microchunk, table)
- **GPU**: RTX 4060 8GB, Paddle CUDA 1 device, Torch CUDA active
- **Cross-case coverage**: 31/100 warmup questions decomposable (19 boolean, 12 name)
- **Smoke test**: 5/5 processed, 4 answered, decomposition verified
