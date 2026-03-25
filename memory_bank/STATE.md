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
| Canonical architecture | `docs/unified_document_processing_architecture.md` — target architecture combining opendataloader-pdf, external/RAG-Challenge-2, and current project. Review at `docs/Document_Processing_Architecture_Review.md` |

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
| 2026-03-17 | RAPID methodology | Engineering competition with tight deadline, not ML training |
| 2026-03-17 | PaddleOCR-VL-1.5 as primary parser | 0.9B, page-level, cross-page tables; ingestion is foundational |
| 2026-03-17 | Qwen3-Embedding-0.6B + Qwen3-Reranker-0.6B | Unified ecosystem, instruction-aware, MRL, 32K context, matched reranker |
| 2026-03-17 | OpenAI API as primary generation backend | Provider abstraction for fallback |
| 2026-03-17 | Qdrant embedded as vector store | Dense + sparse hybrid, payload filtering, persistence, no infra overhead |
| 2026-03-17 | Grounding-first optimization | G is multiplicative in scoring formula; recall > precision (beta=2.5) |
| 2026-03-21 | W2C canonical corpus contract is now schema-first and quality-gated | Reduces parser/serializer/service drift and locks page/table provenance to one ingestion SSOT |
| 2026-03-22 | W3D submission orchestration completed the runnable Wave 3 path | `build-submission`, telemetry packing, local validation, trace manifests, and archive gating now bind W3A/W3B/W3C into a runnable submission pipeline |
| 2026-03-23 | Reranker rewritten to causal LM scoring (yes/no probability) | `AutoModelForCausalLM` with system prompt template; correct approach for Qwen3-Reranker-0.6B |
| 2026-03-23 | Operator scripts pipeline (`scripts/00_*`–`07_*`) | Reproducible numbered shell scripts for full baseline execution |
| 2026-03-23 | Logging fully config-driven; OCR absence fails fast | `LoggingSettings.normalize_level()` before-validator; JSONL dir skip when disabled; `log_path` optional |
| 2026-03-23 | opendataloader-pdf hybrid mode is required path for Wave 4 | Local-only is fallback; hybrid is default for born-digital and layout-complex pages (TASK-W4C) |
| 2026-03-23 | `table_method="cluster"` required default | Required default for Wave 4 parser; deviation requires measured regression on legal PDFs (TASK-W4C) |
| 2026-03-23 | JSON is required sidecar format | Raw parse artifacts must be JSON; Markdown is debug only (TASK-W4C) |
| 2026-03-23 | Two-pass page attribution required | Pass A pre-answer pruning; Pass B post-answer finalization; validation degrades before suppressing answers (TASK-W4A) |
| 2026-03-24 | Schema-first typed solving replaces extraction-first as primary post-retrieval path | Deterministic logic demoted to guardrail layer (candidate generation, validation, normalization, rejection); schema registry with per-type Pydantic schemas is the primary solver (TASK-W4B rewritten) |
| 2026-03-24 | gpt-5.4-mini is a reasoning model with configurable reasoning effort | Reasoning effort defaults: high for boolean/name/names; medium for number/date/free_text; provider abstraction must support schema dispatch and effort controls |
| 2026-03-23 | Typed extraction upgraded per answer type | Boolean polarity, name/names extraction, confidence calibration; LLM table serialization benchmark-gated with kill switch (TASK-W4B) |
| 2026-03-23 | Qdrant hybrid (dense+sparse) stays as-is | No separate BM25 system; no architecture change to vector store (TASK-W4D) |
| 2026-03-23 | Annex/schedule chunk family OUT of scope for Wave 4 | Not in TASK-W4C scope |
| 2026-03-23 | XY-Cut++ calibration OUT of scope for Wave 4 | Not in TASK-W4C scope |
| 2026-03-25 | Cross-case decomposition is rule-based, not LLM-based | 31 cross-case questions (19 boolean, 12 name) have regular patterns; deterministic recomposition sufficient; no extra API calls for decomposition prompt |
| 2026-03-25 | Provider max_output_tokens increased 220→2048 | Reasoning models (gpt-5.4-mini) consume most tokens on thinking; 220 caused truncated JSON; 2048 is safe budget |
| 2026-03-25 | OpenAI strict schema requires all properties in required | Pydantic default-valued fields omitted from `required`; added `_strict_openai_schema()` post-processor in provider |

---

## 5. Accumulated Context

- 2026-03-18 to 2026-03-21: W1A through W2C delivered config/env loading, evaluation contract, dev gold benchmark, and schema-first canonical corpus.
- 2026-03-21 to 2026-03-22: W3A/W3B/W3C/W3D delivered chunking, retrieval, answering, and submission pipeline. All merged to `main`.
- 2026-03-23: Baseline corrections (PaddleOCR v3 migration, Qwen3 prompt split, causal reranker, lint), operator scripts, logging fixes. Test baseline: `187 passed`, `ruff: All checks passed`.
- 2026-03-23: First full 100-question warmup baseline completed. `total=0.2273`, `det=0.129`, `asst=0.987`, `G=0.570`, `T=1.000`. 37 real answers, 47 null, 16 grounding-fallback. Corpus: 30 docs, 590 pages, 6631 chunks. Full postmortem in `memory_bank/tasks/TASK-BASELINE.md`.
- 2026-03-23: Canonical target architecture written at `docs/unified_document_processing_architecture.md`; review at `docs/Document_Processing_Architecture_Review.md`. Combines opendataloader-pdf, external/RAG-Challenge-2, and current project design.
- 2026-03-23: Wave 4 task specs finalized -- TASK-W4A (page attribution), TASK-W4B (typed extraction), TASK-W4C (structural parser), TASK-W4D (retrieval upgrade), TASK-W4E (cross-case orchestration). W4A/W4B/W4C start in parallel. TASKS.md updated with Wave 4 section and dependency graph.
- 2026-03-24: Canonical architecture rewritten from "extraction-first typed answering" to "retrieval-first, schema-first typed solving with deterministic validation." TASK-W4B completely rewritten; schema registry with `is_answerable`, typed `final_answer`, `relevant_pages`, and short `reasoning_summary` is now the primary post-retrieval path. Deterministic extractors are guardrails. TASK-W4A Pass B now explicitly consumes solver-reported `relevant_pages` as narrowing signal. TASK-W4D retrieval owns solver-ready evidence packaging. TASK-W4E reuses W4B schema registry and validator rules. `codex_provider.py` model fixed from `gpt-5-mini` to `gpt-5.4-mini` (reasoning model).
- 2026-03-24 to 2026-03-25: Wave 4 A/B/C/D implemented and merged to `main` (0b8b7ab). Integration issues surfaced due to missing pre-defined cross-task contracts — provider schema dispatch, OCR GPU runtime, opendataloader hybrid URL, structured output API format. Two stabilization commits (d673a0b, 1c412da) resolved all contract mismatches, hardened runtime, and added 122+ new tests. All four W4 tasks have stabilized contracts and definitions of done locked in task files.
- 2026-03-25: TASK-W4E (cross-case decomposition) implemented. Rule-based decomposition for 31/100 cross-case warmup questions (19 boolean, 12 name). Disabled by default (`decomposition.enabled=false`). Provider fixes: OpenAI strict schema compliance, reasoning response parsing, max_output_tokens 220→2048, ISO date hint. Suite: 342 passed, ruff clean.
- 2026-03-25: Full e2e pipeline re-run on GPU (RTX 4060 8GB). Corpus re-parsed with W4C structural parser: all 590 pages → `opendataloader:tagged` provenance, 30 JSON sidecars in `raw_parse/opendataloader/`. GPU OCR (PP-OCRv5) loaded but not triggered (born-digital corpus). Index rebuilt: 3804 chunks (dense+sparse). Smoke test 5/5 questions: 4 answered, 1 null (number — model couldn't extract from evidence), decomposition correctly triggered on cross-case name question (`SCT 295/2025`). Wave 4 fully complete and e2e verified.
