# Task: W3B Working Journal

**Spec:** [SPEC_W3B.md](../specs/SPEC_W3B.md)

## Working Notes

- Scope is frozen by `../../.apm/worktrees/REF-PLANS/src/answering/migration-plan.md`.
- This task preserves schema-first typed answering, two-pass page attribution, and decomposition while breaking `service.py` into owned modules.
- The main risk is answer-semantics drift during extraction of schemas, metadata, deterministic guardrails, and solver logic.
- Verification should cover typed answer smokes, decomposition smokes, page-trace comparison, and one downstream submission question-run.
- Implemented the orchestration wrapper in `src/answering/service.py`, moved shared contracts/schemas/metadata into dedicated modules, added deterministic helper seam, and wired decomposition back into the answering entrypoint.
- Added answering and attribution boundary logs, updated page attribution to use retrieval contracts, and moved decomposition ownership out of submission orchestration.
- Closed the W3B review findings: decomposition fallback now uses `answer_without_decomposition()` instead of re-entering `answer_question()`, `deterministic.py` is a real module, free-text attribution emits start/complete on the normal and low-confidence paths, and the architecture docs now match the split topology.
- Smoke verification passed for `tests/test_answering_service_regressions.py`, `tests/test_submission_regressions.py`, and `tests/test_runtime_logging.py` via `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`.
- Completed the remaining extraction cleanup: `solver.py` now consumes deterministic guardrails/extractors from `deterministic.py`, page evidence helpers live in `page_attribution.py`, and the answering entrypoint only keeps provider-facing orchestration and page-trace composition.
- Updated `ARCHITECTURE.md` and `component_design.md` so the documented ownership matches the code again after the split.
- Restored the missing date helpers in `deterministic.py` so `_extract_date_candidates()` can resolve ISO and textual dates again.
- Cleaned the reviewer’s exact lint scope with `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/answering tests/test_answering_service_regressions.py tests/test_submission_regressions.py tests/test_runtime_logging.py`.
- Verified date extraction behavior in the project env: `_extract_dates_from_text('The agreement was signed on 2024-01-15 and renewed on 15 March 2025.')` returns `['2024-01-15', '2025-03-15']`.

## Review Findings

- P0: recursive decomposition fallback when no subquestions were produced. Resolved by adding `AnsweringService.answer_without_decomposition()` and routing `answer_with_decomposition()` fallback through it.
- P1: incomplete extraction split. Resolved by moving schema ownership to `answer_schemas.py`, query metadata to `query_metadata.py`, and making `deterministic.py` the concrete helper module used by the answering facade.
- P1: missing free-text attribution boundary logs. Resolved by logging `answering.attribution.start/complete` on the normal free-text path and on the low-confidence free-text recovery path.
- P2: missing regressions. Resolved by adding tests for unsupported-template decomposition fallback and free-text attribution logging.
- P1: solver still shadowed deterministic guardrails/extractors and page-evidence helpers. Resolved by moving the deterministic helper surface into `deterministic.py`, moving page helper utilities into `page_attribution.py`, and trimming `solver.py` to provider-facing execution plus imports.
- P2: memory bank ownership notes lagged the actual module split. Resolved by updating `ARCHITECTURE.md` and `component_design.md` to reflect the current ownership.
- P1: date extraction helpers were dropped during the split, breaking `_extract_date_candidates()`. Resolved by restoring `_safe_iso_date()` and `_safe_iso_date_from_textual_match()` in `deterministic.py`.
- P2: reviewer lint gate still failed on import-order and unused-import issues in the answering scope. Resolved by running Ruff auto-fixes and rechecking the reviewer’s exact scope until it passed cleanly.

## Outcome

**Result:** Ready for closure
**Key findings:** Answering now has a thin orchestration entrypoint, dedicated shared contracts, a concrete deterministic helper module, explicit page-attribution helpers, and logged decomposition / attribution boundaries. The reviewer’s final lint scope is now clean.
**Next action:** None unless a final review uncovers a regression; otherwise merge / commit the REF-PLANS worktree changes.
