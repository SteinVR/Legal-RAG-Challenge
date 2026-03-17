# Task: TASK-008

## 1. Summary

**Title**: Dev benchmark, regression harness, consistency testing  
**Description**: Build local evaluation infrastructure for controlled evolution of the pipeline.  
**Status**: Planned

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
- **Dependencies**: TASK-002 (scorer), TASK-007 (E2E pipeline)

## 3. Implementation Plan



## 4. Working Notes

Baseline changes only after regression run passes. Any new hypothesis must: (1) not break telemetry, (2) improve on fixed dev benchmark, (3) not hurt grounding-first profile.

## 5. Outcome

**Result**: [Pending]  
**Next action**: implement after TASK-007
