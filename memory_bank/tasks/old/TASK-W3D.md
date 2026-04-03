# Task: TASK-W3D

## 1. Summary

**Title**: Pipeline orchestration & submission packaging  
**Description**: Wire all stages into single pipeline run; implement telemetry and submission packaging.  
**Status**: Done
**Wave**: Wave 3 -- Parallel Baseline Build

## 2. Scope

- **In scope**:
  - Pipeline orchestrator (main.py): ingest -> index -> (per question) retrieve -> answer -> pack
  - Telemetry packer: timing, usage, retrieved_chunk_pages
  - Submission packager: submission.json + code_archive.zip
  - Submit gate: pre-submit validation (doc_id, page_numbers, timing, archive size)
  - Architecture summary generation (max 500 chars)
  - Trace ID per run and per question
- **Out of scope**: regression/consistency testing (TASK-W2B)
- **Dependencies**: TASK-W2A (validator contract), frozen stage contracts from TASK-W3A/TASK-W3B/TASK-W3C; implementation may proceed in parallel with mocks/stubs once contracts are frozen

## 3. Implementation Plan

- Implemented `src/submission/{telemetry_packer.py, submit_gate.py, packager.py, pipeline.py}`.
- Wired `build-submission` in `src/main.py` and kept the rest of the CLI surface intact.
- Added restart-safe reuse checks, trace manifest writing, wall-clock telemetry, local validation before packaging, code archive size/secret gates, and free-text model fallback.

## 4. Working Notes

TTFT measurement: time from question receipt to first token of final answer. If no streaming, `ttft_ms = total_time_ms`.
Code archive max 25 MB and excludes secret files such as `.env` / `.env.*`.
`build-submission` writes `submission.json`, `code_archive.zip`, and `trace_manifest.json` only after local validation passes.
`SubmitGate` follows the configured unanswerable retrieval policy.

## 5. Outcome

**Result**: Completed on 2026-03-22; the W3D submission pipeline is runnable and the submission-suite is green.
**Next action**: None for W3D; remaining work belongs to lint cleanup and post-baseline tracks.
