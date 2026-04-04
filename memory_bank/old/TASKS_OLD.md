# Task Board (RAPID): Agentic-RAG-Challenge

> Wave-based plan. Tasks inside the same wave may run in parallel when their declared dependencies are satisfied. Details in `memory_bank/tasks/{TASK_ID}.md`.

## 1. Active Plan (Wave-Based)

### Wave 1 -- Foundation

- [x] [TASK-W1A](tasks/TASK-W1A.md) Workspace, config & corpus access

### Wave 2 -- Evaluation & Corpus Framing

- [x] [TASK-W2A](tasks/TASK-W2A.md) Evaluation contract & submission validation
- [x] [TASK-W2B](tasks/TASK-W2B.md) Dev benchmark, gold set & regression control
- [x] [TASK-W2C](tasks/TASK-W2C.md) Corpus parsing & canonicalization

### Wave 3 -- Parallel Baseline Build

- [x] [TASK-W3A](tasks/TASK-W3A.md) Chunking & hybrid indexing
- [x] [TASK-W3B](tasks/TASK-W3B.md) Retrieval, reranking & evidence selection
- [x] [TASK-W3C](tasks/TASK-W3C.md) Answer routing & typed solving
- [x] [TASK-W3D](tasks/TASK-W3D.md) Pipeline orchestration & submission packaging

## 2. Post-Baseline Tracks

> Baseline score: `total=0.2273` (2026-03-23). Primary levers in priority order: grounding, deterministic extraction, free-text grounding validation.

### Wave 4 -- Baseline Recovery & Structural Upgrade

> Wave 4 converts the updated document-processing architecture into execution-ready work packages. `TASK-W4A`, `TASK-W4B`, and `TASK-W4C` start in parallel; `TASK-W4D` depends on stable outputs from `TASK-W4B` and the chunk/schema changes that `TASK-W4C` freezes as accepted; `TASK-W4E` depends on the baseline multi-document path from `TASK-W4B` plus stable retrieval behavior from `TASK-W4D`.

- [x] [TASK-W4A](tasks/TASK-W4A.md) Page attribution precision & validation policy
- [x] [TASK-W4B](tasks/TASK-W4B.md) Structured typed solving, validation & legal prefilters
- [x] [TASK-W4C](tasks/TASK-W4C.md) Structural parser branch, normalization & table enrichment
- [x] [TASK-W4D](tasks/TASK-W4D.md) Retrieval upgrade, chunk calibration & asymmetric tuning
- [x] [TASK-W4E](tasks/TASK-W4E.md) Cross-case decomposition & multi-document orchestration

> The grouped tracks below remain thematic backlog buckets. The Wave 4 tasks above are the authoritative implementation units for execution and acceptance.

### High Priority (score-blocking)

- [x] [TRACK-GROUNDING] Improve retrieved_chunk_pages precision -- addressed by TASK-W4A two-pass attribution
- [x] [TRACK-NAME-EXTRACT] Name extraction -- addressed by TASK-W4B schema-first typed solving
- [x] [TRACK-DET-EXTRACT] Reduce extractor over-conservatism -- addressed by TASK-W4B (deterministic demoted to guardrail)
- [x] [TRACK-FT-GROUNDING] Free-text grounding validation tuning -- addressed by TASK-W4A validation degradation policy

### Medium Priority (incremental gain)

- [ ] [TRACK-DENSE-AB] A/B dense retriever: pplx-embed-v1-0.6B vs baseline
- [ ] [TRACK-OCR-HARD-PAGES] DeepSeek-OCR-2 hard-page fallback
- [ ] [TRACK-TTFT-OPT] TTFT optimization (batching, caching, async orchestration)

### Exploratory

- [ ] [TRACK-LIGHT-GRAPH] Light graph layer (section->clause, definition->usage, main->annex)
- [ ] [TRACK-AGENTIC-ESCALATION] Selective agentic escalation for hard multi-hop / free_text
- [x] [TRACK-COMPARATIVE-DECOMP] Comparative query decomposition -- addressed by TASK-W4E rule-based decomposition
