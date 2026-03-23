# Project State: Agentic-RAG-Challenge

> Compact RAPID project status. Keep under 150 lines.

---

## 1. Delivery Snapshot

| Attribute | Value |
|-----------|-------|
| Blockers | No active product blockers |
| Methodology | RAPID |
| Completed scope | TASK-W1A through TASK-W3D complete; TASK-BASELINE postmortem complete; Wave 4 specs finalized (TASK-W4A/B/C/D/E); full baseline pipeline operational with numbered operator scripts (`scripts/00_*`–`07_*`) |
| Current focus | Wave 4 execution: W4A/W4B/W4C start in parallel; W4D depends on W4A+W4B+W4C; W4E depends on W4A+W4B+W4D |
| Validation baseline | Verified on 2026-03-23 from `.venv`: `PYTHONPATH=. pytest -q` → `187 passed`; `PYTHONPATH=. ruff check src tests` → `All checks passed!` |
| First full baseline result | 100-question warmup submission completed 2026-03-23; `total_score=0.2273`; grounding G=0.570 is primary optimization lever |
| Canonical architecture | `docs/unified_document_processing_architecture.md` — target architecture combining opendataloader-pdf, external/RAG-Challenge-2, and current project. Review at `docs/Document_Processing_Architecture_Review.md` |

---

## 2. Known Issues / Tech Debt

| Date | Issue | Priority | Status |
|------|-------|----------|--------|
| 2026-03-17 | retrieved_chunk_pages [] vs non-empty ambiguity in EVALUATION.md | High | Open -- needs organizer clarification |
| 2026-03-17 | ~~Codex OAuth stability for 900-question batch untested~~ | Medium | **Resolved** -- generation backend uses OpenAI API |
| 2026-03-21 | Warmup real-corpus smoke does not exercise OCR-selected pages | Medium | Open -- OCR provenance depends on dedicated fixtures/scanned samples |
| 2026-03-23 | Name extraction zero-correct (0/15 name questions) | High | Addressed by TASK-W4B (planned) |
| 2026-03-23 | Deterministic extractor over-conservatism: 47/70 null answers | High | Addressed by TASK-W4B (planned) |
| 2026-03-23 | Free-text grounding validation too strict: 16 fallbacks to null | Medium | Addressed by TASK-W4A validation policy (planned) |
| 2026-03-23 | Grounding G=0.570 -- retrieved_chunk_pages precision too low | High | Addressed by TASK-W4A two-pass attribution (planned) |

---

## 3. Architecture Deviations

| Date | Area | Deviation | Reason |
|------|------|-----------|--------|
| 2026-03-22 | Current runnable baseline | No active architecture deviation tracked for the W3A/W3B/W3C/W3D submission path | The remaining work is post-baseline optimization, not a design mismatch |
| 2026-03-23 | Parser | opendataloader-pdf hybrid mode not yet integrated; current baseline runs local-only | TASK-W4C is the planned integration point; local-only is acceptable fallback per spec |
| 2026-03-23 | Table extraction | `table_method="cluster"` not yet set as default | TASK-W4C will enforce this; current baseline predates this decision |

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

---

## 5. Accumulated Context

- 2026-03-18 to 2026-03-21: W1A through W2C delivered config/env loading, evaluation contract, dev gold benchmark, and schema-first canonical corpus.
- 2026-03-21 to 2026-03-22: W3A/W3B/W3C/W3D delivered chunking, retrieval, answering, and submission pipeline. All merged to `main`.
- 2026-03-23: Baseline corrections (PaddleOCR v3 migration, Qwen3 prompt split, causal reranker, lint), operator scripts, logging fixes. Test baseline: `187 passed`, `ruff: All checks passed`.
- 2026-03-23: First full 100-question warmup baseline completed. `total=0.2273`, `det=0.129`, `asst=0.987`, `G=0.570`, `T=1.000`. 37 real answers, 47 null, 16 grounding-fallback. Corpus: 30 docs, 590 pages, 6631 chunks. Full postmortem in `memory_bank/tasks/TASK-BASELINE.md`.
- 2026-03-23: Canonical target architecture written at `docs/unified_document_processing_architecture.md`; review at `docs/Document_Processing_Architecture_Review.md`. Combines opendataloader-pdf, external/RAG-Challenge-2, and current project design.
- 2026-03-23: Wave 4 task specs finalized -- TASK-W4A (page attribution), TASK-W4B (typed extraction), TASK-W4C (structural parser), TASK-W4D (retrieval upgrade), TASK-W4E (cross-case orchestration). W4A/W4B/W4C start in parallel. TASKS.md updated with Wave 4 section and dependency graph.
- 2026-03-24: Canonical architecture rewritten from "extraction-first typed answering" to "retrieval-first, schema-first typed solving with deterministic validation." TASK-W4B completely rewritten; schema registry with `is_answerable`, typed `final_answer`, `relevant_pages`, and short `reasoning_summary` is now the primary post-retrieval path. Deterministic extractors are guardrails. TASK-W4A Pass B now explicitly consumes solver-reported `relevant_pages` as narrowing signal. TASK-W4D retrieval owns solver-ready evidence packaging. TASK-W4E reuses W4B schema registry and validator rules. `codex_provider.py` model fixed from `gpt-5-mini` to `gpt-5.4-mini` (reasoning model).
