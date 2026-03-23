# [W3FIX] [submission-review-regressions]

## Metadata + Exact Request
- Logged at: [23-03-2026 13:20]
- Agent identity: [Codex]
- Task: [W3FIX]
- Branch / worktree: [main at `/home/xeliaray/Projects/Agentic-RAG-Challenge`]
- Scope: [Fix review-reported submission/OCR/wrapper regressions while keeping the single-model `gpt-5.4-mini` policy]
- Exact user request or delegated objective:
  > [Implement the plan.]

## Task Setup
- Context used:
  - `src/submission/pipeline.py`
  - `src/answering/service.py`
  - `src/ingestion/ocr_engine.py`
  - `tools/operator_context.py`
  - `scripts/06_build_submission.sh`
  - `tests/test_submission_pipeline.py`
  - existing review findings and local reproductions
- Constraints:
  - do not touch user-modified `memory_bank/*`
  - keep free-text on `gpt-5.4-mini` only
  - use `.venv` for verification
- Planned approach:
  - remove pseudo-fallback model behavior
  - narrow safe unanswerable fallback to grounding-only failures
  - fix PaddleOCR v3 numpy result handling
  - make the shell wrapper allow deterministic-only preflight/runs without provider creds
  - add regression coverage for all changed behavior

## Implementation Log
1. Reworked the submission pipeline so free-text uses a single fixed model (`gpt-5.4-mini`) with no retry/fallback path, and model/provider failures now propagate as hard build failures.
2. Added `FreeTextGroundingValidationError` in the answering layer and changed the pipeline to convert only that exception into the canonical unanswerable answer.
3. Fixed OCR v3 line extraction to avoid boolean-coercing numpy `dt_polys`, and extended bbox normalization to handle numpy arrays directly.
4. Extended `tools/operator_context.py` with a derived `QUESTION_SET_REQUIRES_PROVIDER` flag and updated `scripts/06_build_submission.sh` to require provider creds only when the selected question set contains `free_text`.
5. Added regression coverage:
   - `tests/test_ingestion_ocr_engine.py`
   - `tests/test_operator_context.py`
   - `tests/test_build_submission_script.py`
   - expanded `tests/test_submission_pipeline.py`

## Verification
- `python -m compileall src tools tests`
- `Result: success`
- `.venv/bin/pytest -q tests/test_ingestion_ocr_engine.py tests/test_operator_context.py`
- `Result: 4 passed`
- `.venv/bin/pytest -q tests/test_build_submission_script.py`
- `Result: 2 passed`
- `.venv/bin/pytest -q tests/test_submission_pipeline.py -k 'gpt_5_4_mini_is_unavailable or grounding_validation_failures or generic_free_text_value_errors or deterministic_only_runs_without_provider_creds'`
- `Result: 3 passed`
- `.venv/bin/pytest -q tests/test_submission_pipeline.py tests/test_answering_service.py tests/test_ingestion_ocr_engine.py tests/test_operator_context.py tests/test_build_submission_script.py`
- `Result: 70 passed in 2.04s`
- `.venv/bin/ruff check src/answering/service.py src/answering/__init__.py src/submission/pipeline.py src/ingestion/ocr_engine.py tools/operator_context.py tests/test_submission_pipeline.py tests/test_ingestion_ocr_engine.py tests/test_operator_context.py tests/test_build_submission_script.py`
- `Result: All checks passed!`
- `bash -n scripts/06_build_submission.sh`
- `Result: success`

## Issues / Resolutions
- Issue: the review request to restore a fallback model conflicted with the explicit product decision to stay on `gpt-5.4-mini` only.
- Resolution: removed the pseudo-fallback machinery instead of restoring a second model.
- Issue: PaddleOCR v3 numpy polygons exposed a second latent bug in bbox normalization once line extraction stopped crashing.
- Resolution: extended `_normalize_bbox` to accept numpy arrays, not just Python lists/tuples.
- Issue: `memory_bank/ARCHITECTURE.md` and `memory_bank/STATE.md` were already dirty in the worktree.
- Resolution: left them untouched.

## Artifacts
- Files touched:
  - `scripts/06_build_submission.sh`
  - `src/answering/__init__.py`
  - `src/answering/service.py`
  - `src/ingestion/ocr_engine.py`
  - `src/submission/pipeline.py`
  - `tests/test_build_submission_script.py`
  - `tests/test_ingestion_ocr_engine.py`
  - `tests/test_operator_context.py`
  - `tests/test_submission_pipeline.py`
  - `tools/operator_context.py`
  - `logs/agents/W3FIX/W3FIX_Codex_submission-review-regressions_13-20_23-03-2026.md`
- Reports, plots, logs, or other evidence:
  - this activity log
- Verification artifacts:
  - green compileall, targeted pytest, expanded pytest, targeted ruff, and shell syntax checks listed above

## Result / Conclusions (Exact Answer to User)
> The planned fixes are implemented: `build-submission` now fails hard when `gpt-5.4-mini` is unavailable or a real provider/config error occurs, grounding-only free-text contradictions still degrade to the canonical unanswerable answer, PaddleOCR v3 numpy outputs no longer crash OCR parsing, and `06_build_submission.sh` now allows deterministic-only preflight/runs without provider credentials. The changed areas are covered by new regression tests, and the targeted verification set passed (`70 passed`, `ruff` clean, shell syntax clean).
