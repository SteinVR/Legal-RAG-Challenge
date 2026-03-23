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

### High Priority (score-blocking)

- [ ] [TRACK-GROUNDING] Improve retrieved_chunk_pages precision -- G=0.570 is multiplicative; increase precision of page attribution
- [ ] [TRACK-NAME-EXTRACT] Name extraction -- 0/15 correct; extractors return null for all name-type questions
- [ ] [TRACK-DET-EXTRACT] Reduce extractor over-conservatism -- 47/70 null answers; det=0.129; loosen thresholds for boolean/number/date
- [ ] [TRACK-FT-GROUNDING] Free-text grounding validation tuning -- 16 fallbacks to null; `FreeTextGroundingValidationError` too strict

### Medium Priority (incremental gain)

- [ ] [TRACK-DENSE-AB] A/B dense retriever: pplx-embed-v1-0.6B vs baseline
- [ ] [TRACK-OCR-HARD-PAGES] DeepSeek-OCR-2 hard-page fallback
- [ ] [TRACK-TTFT-OPT] TTFT optimization (batching, caching, async orchestration)

### Exploratory

- [ ] [TRACK-LIGHT-GRAPH] Light graph layer (section->clause, definition->usage, main->annex)
- [ ] [TRACK-AGENTIC-ESCALATION] Selective agentic escalation for hard multi-hop / free_text
- [ ] [TRACK-COMPARATIVE-DECOMP] Comparative query decomposition (multi-doc, amendment-vs-current)
