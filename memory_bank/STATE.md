# Project State: Agentic-RAG-Challenge

> Compact RAPID project status. Keep under 150 lines.

---

## 1. Delivery Snapshot

| Attribute | Value |
|-----------|-------|
| Blockers | No hard blocker; public evaluation-doc ambiguity on unanswerable grounding remains |
| Methodology | RAPID |
| Completed scope | TASK-W1A and TASK-W2A are complete; TASK-W2B has only its benchmark/reporting contract repaired and quality-gated locally |
| Current focus | Finish the remaining W2B benchmark-assets/regression-control scope, then continue Wave 2 corpus work (`TASK-W2C`) or start Wave 3 contracts |
| Validation baseline | Last recorded gate on 2026-03-19: benchmark-targeted tests passed, full `pytest` passed (`29 passed`), `ruff` passed, `compileall` passed |

---

## 2. Known Issues / Tech Debt

| Date | Issue | Priority | Status |
|------|-------|----------|--------|
| 2026-03-17 | retrieved_chunk_pages [] vs non-empty ambiguity in EVALUATION.md | High | Open -- needs organizer clarification |
| 2026-03-17 | Codex OAuth stability for 900-question batch untested | Medium | Open -- validate early |
| 2026-03-19 | TASK-W2B was previously over-marked as complete; only the benchmark/reporting contract repair is implemented so far | Medium | Open -- benchmark assets, datasets, and regression-control artifacts still need delivery |
| 2026-03-19 | TASK-W2B benchmark/reporting fixes are still uncommitted in the local working tree | Medium | Open -- sync is recorded from local state, commit/integration still pending |

---

## 3. Architecture Deviations

| Date | Area | Deviation | Reason |
|------|------|-----------|--------|
| -- | -- | None yet | -- |

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

---

## 5. Accumulated Context

- 2026-03-18 to 2026-03-19: TASK-W1A delivered config/env loading, phase-local sync, API client, CLI commands, and a live warmup sync with 100 questions and 30 PDFs staged under `data/warmup/`.
- 2026-03-19: TASK-W2A delivered local submission validation/scoring, config-driven unanswerable retrieval policy, and evaluation CLI coverage.
- 2026-03-19: TASK-W2B repaired the dev benchmark/reporting contract, unified compare/consistency flows around current run reports, and passed the recorded quality gate; the broader W2B deliverables remain in progress and the latest diff is still uncommitted.
