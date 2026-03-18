# Task: TASK-W3C

## 1. Summary

**Title**: Answer routing & typed solving  
**Description**: Route questions by answer_type; implement extraction-based solvers and grounded free-text generator.  
**Status**: Planned
**Wave**: Wave 3 -- Parallel Baseline Build

## 2. Scope

- **In scope**:
  - Router by answer_type (number/boolean/name/names/date/free_text)
  - Typed solvers: extraction-first, minimal generation
    - number: extract + normalize (+-1% tolerance)
    - boolean: extract + resolve to true/false
    - name: extract + normalize
    - names: extract list + normalize
    - date: extract + ISO 8601 format
  - Null detector: return JSON null when evidence insufficient
  - Free-text generator: grounded, max 280 chars, calibrated confidence
  - Answer self-check: type validation, length gate, contradiction check
  - Provider abstraction: Codex via OAuth primary backend
- **Out of scope**: agentic multi-hop, query decomposition (post-baseline tracks)
- **Dependencies**: TASK-W2A (validation contract), TASK-W3B interface contract (retrieval), TASK-W1A (provider setup); implementation may proceed in parallel with mocks/stubs once contracts are frozen

## 3. Implementation Plan


## 4. Working Notes

For deterministic types, prefer extraction over generation where possible.
Null is a first-class answer: if both reference and prediction are null -> 1 point.
Free-text: 5 criteria (correctness, completeness, grounding, confidence calibration, clarity). Keep short and grounded.

## 5. Outcome

**Result**: [Pending]  
**Next action**: freeze answer I/O contract, then implement in Wave 3 with stubs or against TASK-W3B outputs
