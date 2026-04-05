# Project State: Agentic-RAG-Challenge

> Compact RAPID project status. Keep under 150 lines.

---

## 1. Delivery Snapshot

| Attribute | Value |
|-----------|-------|
| Blockers | No active product blockers |
| Methodology | RAPID |
| Completed scope | Waves 1-4 complete (W1A through W4E); TASK-BASELINE postmortem complete; full e2e pipeline verified with GPU on RTX 4060 |
| Current focus | Wave 4 fully delivered and e2e verified. Ready for Wave 5 planning or 100-question re-evaluation run |
| Validation baseline | Verified on 2026-03-25: `pytest` → `342 passed`; `ruff` → clean; full e2e re-parse (opendataloader:tagged, 590pp, GPU OCR loaded) → re-index (3804 chunks) → smoke test 5/5 processed (4 answered, decomposition OK) |
| First full baseline result | 100-question warmup submission completed 2026-03-23; `total_score=0.2273`; grounding G=0.570 is primary optimization lever |
| Canonical architecture | `docs/unified_document_processing_architecture.md` — target architecture combining opendataloader-pdf, external/RAG-Challenge-2, and current project. Review at `docs/Document_Processing_Architecture_Review.md`. Memory Bank governance chain: `memory_bank/ARCHITECTURE.md` -> `memory_bank/component_design.md` -> `memory_bank/specs/` and `memory_bank/tasks/` |

---

## 2. Known Issues / Tech Debt

| Date | Issue | Priority | Status |
|------|-------|----------|--------|
| 2026-03-17 | retrieved_chunk_pages [] vs non-empty ambiguity in EVALUATION.md | High | Open -- needs organizer clarification |
| 2026-03-17 | ~~Codex OAuth stability for 900-question batch untested~~ | Medium | **Resolved** -- generation backend uses OpenAI API |
| 2026-03-21 | Warmup real-corpus smoke does not exercise OCR-selected pages | Low | Open -- warmup corpus is born-digital (all native); GPU OCR loaded but not triggered. Need scanned PDF fixtures to exercise OCR path |
| 2026-03-23 | Name extraction zero-correct (0/15 name questions) | High | **Resolved** -- TASK-W4B schema-first typed solving implemented |
| 2026-03-23 | Deterministic extractor over-conservatism: 47/70 null answers | High | **Resolved** -- TASK-W4B demoted deterministic to guardrail layer |
| 2026-03-23 | Free-text grounding validation too strict: 16 fallbacks to null | Medium | **Resolved** -- TASK-W4A validation degradation policy implemented |
| 2026-03-23 | Grounding G=0.570 -- retrieved_chunk_pages precision too low | High | **Resolved** -- TASK-W4A two-pass page attribution implemented |

---

## 3. Architecture Deviations

| Date | Area | Deviation | Reason |
|------|------|-----------|--------|
| 2026-03-22 | Current runnable baseline | No active architecture deviation tracked for the W3A/W3B/W3C/W3D submission path | The remaining work is post-baseline optimization, not a design mismatch |
| 2026-03-23 | ~~Parser~~ | ~~opendataloader-pdf hybrid mode not yet integrated~~ | **Resolved** -- TASK-W4C implemented hybrid mode as required default with fallback routing |
| 2026-03-23 | ~~Table extraction~~ | ~~`table_method="cluster"` not yet set as default~~ | **Resolved** -- TASK-W4C enforced `table_method="cluster"` as required default |

---

## 4. Key Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-17 | RAPID methodology | Tight engineering deadline, not ML training |
| 2026-03-17 | Core stack chosen | `PaddleOCR-VL-1.5` for parsing, `Qwen3-Embedding-0.6B` + `Qwen3-Reranker-0.6B` for retrieval, OpenAI API for generation, Qdrant for dense+sparse persistence |
| 2026-03-17 | Grounding-first optimization | Scoring is multiplicative, so grounding loss dominates end result |
| 2026-03-21 | Canonical corpus contract is schema-first and quality-gated | Locks page/table provenance to one ingestion SSOT and reduces parser/service drift |
| 2026-03-22 | Runnable submission pipeline complete | `build-submission`, telemetry packing, local validation, trace manifests, and archive gating bind the Wave 3 path |
| 2026-03-23 | Wave 4 parser contract is strict | `opendataloader-pdf` hybrid mode is required, `table_method="cluster"` is default, JSON is the only sidecar format, OCR absence fails fast |
| 2026-03-23 | Wave 4 answering contract is typed | Schema-first typed solving is primary; deterministic logic is guardrail only; two-pass page attribution is required |
| 2026-03-23 | Wave 4 retrieval contract stays hybrid | Qdrant dense+sparse remains the store; reranker is causal LM scoring |
| 2026-03-24 | Provider contract hardened | `gpt-5.4-mini` uses reasoning effort by answer type, strict schema requires all properties in `required`, max output raised to `2048` |
| 2026-03-25 | Cross-case solving is rule-based | 31/100 warmup cross-case questions follow regular patterns, so deterministic recomposition is sufficient |
| 2026-03-25 | Provider/schema failures must be explicit | Structured output retries are capped; no silent fallback for ingestion or generation contract breaks |

---

## 5. Accumulated Context

- 2026-03-18 to 2026-03-22: W1A-W3D delivered config/env loading, evaluation contract, gold benchmark, canonical corpus, chunking, retrieval, answering, and submission orchestration. All merged to `main`.
- 2026-03-23: Baseline was established and documented: 100-question warmup, `total=0.2273`, `det=0.129`, `G=0.570`, 30 docs, 590 pages, 6631 chunks, with grounding as the main blocker.
- 2026-03-23 to 2026-03-25: Wave 4 landed across parser, retrieval, typed answering, and cross-case decomposition. Key hardening included strict parser contracts, schema-first solving, reasoning-model provider fixes, and test stabilization (`342 passed`, `ruff clean`).
- 2026-03-25 to 2026-04-03: Full e2e reruns verified the canonical pipeline on GPU. Corpus re-parse produced `opendataloader:tagged` provenance, GPU OCR stayed idle on born-digital pages, index rebuilt to `3804` chunks, and the warmup submission moved to the current tracking state.

---

## 6. Tracking

### 6.1 Run Results

| Run | Total | Deterministic | Assistant | Grounding | TTFT ms | TTFT Multiplier | Warnings |
|-----|-------|---------------|-----------|-----------|---------|-----------------|----------|
| Baseline (`submission_baseline_backup`, mirrors `submission_full`) | 0.2273 | 0.1286 | 0.9867 | 0.5702 | 1321.86 | 1.0329 | 0 |
| Previous (`submission_w4v2`) | 0.4938 | 0.8286 | 0.9867 | 0.5888 | 5524.91 | 0.9573 | 25 |
| Current (`submission_fullrun_20260403_190231`) | 0.4866 | 0.8714 | 0.9867 | 0.5590 | 4745.49 | 0.9609 | 32 |
