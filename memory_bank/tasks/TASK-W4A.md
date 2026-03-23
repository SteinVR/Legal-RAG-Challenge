# Task: TASK-W4A

# About

This task formalizes the first score-recovery track after the warmup baseline: page attribution precision and validation behavior. The baseline showed that grounding is the main multiplicative blocker, with widespread extra-page citation and answer loss from overly strict grounding validation. This task exists to make the page-evidence path explicit, minimal, and temporally consistent.

This task owns only page attribution and validation policy. It does not change typed extraction logic, decomposition logic, or parser architecture. It consumes retrieval outputs from the current baseline stack initially and from `TASK-W4D` retrieval once that contract stabilizes, and it must define a stable contract that both can target.

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
  - Pass B final emitted pages.
- Trace or telemetry fields must be rich enough to reconstruct:
  - which chunks/pages were originally retrieved;
  - which pages survived Pass A;
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
- The task leaves a stable page-attribution contract that `TASK-W4B`, `TASK-W4D`, and `TASK-W4E` can rely on.

## Test and evaluation expectations

- Unit coverage for:
  - Pass A pruning behavior;
  - Pass B finalization behavior;
  - boilerplate/title-page suppression;
  - validation degradation vs suppression;
  - grounded no-answer page emission.
- Regression slices must include:
  - questions with correct answer text but extra pages;
  - questions where title pages previously contaminated emitted pages;
  - free-text questions previously suppressed by grounding validation;
  - no-answer questions.
- Required ablations:
  - baseline vs Pass A only;
  - baseline vs validation-policy-only;
  - baseline vs combined Pass A + validation degradation.

## Dependency assumptions

- Starts immediately against the current baseline retrieval/answering flow.
- Must publish a stable page-attribution contract before `TASK-W4D` and `TASK-W4E` are considered complete.

## 1. Summary

**Title**: Page attribution precision & validation policy  
**Description**: Two-pass minimal-evidence page attribution plus page-degradation-first validation to recover grounding score without destroying answer content.  
**Status**: Planned  
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
  - typed extraction upgrades
  - parser branch integration
  - cross-case question decomposition
- **Dependencies**:
  - none for start
  - downstream consumers: `TASK-W4B`, `TASK-W4D`, `TASK-W4E`

## 3. Implementation Plan

- Define the retrieval-to-answering page contract and the separation between raw candidates, Pass A pages, and final emitted pages.
- Implement suppression heuristics for title pages and repeated boilerplate.
- Define validation behavior that trims pages before suppressing answers.
- Lock config flags so mainline behavior and A/B isolation are both supported.
- Validate against baseline regression slices where grounding precision is the main loss driver.

## 4. Working Notes

Baseline signals motivating this task:

- grounding `G=0.570` is the main multiplicative blocker;
- many correct answers still lose score because of extra pages;
- free-text fallback is currently too eager when page validation fails.

This task is intentionally first in Wave 4 because it can improve score even before parser or decomposition work lands.

## 5. Outcome

**Result target**: Stable two-pass page-attribution contract with ablation-ready controls and validation behavior that preserves supportable answers.  
**Next action**: Feed the finalized page-attribution contract into `TASK-W4D` retrieval integration and `TASK-W4E` decomposed-answer flows.
