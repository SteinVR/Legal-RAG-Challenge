# Task: TASK-002

## 1. Summary

**Title**: Local evaluator & submission validator  
**Description**: Implement local scoring and validation that mirrors challenge rules. Enables measurement before burning remote submissions.  
**Status**: Planned

## 2. Scope

- **In scope**:
  - Submission JSON schema validator (question_id, answer types, doc_id, page_numbers, timing, usage)
  - Deterministic scorers: number (+-1%), boolean (exact), name (normalized exact), names (Jaccard), date (ISO 8601 exact), null policy
  - Grounding scorer: F-beta with beta=2.5 on (doc_id, page_number) pairs
  - Telemetry factor calculator
  - TTFT factor calculator
  - Composite score calculator: (0.7*S_det + 0.3*S_asst) * G * T * F
  - Switchable unanswerable policy (empty vs non-empty retrieved_chunk_pages)
- **Out of scope**: LLM-as-judge for free_text (use proxy/manual review instead)
- **Dependencies**: TASK-001 (schemas)

## 3. Implementation Plan



## 4. Working Notes

Known issue: EVALUATION.md says `retrieved_chunk_pages: []` for unanswerable (grounding 1.0), but telemetry validation says "non-empty". Default to `[]`; flag for organizer clarification.

## 5. Outcome

**Result**: [Pending]  
**Next action**: implement after TASK-001
