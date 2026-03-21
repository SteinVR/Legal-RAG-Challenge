# Task: TASK-W2B

## 1. Summary

**Title**: Dev benchmark, gold set & regression control  
**Description**: Build local benchmark assets and regression controls for controlled evolution of the pipeline.  
**Status**: In Progress
**Wave**: Wave 2 -- Evaluation & Corpus Framing

## 2. Scope

- **In scope**:
  - Dev gold set: manually annotated subset (~25-30 questions) with answers + support pages
  - Dev silver set: all warm-up questions with auto-scored + spot-checked results
  - Regression harness: run benchmark, compare against previous config version
  - Slice-by-slice metrics (by answer_type, by question difficulty, by doc count)
  - Consistency testing: repeated runs, variance analysis, unstable question detection
  - Versioned config comparison: before/after metrics per config change
  - Leaderboard log: submission UUID, config version, expected vs observed deltas
- **Out of scope**: experiment tracks (backlog)
- **Dependencies**: TASK-W1A (corpus access), TASK-W2A (scorer/validator contract)

## 3. Implementation Plan



## 4. Working Notes

Baseline changes only after regression run passes. Any new hypothesis must: (1) not break telemetry, (2) improve on fixed dev benchmark, (3) not hurt grounding-first profile. Gold/silver assets start in this wave and expand as more pipeline stages become available.

## 5. Outcome

**Result**: Partially implemented. The dev benchmark/reporting layer was repaired, benchmark compare/consistency flows were aligned to the current run-report schema, and recorded verification is green; however, the broader W2B scope is not finished because the dev gold set, dev silver set, populated regression assets, and leaderboard-style tracking artifacts are still pending. The repaired benchmark/reporting surface is now committed in the main branch.  
**Next action**: Complete the remaining W2B deliverables: benchmark assets, regression-control datasets, and tracking/reporting artifacts.
