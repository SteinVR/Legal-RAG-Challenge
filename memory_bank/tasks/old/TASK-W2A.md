# Task: TASK-W2A

## 1. Summary

**Title**: Evaluation contract & submission validation  
**Description**: Implement local scoring and validation that mirrors challenge rules. Enables measurement before burning remote submissions.  
**Status**: Completed
**Wave**: Wave 2 -- Evaluation & Corpus Framing

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
- **Dependencies**: TASK-W1A (workspace, shared schemas/config surfaces)

## 3. Implementation Plan



## 4. Working Notes

Known issue: EVALUATION.md says `retrieved_chunk_pages: []` for unanswerable (grounding 1.0), but telemetry validation says "non-empty". Default to `[]`; flag for organizer clarification.

## 5. Outcome

**Result**: Implemented and verified. The repo now has a local evaluator/validator contract, CLI commands for validation and scoring, and documented handling of the unanswerable-grounding ambiguity.  
**Next action**: Use the W2A contract as the scoring/validation base for W2B regression work and later pipeline stages.
