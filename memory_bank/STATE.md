# Project State: Agentic-RAG-Challenge

> Compact RAPID project status. Keep under 150 lines.

---

## 1. Delivery Snapshot

| Attribute | Value |
|-----------|-------|
| Blockers | No active execution blockers; strict smoke and full e2e answer-generation gates are green |
| Methodology | RAPID |
| Delivered | Waves 1-4 complete; TASK-BASELINE postmortem complete; canonical e2e pipeline verified on RTX 4060 |
| Current focus | Continue strict eval hardening with no hidden fallback behavior; push grounding quality after stability recovery |
| Latest validation | 2026-04-06: `tests/test_smoke_warmup_runtime.py` passed; full warmup e2e run `submission_e2e_20260406_fix` completed 100/100 with restored assistant coverage (`assistant_score_count=30`) |
| Baseline reference | 2026-03-23 warmup submission: `total_score=0.2273`, grounding `G=0.5702`; grounding remains the main optimization lever |
| Canonical architecture | `docs/unified_document_processing_architecture.md`; governance chain stays `memory_bank/ARCHITECTURE.md` -> `memory_bank/component_design.md` -> `memory_bank/specs/` -> `memory_bank/tasks/` |

---

## 2. Known Issues / Tech Debt

| Date | Issue | Priority | Status |
|------|-------|----------|--------|
| 2026-03-17 | retrieved_chunk_pages [] vs non-empty ambiguity in EVALUATION.md | High | Open -- needs organizer clarification |
| 2026-03-21 | Warmup real-corpus smoke does not exercise OCR-selected pages | Low | Open -- warmup corpus is born-digital (all native); GPU OCR loaded but not triggered. Need scanned PDF fixtures to exercise OCR path |
| 2026-04-06 | Smoke regression in `test_warmup_smoke_questions_no_openai` (`question_id=5d271f...`) | High | Resolved -- targeted retrieval/grounding fixes plus warmup smoke expansion; test now passes |
| 2026-04-06 | Assistant coverage collapse (`assistant_score_count=0`) in fullrun benchmark summary | High | Resolved -- free-text scoring path recovered; current run reports `assistant_score_count=30`, `assistant=0.9867` |

---

## 3. Architecture Deviations

| Date | Area | Deviation | Reason |
|------|------|-----------|--------|


---

## 4. Key Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-17 | RAPID methodology | Delivery is gated by deadline, feedback loops, and iterative hardening rather than broad exploration |
| 2026-03-17 | Core stack standardized | `PaddleOCR-VL-1.5` for parsing, `Qwen3-Embedding-0.6B` + `Qwen3-Reranker-0.6B` for retrieval, OpenAI API for generation, Qdrant for persistence |
| 2026-03-21 | Schema-first corpus contract | One ingestion SSOT with quality gates keeps page and table provenance stable |
| 2026-03-23 | Typed answering is primary | Schema-first solving is the main path; deterministic logic only fills guardrail and recomposition gaps |
| 2026-03-23 | Retrieval stays hybrid | Dense+sparse Qdrant retrieval plus reranking remains the default search strategy |
| 2026-03-24 | Provider failures stay explicit | Strict schemas, bounded retries, and no silent fallback prevent hidden contract drift |

---

## 5. Accumulated Context

- 2026-03-23: Baseline was established and documented: 100-question warmup, `total=0.2273`, `det=0.129`, `G=0.570`, 30 docs, 590 pages, 6631 chunks, with grounding as the main blocker.
- 2026-03-23 to 2026-03-25: Wave 4 landed across parser, retrieval, typed answering, and cross-case decomposition. Key hardening included strict parser contracts, schema-first solving, reasoning-model provider fixes, and test stabilization (`342 passed`, `ruff clean`).
- 2026-03-25 to 2026-04-03: Full e2e reruns verified the canonical pipeline on GPU. Corpus re-parse produced `opendataloader:tagged` provenance, GPU OCR stayed idle on born-digital pages, index rebuilt to `3804` chunks, and the warmup submission moved to the current tracking state.
- 2026-04-06: Recovery run `submission_e2e_20260406_fix` completed with reused corpus/index, generated full artifact set, and restored assistant scoring (`assistant_score_count=30`, `assistant=0.9867`). Overall improved from `0.3402` to `0.5241` vs `submission_fullrun_20260406_001200`.

---

## 6. Tracking

### 6.1 Run Results

| Run | Total | Deterministic | Assistant | Grounding | TTFT ms | TTFT Multiplier | Warnings |
|-----|-------|---------------|-----------|-----------|---------|-----------------|----------|
| Baseline (`submission_baseline_backup`, mirrors `submission_full`) | 0.2273 | 0.1286 | 0.9867 | 0.5702 | 1321.86 | 1.0329 | 0 |
| Previous (`submission_w4v2`) | 0.4938 | 0.8286 | 0.9867 | 0.5888 | 5524.91 | 0.9573 | 25 |
| Previous Fullrun (`submission_fullrun_20260403_190231`) | 0.4866 | 0.8714 | 0.9867 | 0.5590 | 4745.49 | 0.9609 | 32 |
| Current Fullrun (`submission_fullrun_20260406_001200`) | 0.3402 | 0.8429 | 0.0000 | 0.6023 | 5342.02 | 0.9573 | 27 |
| Recovery Fullrun (`submission_e2e_20260406_fix`) | 0.5241 | 0.8714 | 0.9867 | 0.6015 | 4600.94 | 0.9616 | 26 |

### 6.2 Latest Comparison (Recovery vs 2026-04-06 fullrun)

- Artifacts: `data/warmup/submission_e2e_20260406_fix/benchmark_report.json` and `data/warmup/submission_e2e_20260406_fix/comparison_vs_prev_fullrun.json`.
- Overall delta vs `submission_fullrun_20260406_001200`: `total +0.1839`, `det +0.0286`, `assistant +0.9867`, `grounding -0.0007`, `ttft_multiplier +0.0043`.
- Runtime behavior: `build-submission` reused corpus/index and completed QA stage in ~`460141 ms`; runtime log `logs/project/runtime/warmup/20260405T224512Z_build-submission_cb9589bdeaea4bf5ad95272545de12fc.jsonl`.
- Quality note: free_text assistant slice recovered (from zero-coverage collapse to normal benchmark scoring), while grounding stayed essentially flat.
