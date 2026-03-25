# Task: TASK-W4A

# About

This task formalizes the first score-recovery track after the warmup baseline: page attribution precision and validation behavior. The baseline showed that grounding is the main multiplicative blocker, with widespread extra-page citation and answer loss from overly strict grounding validation. This task exists to make the page-evidence path explicit, minimal, and temporally consistent.

This task owns only page attribution and validation policy. It does not change typed solving logic, decomposition logic, or parser architecture. It consumes retrieval outputs from the current baseline stack initially and from `TASK-W4D` retrieval once that contract stabilizes, and it must define a stable contract that both can target.

# Specification

## Target behavior

- Introduce a two-pass grounding path:
  - Pass A prunes retrieved candidate pages before final answer emission.
  - Pass B finalizes the emitted page list after an answer attempt.
- Pass A must reduce over-retrieval without making no-answer decisions.
- Pass B is the only stage allowed to emit an empty page list, and only for a true grounded no-answer outcome.
- Grounding validation must trim or downgrade unsupported page attribution before it suppresses answer content.

## Required interfaces and artifacts

- A retrieval-to-answering contract that distinguishes:
  - raw retrieved candidate pages;
  - Pass A pruned candidate pages;
  - solver-reported support pages;
  - Pass B final emitted pages.
- Trace or telemetry fields must be rich enough to reconstruct:
  - which chunks/pages were originally retrieved;
  - which pages survived Pass A;
  - which pages the structured solver reported as direct support;
  - which pages were finally emitted after Pass B;
  - whether validation trimmed pages or collapsed the answer.
- Config surfaces must separate:
  - Pass A pruning controls;
  - title-page / boilerplate suppression controls;
  - Pass B no-answer emission policy;
  - validation degradation policy.

## Development rules and non-goals

- Do not let Pass A decide that a question is truly unanswerable.
- Do not bundle Pass A pruning and validation policy into one inseparable implementation surface.
- Solver-reported pages may narrow Pass B only after subset/intersection validation against retrieval-backed pages.
- Solver-reported pages must never add pages beyond retrieval-backed evidence.
- Keep the intended mainline target as:
  - Pass A minimal-evidence pruning enabled;
  - page-degradation-first validation enabled.
- Preserve separate toggles so A/B work can isolate:
  - Pass A only;
  - validation-policy only;
  - combined stack.
- Do not modify typed answer extraction, query decomposition, or parser routing inside this task.

## Acceptance criteria

- The implementation exposes a clear two-pass temporal flow with no chicken-and-egg ambiguity.
- Boilerplate-heavy pages are suppressible without breaking answer-bearing pages on the same document.
- Validation can downgrade or trim pages without automatically replacing a semantically supportable answer with fallback output.
- No-answer handling can emit empty final pages without forcing empty retrieved candidates upstream.
- Solver-reported support pages can improve final precision without replacing retrieval-grounded truth.
- The task leaves a stable page-attribution contract that `TASK-W4B`, `TASK-W4D`, and `TASK-W4E` can rely on.

## Test and evaluation expectations

- Unit coverage for:
  - Pass A pruning behavior;
  - Pass B finalization behavior;
  - boilerplate/title-page suppression;
  - validation degradation vs suppression;
  - subset validation of solver-reported pages;
  - grounded no-answer page emission.
- Regression slices must include:
  - questions with correct answer text but extra pages;
  - questions where title pages previously contaminated emitted pages;
  - free-text questions previously suppressed by grounding validation;
  - typed answers where solver-reported pages should narrow the final set;
  - no-answer questions.
- Required ablations:
  - baseline vs Pass A only;
  - baseline vs validation-policy-only;
  - baseline vs combined Pass A + validation degradation.

## Dependency assumptions

- Starts immediately against the current baseline retrieval/answering flow.
- Must publish a stable page-attribution contract before `TASK-W4D` and `TASK-W4E` are considered complete.

## Stabilized Contract

- Authoritative page-grounding flow is:
  - `raw_retrieved_chunk_pages`
  - `pass_a_pages`
  - `solver_reported_pages`
  - `final_emitted_pages`
- Pass A may prune noisy pages and boilerplate, but it must never decide true no-answer.
- If retrieval produced valid evidence, Pass A must not collapse support to an empty set as a hidden abstention.
- Pass B is the only stage allowed to emit empty final pages, and only for a grounded no-answer outcome.
- Solver-reported pages are a narrowing signal only. They must be validated against retrieval-backed pages before use.
- Solver-reported pages must never add pages beyond retrieval-backed evidence.
- `AnswerResult.evidence_pages` and telemetry/page-trace output must encode the same final emitted page set.

## Definition of Done

- The runtime exposes the full page-grounding chain from raw retrieval pages through final emitted pages.
- Pass A behavior, Pass B behavior, and validation policy are separately configurable and testable.
- Off-page or title-page leakage is trimmed without suppressing otherwise supportable answers.
- Grounded no-answer behavior emits empty final pages only through the explicit Pass B/no-answer path.
- `AnswerResult.evidence_pages`, page trace fields, and submission telemetry remain consistent for the same answer.
- Regression and contract tests cover hidden-no-answer prevention, page narrowing, and final page emission consistency.

## 1. Summary

**Title**: Page attribution precision & validation policy  
**Description**: Two-pass minimal-evidence page attribution plus page-degradation-first validation to recover grounding score without destroying answer content.  
**Status**: Done (stabilized 2026-03-25, commits d673a0b + 1c412da)
**Wave**: Wave 4 -- Baseline Recovery & Structural Upgrade

## 2. Scope

- **In scope**:
  - Pass A minimal-evidence page pruning
  - Pass B final page attribution
  - Title-page, cover-page, index, and repeated-boilerplate suppression
  - Grounding validation degradation policy
  - No-answer page-emission rules
  - Page-attribution telemetry and traceability
- **Out of scope**:
  - typed solving upgrades
  - parser branch integration
  - cross-case question decomposition
- **Dependencies**:
  - none for start
  - downstream consumers: `TASK-W4B`, `TASK-W4D`, `TASK-W4E`

## 3. Implementation Plan

- Define the retrieval-to-answering page contract and the separation between raw candidates, Pass A pages, solver-reported pages, and final emitted pages.
- Implement suppression heuristics for title pages and repeated boilerplate.
- Define validation behavior that trims pages before suppressing answers.
- Lock config flags so mainline behavior and A/B isolation are both supported.
- Validate against baseline regression slices where grounding precision is the main loss driver.

## Source References & Adaptation Map

### Enhance in current `src/`

**Pass A — minimal-evidence pruning (new code, inserted between retrieval and answering):**
- Insert point: `src/submission/pipeline.py` `_answer_question()` (line ~420). Currently this function calls retrieval then immediately calls answering. Pass A sits between those calls.
- `src/retrieval/page_lifter.py` `PageLifter.to_page_references()` (lines 94-109) — current chunk-to-page lifting that produces the raw candidate page list. Pass A consumes this output and prunes it.
- `src/retrieval/page_lifter.py` `PageLifter.lift()` (lines 53-92) — aggregates chunks with scores. Pass A can use rerank scores and chunk-type metadata to decide which pages to keep.

**Pass B — post-answer page finalization (rework of grounding validation):**
- Rework: `src/answering/service.py` `_validate_free_text_grounding()` (lines 560-609) — current grounding validation that raises `FreeTextGroundingValidationError`. This must become Pass B: instead of raising an exception that suppresses the answer, it trims unsupported pages and only collapses to fallback when the answer itself is unsupportable.
- Rework: `src/submission/pipeline.py` `_answer_question()` (lines 428-445) — the `except FreeTextGroundingValidationError` block that currently replaces the answer with `CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER`. This catch-and-suppress pattern is the core of the over-eager fallback problem.
- Incoming signal: `TASK-W4B` structured solver outputs — Pass B consumes solver-reported `relevant_pages` only after validating they are a subset of retrieval-backed page candidates.

**Title-page / boilerplate suppression:**
- `src/ingestion/corpus_builder.py` — canonical pages already carry `document_title`, `document_family`, `page_number`. Page 1 of most documents is a title/cover page. Suppression heuristics can use page_number=1 + low legal-marker density as signals.
- `src/ingestion/page_triage.py` `score_page_quality()` — quality breakdown includes `legal_marker_score`. Pages with high quality but zero legal markers are likely cover/index pages.

### Reference from `external/RAG-Challenge-2`

- `external/RAG-Challenge-2/src/questions_processing.py` `_validate_page_references()` (lines 87-119) — partial guardrail reference only. Reusable idea: emitted pages must be a subset of retrieval-backed pages. Do **not** port its `min_pages` backfill behavior, because padding page lists from retrieval results conflicts with W4A's minimal-evidence objective.

### New code

- Two-pass temporal flow controller (Pass A → answering → Pass B) — no direct source in either codebase.
- Pass A pruning heuristics (score threshold, chunk-type filtering, title-page detection).
- Pass B page-degradation logic (trim pages before suppressing answers).
- Solver-reported page intersection logic (`retrieved pages ∩ solver-reported pages`) for Pass B narrowing.
- Config flags for A/B isolation (pass_a_enabled, validation_policy, combined).

## 4. Working Notes

Baseline signals motivating this task:

- grounding `G=0.570` is the main multiplicative blocker;
- many correct answers still lose score because of extra pages;
- free-text fallback is currently too eager when page validation fails.

This task is intentionally first in Wave 4 because it can improve score even before parser or decomposition work lands.

## 5. Outcome

**Result target**: Stable two-pass page-attribution contract with ablation-ready controls and validation behavior that preserves supportable answers.  
**Next action**: Feed the finalized page-attribution contract into `TASK-W4D` retrieval integration and `TASK-W4E` decomposed-answer flows.
