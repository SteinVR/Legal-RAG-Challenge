# Task: TASK-W3C

## 1. Summary

**Title**: Answer routing & typed solving  
**Description**: Route questions by answer_type; implement extraction-based solvers and grounded free-text generator.  
**Status**: Done (baseline merged; runnable-completeness closed by W3D integration)
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
- **Dependencies**: TASK-W2A (validation contract), TASK-W3B runnable retrieval contract, TASK-W1A (provider/config setup); implementation may proceed in parallel with mocks/stubs only for baseline development, not for final acceptance

## 3. Implementation Plan

- Implemented the answering service layer in `src/answering/service.py` plus provider abstractions in `src/providers/`.
- Added dedicated answering tests covering routing/solver behavior and integrated the service into the merged Wave 3 baseline.
- Merged task branch into `main` after quality-gate review and final integrated verification.
- The integrated W3D submission path now exercises the concrete provider path on top of the runnable retrieval contract.
- No corrective follow-up remains inside W3C; submission orchestration lives in W3D.

## 4. Working Notes

For deterministic types, prefer extraction over generation where possible.
Null is a first-class answer: if both reference and prediction are null -> 1 point.
Free-text: 5 criteria (correctness, completeness, grounding, confidence calibration, clarity). Keep short and grounded.
Provider abstraction alone was no longer considered sufficient completion for W3C. The W3D runnable pipeline now exercises a concrete provider path plus system-level coverage against the real W3B retrieval contract.

## 5. Outcome

**Result**: Completed on 2026-03-21 as a baseline answering layer and merged to `main`; the W3D runnable pipeline now confirms the concrete provider path and answer routing on top of retrieval.  
**Next action**: None for W3C; use as a stable baseline for post-baseline tracks.
