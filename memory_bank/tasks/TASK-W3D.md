# Task: TASK-W3D

## 1. Summary

**Title**: Pipeline orchestration & submission packaging  
**Description**: Wire all stages into single pipeline run; implement telemetry and submission packaging.  
**Status**: Planned
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



## 4. Working Notes

TTFT measurement: time from question receipt to first token of final answer. If no streaming, ttft_ms = total_time_ms.
Code archive max 25 MB.
doc_id must be PDF filename (SHA-like string), page_numbers must be physical 1-based.

## 5. Outcome

**Result**: [Pending]  
**Next action**: freeze orchestration contracts, then implement in Wave 3 with test doubles and bind to real stages as they land
