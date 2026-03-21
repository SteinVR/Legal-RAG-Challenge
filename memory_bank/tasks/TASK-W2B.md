# Task: TASK-W2B

## 1. Summary

**Title**: Dev benchmark, gold set & regression control  
**Description**: Build local benchmark assets and regression controls for controlled evolution of the pipeline.  
**Status**: Done
**Wave**: Wave 2 -- Evaluation & Corpus Framing

## 2. Scope

- **In scope**:
  - Dev gold set: fully reviewed warm-up benchmark covering all 100 questions with answers + support pages
  - No separate silver set: replaced by the accepted decision to maintain a single gold benchmark for the full warmup set
  - Regression harness: run benchmark, compare against previous config version
  - Slice-by-slice metrics (by answer_type, by question difficulty, by doc count)
  - Consistency testing: repeated runs, variance analysis, unstable question detection
  - Versioned config comparison: before/after metrics per config change
  - Benchmark artifacts and manifests needed to operate the full warmup goldset workflow
- **Out of scope**: experiment tracks (backlog)
- **Dependencies**: TASK-W1A (corpus access), TASK-W2A (scorer/validator contract)

## 3. Implementation Plan



## 4. Working Notes

Baseline changes only after regression run passes. Any new hypothesis must: (1) not break telemetry, (2) improve on fixed dev benchmark, (3) not hurt grounding-first profile. Gold/silver assets start in this wave and expand as more pipeline stages become available.

## 5. Outcome

**Result**: Completed. W2B now consists of the repaired benchmark/reporting contract plus a full warmup100 goldset workflow and artifacts under `data/dev/gold/warmup100/`, with compare/consistency CLI support and dedicated tests in the repository. Per accepted task decision, the full 100-question goldset replaced the earlier subset-gold-plus-silver split.  
**Next action**: Use the completed W2B benchmark baseline for Wave 3/4 regression checks and submission iteration.
