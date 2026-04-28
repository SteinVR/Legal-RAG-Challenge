# Agentic RAG Legal Challenge 2026

Best warm-up run: **0.759380** | Final blind leaderboard: **0.697287 | Top 9**

An end-to-end legal question-answering pipeline for the Agentic RAG Legal Challenge 2026, a competition focused on production-grade RAG systems: answer quality, source grounding, latency, telemetry, and reproducible engineering.

The system answers legal questions over competition PDF collections. It downloads the inputs, parses and normalizes legal documents, builds a hybrid retrieval index, reranks evidence, generates typed answers, narrows source pages, packs the required telemetry, validates the output, and produces a submission bundle. The public snapshot includes the complete saved output for the best warm-up run:

```text
artifacts/warmup_runs/runs/submission_e2e_20260424_solver_narrowing_no_guard/
```

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

## How It Works

1. **Dataset sync.** `scripts/02a_sync_datasets.sh` downloads and extracts the selected competition split. Inputs land in predictable paths such as `data/warmup/questions/questions.json` and `data/warmup/documents/pdfs`.

2. **Corpus construction.** `parse-corpus` reads each PDF page, tries native text extraction first, routes scanned or suspicious pages through OCR, applies structural normalization, serializes tables, and writes a canonical corpus plus a page map. Every downstream chunk keeps document and page provenance.

3. **Hybrid indexing.** `build-indices` creates multiple chunk families: page, section, clause, microchunk, and table. Dense embeddings and sparse text features are stored with stable metadata so retrieval can combine lexical recall with semantic matching.

4. **Question-aware retrieval.** At QA time the pipeline classifies the question shape and answer type, expands case-style queries when useful, applies candidate and rerank budgets, runs hybrid search, and reranks candidates with the Qwen reranker. Evidence selection keeps enough context for answer quality while limiting extra pages that hurt grounding precision.

5. **Answer routing.** Structured types (`boolean`, `number`, `name`, `names`, `date`) go through typed normalization and validation. `free_text` answers use the provider path with retrieved evidence and answer-type constraints. Unanswerable behavior is handled explicitly instead of leaking empty or malformed answers into the final payload.

6. **Page attribution.** The answerer emits a page trace. The attribution layer collapses candidate chunks into final source pages, suppresses repeated boilerplate, validates the chosen pages against answer evidence, and records whether the final pages came from solver narrowing, retrieval fallback, or validation repair.

7. **Submission packaging.** `build-submission` checkpoints answers and traces, packs the required retrieval/latency telemetry for every answer, validates `submission.json`, writes a code archive, and stores the metrics needed to audit the run question by question.

## Core Engineering Ideas

### Preserve the Legal Source

Legal PDFs mix clean text, scans, tables, repeated headers, and long case documents. The parser handles that variety with native extraction, OCR fallback, table serialization, and structural cleanup. The output is a stable page-level corpus, so every later decision can still point back to a concrete document page.

This matters because legal RAG is judged by both the answer and the cited evidence. Page identity is preserved from ingestion onward instead of being reconstructed after generation.

### Retrieve Broadly, Answer Narrowly

The index uses several granularities at once. Page chunks preserve grounding, section and clause chunks capture legal context, microchunks improve exact matching, and table chunks keep tabular evidence searchable. Retrieval starts broad enough to avoid missing the answer, then reranking and evidence budgets shrink the context before generation.

The pipeline adapts candidate and evidence budgets by question shape. Case-style questions can search wider; simple factual questions can stay narrow. The goal is high recall before reranking and high precision before emitting final source pages.

### Treat Answer Types Differently

The benchmark mixes booleans, numbers, names, dates, lists, and free text. The pipeline does not send all of them through the same generic answer path. Structured answers get type-specific normalization and validation; free-text answers use retrieved evidence with stricter grounding controls.

Generation and page attribution are separate steps. The model can propose an answer, but the system still decides which pages deserve to be cited. In the saved warm-up run, all 95 questions with page-level evidence were assigned at least one correct final source page.

### Make Each Answer Auditable

Every answer carries retrieval telemetry, selected pages, latency data, and a trace of the answering path. That makes failures inspectable: a wrong answer can be traced back to missing retrieval, reranking, evidence compression, answer normalization, or final page selection.

The operator path is reproducible: dependencies come from `.python-version` and `uv.lock`, datasets are synced through the competition API, model caches are prepared explicitly, and the public gate runs from a clean checkout.

## Scoring Model

The included warm-up evaluation scores 100 legal questions with a multiplicative formula. A strong answer must be correct, grounded, well-formed, and fast enough:

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

Saved warm-up run metrics:

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

Final source-page quality for the same run:

```text
questions_with_page_evidence: 95
questions_with_correct_page:  95
questions_missing_pages:      0
final_page_recall:            0.951754
final_page_precision:         0.739474
final_page_grounding:         0.891790
```

The two grounding numbers answer different questions. `grounding=0.847201` is the benchmark component used inside `total_score` across all 100 answers. `final_page_grounding=0.891790` focuses only on the 95 questions that have page-level evidence and measures the quality of the final pages emitted by the attribution layer.

## Saved Warm-up Run

The public snapshot includes one complete warm-up run:

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
