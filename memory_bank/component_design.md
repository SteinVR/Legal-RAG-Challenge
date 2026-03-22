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

At the time of writing, the workspace contains warmup PDFs and downloaded question/manifests, but the generated `data/warmup/corpus/` and `data/warmup/index/` directories have not been materialized yet.

## A. Ingestion (`src/ingestion/`)

### Responsibility

Ingestion turns raw PDFs into a canonical page-level corpus with normalized text, table blocks, page-level quality signals, and document/page manifests.

### Primary Files

- `src/ingestion/service.py` orchestrates `parse-corpus`, path resolution, cache reuse checks, and artifact writing.
- `src/ingestion/pdf_parser.py` parses one PDF with PyMuPDF, extracts native text and table candidates, and optionally upgrades pages with OCR.
- `src/ingestion/page_triage.py` classifies pages into `native_clean`, `scan`, or `suspicious` and computes quality scores and flags.
- `src/ingestion/ocr_engine.py` exposes the OCR adapter used when pages need OCR fallback.
- `src/ingestion/table_serializer.py` normalizes, merges, and serializes table rows into retrieval-friendly blocks.
- `src/ingestion/corpus_builder.py` converts parsed documents into canonical corpus records, page maps, manifests, and per-document debug markdown.

### Inputs

- PDFs under `data/{phase}/documents/pdfs/*.pdf`.
- Ingestion thresholds from `configs/baseline/v001/config.yaml`.
- Optional OCR availability through `src/ingestion/ocr_engine.py`.

### Outputs

`src/ingestion/service.py` writes four artifact groups:

- `corpus.jsonl`, one `CanonicalPageRecord` per page.
- `page_map.json`, document-level `PageMapRecord` summaries.
- `corpus_manifest.json`, document-level parse results and failure reporting.
- `debug/*.md`, one markdown debug view per successfully parsed document.

The main corpus output is page-scoped, not document-scoped. `CanonicalPageRecord` in `src/common/schemas.py` currently includes:

- `doc_id`, `page_number`, `document_title`, `document_family`
- `triage_label`, `source_mode`, `parse_status`
- `quality_score`, `quality_flags`
- `text`
- `blocks[]` with `text` and `table` content blocks
- `table_ids[]`

### Runtime Flow

For each PDF, `DocumentParser` in `src/ingestion/pdf_parser.py`:

- extracts native text and simple text blocks with PyMuPDF
- gathers raw table candidates
- computes page signals such as text count, image area, legal markers, and encoding noise
- routes the page through `triage_page`
- keeps native text for `native_clean`
- invokes OCR for `scan` and selected `suspicious` pages when OCR is enabled

After parsing, `serialize_document_tables()` merges adjacent cross-page tables and emits row-level `SerializedTableBlock` content. `CorpusBuilder` then assembles canonical page records and debug markdown.

### Important Notes

- `SourceMode` in `src/common/schemas.py` allows `hybrid`, but the current page resolution path in `src/ingestion/pdf_parser.py` effectively resolves pages as native or OCR.
- Quality is deterministic and heuristic-based. It is not model-scored.
- OCR availability is policy-driven: config can either fail hard or degrade parsing when the OCR runtime is missing.

### Tests

- `tests/test_ingestion_service.py`
- `tests/test_ingestion_pdf_parser.py`
- `tests/test_ingestion_page_triage.py`
- `tests/test_ingestion_table_serializer.py`
- `tests/test_ingestion_corpus_builder.py`

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

- The older architecture note mentioned separate `chunker.py`, `embedder.py`, and `index_builder.py` modules. In the current repository those responsibilities are consolidated in `src/indexing/service.py`.
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

### Tests

- `tests/test_retrieval_components.py`
- `tests/test_retrieval_qdrant_backend.py`
- `tests/test_retrieval_service.py`
- `tests/test_answering_retrieval_integration.py`

## D. Answering (`src/answering/`)

### Responsibility

Answering converts grounded retrieval output into final answer payloads. Deterministic answer types are solved through extraction-first logic; free-text questions are delegated to a provider with grounding checks and answer validation.

### Primary Files

- `src/answering/service.py` contains the answering contract, deterministic extractors, free-text path, validation helpers, and evidence normalization.

### Inputs

- `QuestionRecord`
- `RetrievalResult` or a retriever that can produce one
- a `FreeTextProvider` implementation for `free_text`

### Outputs

`AnsweringService.answer_question()` produces `AnswerResult` with:

- `question_id`
- typed `answer`
- normalized confidence
- grouped evidence page references

### Runtime Flow

- Deterministic answer types (`number`, `boolean`, `name`, `names`, `date`) use extraction heuristics over the retrieved evidence pages.
- The service normalizes evidence pages, deduplicates support, and validates polarity and format constraints.
- Free-text questions are sent to the provider through the `FreeTextProvider.generate()` contract and then checked for grounding and max-length compliance.
- If retrieval returns no valid evidence, the service emits the canonical unanswerable response path instead of hallucinating unsupported content.

### Important Notes

- The older architecture note referred to a `router.py`, `solvers/`, `free_text_gen.py`, and `self_check.py` split. In the current repository those responsibilities are consolidated inside `src/answering/service.py`.
- The answering layer is extraction-first by design. The LLM provider is not used for deterministic answer types.
- Free-text answers are capped to challenge-friendly short form and validated against the supplied evidence window.

### Tests

- `tests/test_answering_service.py`
- `tests/test_answering_retrieval_integration.py`

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
- `src/submission/pipeline.py` assembles the full run from corpus/index reuse checks through answering and packaging.
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

### Tests

- `tests/test_submission_pipeline.py`
- `tests/test_sync.py`
- `tests/test_api_client.py`
- `tests/test_main.py`

## G. Providers (`src/providers/`)

### Responsibility

Providers abstract the free-text generation backend used by the answering layer.

### Primary Files

- `src/providers/base.py` defines the `FreeTextProvider` protocol.
- `src/providers/codex_provider.py` implements the Codex-compatible HTTP provider over `/responses`.

### Inputs

- question text
- evidence page payloads
- character budget
- API credentials through `CODEX_OAUTH_TOKEN`, `OPENAI_API_KEY`, `CODEX_API_KEY`, or explicit constructor arguments

### Outputs

The provider returns a mapping with:

- `answer`
- `confidence`

### Important Notes

- The high-level architecture note mentioned a `fallback_provider.py`, but the current repository only contains the base protocol and the Codex-backed implementation.
- The provider is intentionally narrow. It only handles grounded free-text generation, not retrieval or deterministic extraction.
- `CodexFreeTextProvider` normalizes several possible response payload shapes before extracting the final answer text.

### Tests

- `tests/test_codex_provider.py`

## H. Common (`src/common/`)

### Responsibility

Common contains shared configuration and schema contracts used across ingestion, indexing, retrieval, evaluation, and submission.

### Primary Files

- `src/common/config.py` loads YAML config, applies env overrides, and exposes typed settings.
- `src/common/schemas.py` defines the phase, parse, table, corpus, and question models shared across the pipeline.

### Important Notes

- `AppConfig` is the root runtime configuration object; most services resolve their filesystem layout from it.
- `src/common/schemas.py` is the canonical definition site for ingestion and corpus artifacts such as `CanonicalPageRecord`, `PageMapRecord`, and `CorpusParseManifest`.
- Because these schemas sit at the foundation, drift here propagates into multiple stages quickly. When debugging artifact mismatches, start with this directory.

### Tests

- `tests/test_config.py`
- `tests/test_main.py`
- ingestion, indexing, retrieval, and evaluation tests also exercise these shared contracts indirectly

## Practical Reading Order

If you are new to the repository, the fastest way to orient yourself is:

1. `src/main.py`
2. `src/common/config.py`
3. `src/submission/sync.py`
4. `src/ingestion/service.py`
5. `src/indexing/service.py`
6. `src/retrieval/service.py`
7. `src/answering/service.py`
8. `src/submission/pipeline.py`

That sequence follows the actual lifecycle of the system more closely than the raw directory listing does.
