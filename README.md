# RAG Legal Challenge 2026

Saved evaluation run: **0.759380 score** | **0.891790 source-page grounding** | Final blind leaderboard: **0.697287, Top 9**

An end-to-end legal RAG pipeline for answering questions over large PDF collections with page-level citations, structured answer validation, latency telemetry, and reproducible submission artifacts.

Legal QA over PDFs is difficult for reasons that are easy to underestimate: relevant evidence may live in scanned pages, dense legal clauses, tables, repeated headers, or multi-page case context. This system handles that with OCR-backed ingestion, multi-granularity hybrid retrieval, Qwen reranking, typed answer routing, source-page narrowing, and traceable submission packaging.

Among 100 evaluated legal questions, 95 had annotated source-page evidence; the pipeline recovered expected source-page evidence for all 95, with 0 questions missing all required page support.

---

## Architecture

```text
    +------------------------+
    | Competition data       |
    +-----------+------------+
                |
                | download + extract
                v
    +------------------------+       +------------------------+
    | Questions + PDFs       |------>| PDF parsing + OCR     |
    | downloaded files       |       | structure + tables    |
    +-----------+------------+       +-----------+------------+
                |                                |
                |                                v
                |                    +------------------------+
                |                    | Corpus + page map      |
                |                    +-----------+------------+
                |                                |
                v                                v
    +------------------------+       +------------------------+
    | Questions              |------>| Hybrid index           |
    | type + metadata        |       | dense + sparse chunks  |
    +-----------+------------+       +-----------+------------+
                |                                |
                v                                v
    +------------------------+       +------------------------+
    | Retrieval + reranking  |<------| Qdrant / Qwen runtime |
    | budgets + page lifting |       +------------------------+
    +-----------+------------+
                |
                v
    +------------------------+       +------------------------+
    | Typed answering        |------>| Page attribution      |
    | deterministic + LLM    |       | narrowing + validation|
    +-----------+------------+       +-----------+------------+
                |                                |
                v                                v
    +------------------------+       +------------------------+
    | submission.json        |------>| Validation + artifacts|
    | telemetry + archive    |       | metrics + traces      |
    +------------------------+       +------------------------+
```

## Model Stack

- **OCR:** PaddleOCR with `PP-OCRv5_server_det` for text detection and `en_PP-OCRv5_mobile_rec` for text recognition.
- **Embeddings:** `Qwen/Qwen3-Embedding-0.6B` through SentenceTransformers, normalized dense vectors, CUDA runtime.
- **Reranking:** `Qwen/Qwen3-Reranker-0.6B` through a local Transformers backend.
- **Answering:** `gpt-5.4-mini` through an OpenAI-compatible Responses endpoint with strict JSON-schema outputs.
- **Search runtime:** Qdrant for dense/sparse vector storage plus a local BM25 sparse encoder for lexical matching.

## Pipeline Logic

1. **Stable data entrypoint.** `scripts/02a_sync_datasets.sh` downloads and extracts the selected competition split into predictable paths. The pipeline treats downloaded questions and PDFs as immutable inputs, which keeps later parsing, indexing, and evaluation runs reproducible.

2. **Page-first corpus construction.** Legal answers must cite source pages, so ingestion preserves page identity from the first processing step. `parse-corpus` reads each PDF page, tries native text extraction, routes scanned or suspicious pages through OCR, normalizes legal structure, serializes tables, and writes a canonical corpus plus a page map.

3. **Multi-granularity indexing.** Legal evidence can be a whole page, a section, a clause, a small phrase, or a table cell. `build-indices` creates page, section, clause, microchunk, and table views, then stores dense embeddings and sparse text features with document/page metadata.

4. **Recall before precision.** Retrieval starts broad enough to avoid losing the answer, then narrows aggressively before generation. The QA layer classifies question shape and answer type, expands case-style queries when useful, applies candidate and rerank budgets, runs hybrid dense/sparse search, and reranks candidates with the Qwen reranker.

5. **Answer-type routing.** Booleans, numbers, names, dates, lists, and free-text answers fail in different ways. Structured types (`boolean`, `number`, `name`, `names`, `date`) go through typed normalization and validation; `free_text` answers use the provider path with retrieved evidence and answer-type constraints.

6. **Attribution after answering.** A correct answer still loses value if its cited pages are weak. The attribution layer collapses candidate chunks into final source pages, suppresses repeated boilerplate, validates chosen pages against answer evidence, and records whether pages came from solver narrowing, retrieval fallback, or validation repair.

7. **Auditable submission packaging.** `build-submission` checkpoints answers and traces, packs retrieval and latency telemetry for every answer, validates `submission.json`, writes a code archive, and stores enough run data to inspect failures question by question.

## Pipeline Internals

### Ingestion

Ingestion turns noisy legal PDFs into citation-safe page records. The core decision is page-level source selection: trust native extraction, route to OCR, or keep a degraded record with explicit quality signals.

- **Page triage:** computes text length, image area, encoding noise, detected tables, and legal-marker density. Pages are classified as clean native text, suspicious extraction, or likely scan.
- **Source selection:** clean pages keep native PyMuPDF extraction; scanned pages require PaddleOCR; suspicious pages use OCR only when it improves the extracted text. Each page records `source_mode`, `parse_status`, quality flags, and OCR/native resolution notes.
- **OCR path:** PaddleOCR uses `PP-OCRv5_server_det` and `en_PP-OCRv5_mobile_rec`; OCR output is stored as text blocks, table candidates, and page-level fallback text.
- **Structural path:** document-level routing chooses tagged, hybrid, or local-only parsing through OpenDataLoader sidecars and the `docling-fast` hybrid backend. Parser nodes are normalized into headings, clauses, list items, table context, `heading_path`, and block roles.
- **Table path:** tables are extracted from native or OCR results, headers are inferred, multi-page continuations are merged when signatures and continuation cues match, and rows are serialized into retrievable text blocks with page anchors.
- **Artifacts:** `corpus.jsonl`, `page_map.json`, parse manifest, parser sidecars, and debug markdown. Every downstream chunk inherits document id, page number, parser provenance, quality signals, structural blocks, and table ids.

### Indexing

Indexing keeps several representations of the same page-stable corpus instead of betting on one chunk size. Page chunks preserve citation boundaries; section and clause chunks keep legal context; microchunks improve exact matching; table chunks expose row-level facts. Each chunk is embedded with `Qwen/Qwen3-Embedding-0.6B`, encoded with BM25, stored in Qdrant, and linked back to its parent page.

### Retriever

Retrieval starts wide, then narrows before answering. Dense and sparse candidates are fused, metadata boosts favor useful legal signals, and `Qwen/Qwen3-Reranker-0.6B` reranks the evidence. Budgets depend on the question class: cross-case questions search wider, case questions keep more context, simple factual/statute questions stay tighter. Evidence compression and page lifting keep the final context answerable without flooding attribution with weak pages.

### Answering and Grounding

Answering is typed because the failure modes differ. Booleans, numbers, names, name lists, and dates use type-specific extraction, normalization, confidence checks, and validation. Free-text answers use `gpt-5.4-mini` through strict JSON-schema outputs. Page attribution is a separate step: solver narrowing, retrieval fallback, boilerplate suppression, and validation repair decide which pages deserve to be cited. The saved run recovered expected page support for all 95 questions with annotated source-page evidence.

### Submission and Operations

The submission layer is built for auditability: checkpointed answers, per-question traces, packed telemetry, validated `submission.json`, score artifacts, grounding ledgers, and a code archive. Operator scripts keep setup and gate checks reproducible through `.python-version`, `uv.lock`, explicit dataset sync, model-cache provisioning, and `scripts/03_lint_and_test.sh`.

## Evaluation

The saved evaluation scores 100 legal questions with a multiplicative formula. A strong answer must be correct, grounded, well-formed, and fast enough:

```text
answer_quality = 0.7 * deterministic + 0.3 * assistant
total_score    = answer_quality * grounding * telemetry * ttft_multiplier
```

Component meanings:

- `deterministic`: mean score over structured questions. Booleans and dates require exact match, names are normalized text matches, name lists use set overlap, and numbers allow a 1 percent tolerance.
- `assistant`: quality score for `free_text` answers.
- `grounding`: F-beta score over emitted `(document, page)` references versus expected source pages, with beta=2.5 to weight recall more heavily than precision.
- `telemetry`: 1.0 for well-formed telemetry, 0.9 when required telemetry is malformed or missing.
- `ttft_multiplier`: latency factor from answer telemetry. Faster first-token responses receive a higher multiplier; slower responses reduce the final score.

Saved evaluation run metrics:

```text
scored_questions:        100
deterministic_questions: 70
free_text_questions:     30
deterministic:           0.942857
assistant:               0.986667
answer_quality:          0.956000
grounding:               0.847201
telemetry:               1.000000
mean_ttft_ms:            6390.477
ttft_multiplier:         0.937594
total_score:             0.759380
```

Source-page attribution quality for the same run:

```text
questions_with_page_evidence: 95
questions_with_correct_page:  95
questions_missing_pages:      0
final_page_recall:            0.951754
final_page_precision:         0.739474
final_page_grounding:         0.891790
```

The two grounding numbers measure different layers. `grounding=0.847201` is the benchmark component used inside `total_score` across all 100 answers. `final_page_grounding=0.891790` measures final source-page attribution on the 95 questions with annotated page evidence.

## Saved Evaluation Run

The repository includes one complete saved evaluation run for inspection:

```text
artifacts/warmup_runs/
|-- configs/solver_narrowing_true.yaml
|-- summary_runs.tsv
|-- top_failures.tsv
`-- runs/submission_e2e_20260424_solver_narrowing_no_guard/
    |-- manifest.json
    |-- submission/
    |   |-- submission.json
    |   |-- qa_checkpoint.json
    |   |-- trace_manifest.json
    |   `-- traces/
    |-- eval/
    |   |-- benchmark_report.json
    |   `-- benchmark_answer_scores.checkpoint.jsonl
    `-- grounding/
        |-- summary.json
        |-- ledger.jsonl
        `-- ledger.csv
```

- `submission/submission.json`: final payload shape sent to the challenge platform.
- `submission/qa_checkpoint.json`: checkpointed answer state.
- `submission/traces/`: question-level retrieval, answering, page attribution, and telemetry traces.
- `eval/benchmark_report.json`: score breakdown.
- `grounding/summary.json` and `grounding/ledger.*`: source-page evaluation data.
- `manifest.json`: run metadata and artifact paths.

## Running

Create the deterministic environment, sync warm-up inputs, prepare model caches, and run the public preflight:

```bash
./scripts/01_install_deps.sh
./scripts/02a_sync_datasets.sh --phase warmup
./scripts/02_download_models.sh
./scripts/00_check_env.sh
```

Run the pipeline wrappers:

```bash
./scripts/04_parse_corpus.sh --phase warmup --force
./scripts/05_build_indices.sh --phase warmup --force
./scripts/06_build_submission.sh --phase warmup --checkpoint-every 1
./scripts/07_validate_submission.sh --phase warmup
```

Full execution expects a GPU-backed runtime for OCR and reranking. Dataset sync requires `COMPETITION_API_KEY`; model and provider credentials are checked by the setup scripts before expensive stages run.

For the public quality gate:

```bash
./scripts/03_lint_and_test.sh
```

## Project Structure

```text
src/                     Pipeline implementation and CLI entrypoint
scripts/                 Operator scripts and public quality gate
configs/                 Baseline runtime configuration
data/warmup/             Warmup questions and document placeholders
artifacts/warmup_runs/   Kept best-run demo bundle and summaries
tools/                   Shared operator helpers
pyproject.toml           Package metadata and tool config
uv.lock                  Locked dependency graph
```

## Notes

Full and final-phase datasets are downloaded through `scripts/02a_sync_datasets.sh --phase warmup` or `scripts/02a_sync_datasets.sh --phase final`.

Generated runtime logs, parsed corpora, indices, downloaded final data, model caches, and new submissions are intentionally ignored. The checked-in warm-up output is the curated demonstration run.
