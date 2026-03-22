# Project State: Agentic-RAG-Challenge

> Compact RAPID project status. Keep under 150 lines.

---

## 1. Delivery Snapshot

| Attribute | Value |
|-----------|-------|
| Blockers | Wave 3 runnable-completeness gaps remain in W3A/W3B/W3C; public evaluation-doc ambiguity on unanswerable grounding also remains |
| Methodology | RAPID |
| Completed scope | TASK-W1A, TASK-W2A, TASK-W2B, and TASK-W2C are complete; TASK-W3A/W3B/W3C are merged as baseline service layers but still have open corrective runnable-completeness work; TASK-W3D is still pending |
| Current focus | Close runnable-completeness gaps inside TASK-W3A/TASK-W3B/TASK-W3C before starting TASK-W3D orchestration/submission packaging |
| Validation baseline | Verified on 2026-03-21 from `.venv`: `pytest -q` -> `150 passed`, `python -m compileall src` -> clean; current full `ruff check src tests` is not green because of 3 existing issues in `src/evaluation/goldset.py` and `tests/test_goldset.py` |

---

## 2. Known Issues / Tech Debt

| Date | Issue | Priority | Status |
|------|-------|----------|--------|
| 2026-03-17 | retrieved_chunk_pages [] vs non-empty ambiguity in EVALUATION.md | High | Open -- needs organizer clarification |
| 2026-03-17 | Codex OAuth stability for 900-question batch untested | Medium | Open -- validate early |
| 2026-03-22 | W3A persisted sparse/query path is incomplete for restartable retrieval | High | Open -- corrective pass needed inside W3A |
| 2026-03-22 | W3B lacks a concrete Qdrant-backed retrieval backend over persisted W3A artifacts | High | Open -- corrective pass needed inside W3B |
| 2026-03-22 | W3C lacks a concrete free-text provider and had post-merge runnable-boundary defects | High | Open -- corrective pass needed inside W3C |
| 2026-03-21 | Warmup real-corpus smoke does not exercise OCR-selected pages | Medium | Open -- available warmup PDFs validate native/table/artifact paths well, but OCR provenance still depends on dedicated fixtures/scanned samples |
| 2026-03-21 | Repository-wide `ruff check src tests` currently fails | Medium | Open -- 2 `E501` violations in `src/evaluation/goldset.py` and 1 import-order violation in `tests/test_goldset.py` |

---

## 3. Architecture Deviations

| Date | Area | Deviation | Reason |
|------|------|-----------|--------|
| 2026-03-22 | Wave 3 retrieval architecture | Baseline Wave 3 used a custom sparse-encoding/protocol-oriented path instead of a fully Qdrant-native runnable retrieval path | Independent review showed the baseline layers were mergeable and unit-tested but not yet runnable after restart |

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
| 2026-03-22 | Wave 3 corrective work now targets runnable completeness inside W3A/W3B/W3C before any W3D implementation | Independent review found that baseline-complete did not equal runnable-complete; acceptance now requires restartable artifacts, concrete retrieval/provider implementations, and system-level verification |

---

## 5. Accumulated Context

- 2026-03-18 to 2026-03-19: TASK-W1A delivered config/env loading, phase-local sync, API client, CLI commands, and a live warmup sync with 100 questions and 30 PDFs staged under `data/warmup/`.
- 2026-03-19: TASK-W2A delivered local submission validation/scoring, config-driven unanswerable retrieval policy, and evaluation CLI coverage.
- 2026-03-19: TASK-W2B repaired the dev benchmark/reporting contract, unified compare/consistency flows around current run reports, and passed the recorded quality gate; the broader W2B deliverables remain in progress.
- 2026-03-21: W2B is considered complete under the accepted task decision to build a goldset for all 100 warmup questions instead of maintaining a separate 25-30 question gold subset plus silver set.
- 2026-03-20 to 2026-03-21: TASK-W2C was rebuilt around `src/common/schemas.py` as the ingestion SSOT, with centralized page provenance, hardened table serialization, complete-artifact skip logic, expanded invariant-based tests, green quality gate, and final independent review approval.
- 2026-03-21: Real warmup smoke validation passed on 10 selected PDFs and then on all 30 available warmup PDFs; native/table/artifact paths looked healthy, but the current dataset did not trigger any OCR-selected pages.
- 2026-03-21: TASK-W3A, TASK-W3B, and TASK-W3C were implemented in isolated worktrees, quality-gated, merged to `main`, and recorded in `logs/agents/W3ABC_Codex_wave-3-orchestration_23-06_21-03-2026.md`.
- 2026-03-21: Current `main` now contains `src/indexing/service.py`, `src/retrieval/service.py`, `src/answering/service.py`, provider abstractions, and dedicated tests; end-to-end orchestration/submission packaging remains outside the merged scope.
- 2026-03-22: Independent review clarified that the merged Wave 3 baseline is not yet a runnable pipeline: W3A artifacts are not restart-complete for retrieval, W3B lacks a concrete Qdrant-backed backend, and W3C still needs a concrete provider path plus the already-started runnable-boundary fixes.
