# Agentic RAG Legal Challenge 2026

Warmup demo run: 0.759380 on Warmup 100 Gold Set v1 | Final blind leaderboard: 0.697287, Top 9

An end-to-end legal question-answering pipeline for the Agentic RAG Legal Challenge 2026, a competition focused on production-grade RAG systems: answer quality, source grounding, latency, telemetry, and reproducible engineering.

The system answers legal questions over phase-local PDF corpora. It downloads the competition inputs, parses and normalizes legal documents, builds a hybrid retrieval index, reranks evidence, generates typed answers, narrows source pages, packs the required telemetry, validates the output locally, and produces a submission bundle. The public snapshot includes the full artifact bundle for the best warmup demonstration run:

```text
artifacts/warmup_runs/runs/submission_e2e_20260424_solver_narrowing_no_guard/
```

---

## Architecture

```text
    +------------------------+
    | Competition API / data |
    +-----------+------------+
                |
                | sync-phase
                v
    +------------------------+       +------------------------+
    | Phase-local datasets   |------>| PDF parsing + OCR     |
    | questions + documents  |       | structure + tables    |
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
    | telemetry + archive    |       | reports + traces      |
    +------------------------+       +------------------------+
```

## How It Works

1. **Dataset sync.** `scripts/02a_sync_datasets.sh` calls the maintained CLI path, `agentic-rag sync-phase --phase <warmup|final> --extract`. Inputs land under phase-local paths such as `data/warmup/questions/questions.json` and `data/warmup/documents/pdfs`.

2. **Corpus construction.** `parse-corpus` reads each PDF page, tries native text extraction first, routes scanned or suspicious pages through OCR, applies structural normalization, serializes tables, and writes a canonical corpus plus a page map. Every downstream chunk keeps document and page provenance.

3. **Hybrid indexing.** `build-indices` creates multiple chunk families: page, section, clause, microchunk, and table. Dense embeddings and sparse text features are stored with stable metadata so retrieval can combine lexical recall with semantic matching.

4. **Question-aware retrieval.** At QA time the pipeline classifies the question shape and answer type, expands case-style queries when useful, applies candidate and rerank budgets, runs hybrid search, and reranks candidates with the Qwen reranker. Evidence selection keeps enough context for answer quality while limiting extra pages that hurt grounding precision.

5. **Answer routing.** Structured types (`boolean`, `number`, `name`, `names`, `date`) go through typed normalization and validation. `free_text` answers use the provider path with retrieved evidence and answer-type constraints. Unanswerable behavior is handled explicitly instead of leaking empty or malformed answers into the final payload.

6. **Page attribution.** The answerer emits a page trace. The attribution layer collapses candidate chunks into final source pages, suppresses repeated boilerplate, validates the chosen pages against answer evidence, and records whether the final pages came from solver narrowing, retrieval fallback, or validation repair.

7. **Submission packaging.** `build-submission` checkpoints answers and traces, packs the required retrieval/latency telemetry for every answer, validates `submission.json`, writes a code archive, and stores run reports. This makes the submission auditable question by question.

## Implementation Design

### Ingestion and Document Structure

Legal PDFs are heterogeneous: text PDFs, scanned pages, dense tables, repeated headers, and long case documents. The ingestion stage uses page triage to decide whether native extraction is enough or OCR is required. OpenDataLoader/Docling enrichment is used for structure-aware parsing, while the normalizer converts the result into a stable page-level corpus format.

The important design choice is that page identity is preserved from the first stage. The scorer evaluates retrieved `(document, page)` pairs, so the pipeline treats page mapping as a contract, not as auxiliary metadata.

### Indexing and Retrieval

The index is intentionally multi-granular. Page chunks provide stable grounding, section and clause chunks improve legal-context recall, microchunks improve precise matching, and table chunks keep tabular evidence searchable. Retrieval starts broad, then reranking and evidence budgeting reduce the context before answering.

The retrieval service records candidate counts, reranked windows, selected pages, budget decisions, query expansion, and page lifting. These traces are used both for debugging failures and for packing submission telemetry.

### Answering and Grounding

The answerer is typed because the benchmark mixes deterministic and generative answer types. Numbers, dates, names, and booleans are cleaned and validated differently from free-text answers. Final page attribution is deliberately separated from generation: the model can propose an answer, but the pipeline still validates which pages should be emitted as final grounding.

This separation is what improved the best warmup run. The saved run has zero final page misses on the grounding ledger: 95 eligible grounded questions, 95 hits, and `mean_final_grounding=0.891790` after page narrowing.

### Submission and Reproducibility

The submission layer is a production-style wrapper around the pipeline. It can reuse existing corpus and index artifacts, resume from QA checkpoints, validate payload shape before submission, and emit a bundle with reports, traces, and the exact generated `submission.json`.

Operator scripts keep the public path deterministic: dependencies are installed from `.python-version` and `uv.lock`, datasets are synced through the official API path, model caches are prepared explicitly, and the public gate runs without requiring private dev-only directories.

## Scoring Model

The local warmup scorer mirrors the challenge-style scoring contract used for development. The total score is multiplicative:

```text
answer_quality = 0.7 * deterministic + 0.3 * assistant
total_score    = answer_quality * grounding * telemetry * ttft_multiplier
```

Component meanings:

- `deterministic`: mean score over structured questions. Booleans and dates require exact match, names are normalized text matches, name lists use set overlap, and numbers allow a 1 percent tolerance.
- `assistant`: manual/proxy quality score for `free_text` answers.
- `grounding`: F-beta score over emitted `(document, page)` references versus gold references, with beta=2.5 to weight recall more heavily than precision.
- `telemetry`: 1.0 for well-formed telemetry, 0.9 when required telemetry is malformed or missing.
- `ttft_multiplier`: latency factor from answer telemetry. The local scorer uses documented bins up to 3 seconds and a linear proxy above 3 seconds because the public docs expose the range, not the exact platform function.

Warmup 100 Gold Set v1 metrics for the saved demo run:

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

Grounding ledger diagnostics for the same run:

```text
eligible_grounded_questions: 95
final_page_hits:             95
final_page_misses:           0
mean_final_recall:           0.951754
mean_final_precision:        0.739474
mean_final_grounding:        0.891790
```

The apparent difference between `grounding=0.847201` and `mean_final_grounding=0.891790` comes from two reports. The scorer metric is the final component used in `total_score` over all scored questions. The grounding ledger is a diagnostic report over eligible grounded questions after page-attribution analysis.

## Demo Artifact Bundle

The public snapshot includes one complete warmup run:

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

Use the bundle to inspect the run without executing the full GPU-backed pipeline:

- `submission/submission.json`: final payload shape sent to the challenge platform.
- `submission/qa_checkpoint.json`: checkpointed answer state.
- `submission/traces/`: question-level retrieval, answering, page attribution, and telemetry traces.
- `eval/benchmark_report.json`: local score breakdown.
- `grounding/summary.json` and `grounding/ledger.*`: page-grounding diagnostics.
- `manifest.json`: run metadata and artifact paths.

## Running

Create the deterministic environment, sync warmup inputs, prepare model caches, and run the public preflight:

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

Generated runtime logs, parsed corpora, indices, downloaded final data, model caches, and new submissions are intentionally ignored. The checked-in artifact bundle is the curated demonstration run.
