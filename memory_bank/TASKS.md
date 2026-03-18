# Task Board (RAPID): Agentic-RAG-Challenge

> Wave-based plan. Tasks inside the same wave may run in parallel when their declared dependencies are satisfied. Details in `memory_bank/tasks/{TASK_ID}.md`.

## 1. Active Plan (Wave-Based)

### Wave 1 -- Foundation

- [x] [TASK-W1A](./TASK-W1A.md) Workspace, config & corpus access

### Wave 2 -- Evaluation & Corpus Framing

- [ ] [TASK-W2A](./TASK-W2A.md) Evaluation contract & submission validation
- [ ] [TASK-W2B](./TASK-W2B.md) Dev benchmark, gold set & regression control
- [ ] [TASK-W2C](./TASK-W2C.md) Corpus parsing & canonicalization

### Wave 3 -- Parallel Baseline Build

- [ ] [TASK-W3A](./TASK-W3A.md) Chunking & hybrid indexing
- [ ] [TASK-W3B](./TASK-W3B.md) Retrieval, reranking & evidence selection
- [ ] [TASK-W3C](./TASK-W3C.md) Answer routing & typed solving
- [ ] [TASK-W3D](./TASK-W3D.md) Pipeline orchestration & submission packaging

## 2. Post-Baseline Tracks

- [ ] [TRACK-DENSE-AB] A/B dense retriever: pplx-embed-v1-0.6B vs baseline
- [ ] [TRACK-OCR-HARD-PAGES] DeepSeek-OCR-2 hard-page fallback
- [ ] [TRACK-LIGHT-GRAPH] Light graph layer (section->clause, definition->usage, main->annex)
- [ ] [TRACK-AGENTIC-ESCALATION] Selective agentic escalation for hard multi-hop / free_text
- [ ] [TRACK-COMPARATIVE-DECOMP] Comparative query decomposition (multi-doc, amendment-vs-current)
- [ ] [TRACK-TTFT-OPT] TTFT optimization (batching, caching, async orchestration)
