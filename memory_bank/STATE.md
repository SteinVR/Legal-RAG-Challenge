# Project State: Agentic-RAG-Challenge

> Compact RAPID project status. Keep under 150 lines.

---

## 1. Delivery Snapshot

| Attribute | Value |
|-----------|-------|
| Blockers | No active product blockers; baseline is runnable end-to-end with operator scripts |
| Methodology | RAPID |
| Completed scope | TASK-W1A through TASK-W3D complete; full baseline pipeline operational with numbered operator scripts (`scripts/00_*`–`07_*`) |
| Current focus | Post-baseline exploration tracks (TRACK-DENSE-AB, TRACK-OCR-HARD-PAGES, etc.); first real warmup/private submission |
| Validation baseline | Verified on 2026-03-23 from `.venv`: `PYTHONPATH=. pytest -q` → `187 passed`; `PYTHONPATH=. ruff check src tests` → `All checks passed!` |

---

## 2. Known Issues / Tech Debt

| Date | Issue | Priority | Status |
|------|-------|----------|--------|
| 2026-03-17 | retrieved_chunk_pages [] vs non-empty ambiguity in EVALUATION.md | High | Open -- needs organizer clarification |
| 2026-03-17 | Codex OAuth stability for 900-question batch untested | Medium | Open -- validate early |
| 2026-03-21 | Warmup real-corpus smoke does not exercise OCR-selected pages | Medium | Open -- available warmup PDFs validate native/table/artifact paths well, but OCR provenance still depends on dedicated fixtures/scanned samples |
| 2026-03-22 | ~~Repository-wide `ruff check src tests` currently fails~~ | Medium | **Resolved** 2026-03-23 -- all lint issues fixed |

---

## 3. Architecture Deviations

| Date | Area | Deviation | Reason |
|------|------|-----------|--------|
| 2026-03-22 | Current runnable baseline | No active architecture deviation is currently tracked for the W3A/W3B/W3C/W3D submission path | The remaining work is lint debt and post-baseline exploration, not a design mismatch |

---

## 4. Key Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-17 | RAPID methodology | Engineering competition with tight deadline, not ML training |
| 2026-03-17 | PaddleOCR-VL-1.5 as primary parser | 0.9B, page-level, cross-page tables; ingestion is foundational |
| 2026-03-17 | Qwen3-Embedding-0.6B + Qwen3-Reranker-0.6B | Unified ecosystem, instruction-aware, MRL, 32K context, matched reranker |
| 2026-03-17 | Codex via OAuth as primary generation backend | Cost-efficient; provider abstraction for fallback |
| 2026-03-17 | Qdrant embedded as vector store | Dense + sparse hybrid, payload filtering, persistence, no infra overhead |
| 2026-03-17 | Grounding-first optimization | G is multiplicative in scoring formula; recall > precision (beta=2.5) |
| 2026-03-19 | Benchmark compare/consistency CLI now targets the current benchmark run-report schema only | Removes misleading legacy fallback and keeps W2B report contracts explicit |
| 2026-03-21 | W2C canonical corpus contract is now schema-first and quality-gated | Reduces parser/serializer/service drift and locks page/table provenance to one ingestion SSOT |
| 2026-03-21 | Wave 3 baseline service layers were merged to `main` before pipeline orchestration | Indexing, retrieval, and answering can now progress independently of the still-pending end-to-end orchestration/package layer |
| 2026-03-22 | W3D submission orchestration completed the runnable Wave 3 path | `build-submission`, telemetry packing, local validation, trace manifests, and archive gating now bind W3A/W3B/W3C into a runnable submission pipeline |
| 2026-03-23 | PaddleOCR v3 `.predict()` migration | Old `.ocr()` API replaced; `ocr_unavailable_policy` set to `error` to catch missing runtime early |
| 2026-03-23 | Qwen3 embedding prompt_name split: `"document"` for indexing, `"query"` for retrieval | Aligns with Qwen3-Embedding best practices; `build_query_embedder()` added |
| 2026-03-23 | Reranker `local_files_only=True` | Prevents accidental HuggingFace downloads at runtime |
| 2026-03-23 | Operator scripts pipeline (`scripts/00_*`–`07_*`) | Reproducible numbered shell scripts for full baseline execution |

---

## 5. Accumulated Context

- 2026-03-18 to 2026-03-19: TASK-W1A delivered config/env loading, phase-local sync, API client, CLI commands, and a live warmup sync with 100 questions and 30 PDFs staged under `data/warmup/`.
- 2026-03-19: TASK-W2A delivered local submission validation/scoring, config-driven unanswerable retrieval policy, and evaluation CLI coverage.
- 2026-03-19: TASK-W2B repaired the dev benchmark/reporting contract, unified compare/consistency flows around current run reports, and passed the recorded quality gate; the broader W2B deliverables remain in progress.
- 2026-03-21: W2B is considered complete under the accepted task decision to build a goldset for all 100 warmup questions instead of maintaining a separate 25-30 question gold subset plus silver set.
- 2026-03-20 to 2026-03-21: TASK-W2C was rebuilt around `src/common/schemas.py` as the ingestion SSOT, with centralized page provenance, hardened table serialization, complete-artifact skip logic, expanded invariant-based tests, green quality gate, and final independent review approval.
- 2026-03-21: Real warmup smoke validation passed on 10 selected PDFs and then on all 30 available warmup PDFs; native/table/artifact paths looked healthy, but the current dataset did not trigger any OCR-selected pages.
- 2026-03-21: TASK-W3A, TASK-W3B, and TASK-W3C were implemented in isolated worktrees, quality-gated, merged to `main`, and recorded in `logs/agents/W3ABC_Codex_wave-3-orchestration_23-06_21-03-2026.md`.
- 2026-03-22: TASK-W3D completed the submission pipeline in `src/submission/` and `src/main.py`.
- 2026-03-23: First smoke baseline run applied on-site corrections: PaddleOCR v3 API migration, Qwen3 embedding prompt_name split (`document`/`query`), reranker offline-only loading, pipeline ValueError fallback for safe per-question failure, lint debt fully resolved. Operator scripts (`scripts/00_*`–`07_*`) added for reproducible end-to-end execution. Test baseline: `187 passed`, `ruff: All checks passed`.
