# Task: TASK-W4B

# About

This task formalizes the second baseline-recovery track: typed extraction quality and query-side legal prefilters. The baseline shows that deterministic answering is underperforming mainly because extraction is too conservative, `name`/`names` are effectively broken, and cross-document questions lack strong entity-aware retrieval cues.

This task owns answer-type-specific extraction behavior plus lightweight question understanding that improves retrieval. It explicitly does not own full question decomposition or parser/ingestion upgrades.

# Specification

## Target behavior

- Upgrade deterministic answering by answer type rather than treating all abstention the same.
- Improve extraction quality for:
  - boolean;
  - number;
  - name;
  - names;
  - date.
- Introduce canonical legal-entity extraction from the question for:
  - `case_id`;
  - `statute_id`;
  - document-title cues.
- Expose those extracted cues as soft retrieval filters or boosts, not as one-document routing locks.
- Enable a baseline multi-document reasoning path without decomposition.

## Required interfaces and artifacts

- Typed extraction must surface per-type confidence or decision metadata sufficient for calibrated abstention.
- Retrieval-facing query metadata must distinguish:
  - extracted legal entities;
  - whether each entity is strong enough for boosting/filtering;
  - whether the question likely requires multi-document breadth.
- Config must support per-type thresholding or calibration controls.
- The output contract must remain compatible with current answer schema and validation expectations.

## Development rules and non-goals

- Do not implement full comparative-question decomposition here.
- Do not let legal-entity extraction force hard single-document routing.
- Treat baseline multi-document reasoning as:
  - better candidate retrieval;
  - better evidence matching;
  - better extraction across multiple documents;
  not as orchestration across subquestions.
- Name extraction must explicitly handle:
  - case ids vs title-page artifacts;
  - party names vs surrounding boilerplate;
  - multi-name outputs as unordered lists.

## Acceptance criteria

- Typed extraction no longer behaves as a mostly binary abstain system.
- `name` and `names` have explicit extraction logic rather than relying on generic span capture.
- Boolean extraction has explicit polarity and negation handling.
- Number extraction can suppress title-page years and similar spurious literals.
- Query-side legal entities are available to retrieval as soft (non-blocking) guidance.
- The task produces a stable non-decomposition multi-document baseline that `TASK-W4E` can build on.

## Test and evaluation expectations

- Unit coverage per answer type:
  - boolean polarity and negation;
  - number normalization and spurious-literal rejection;
  - name / names entity selection;
  - date normalization.
- Regression slices must include:
  - `name` and `names` questions from the warmup baseline;
  - high-grounding deterministic nulls;
  - cross-case questions without decomposition;
  - statute-number and case-id questions where soft prefilters should help.
- Evaluation should report both:
  - deterministic score movement;
  - null-rate reduction by answer type.

## Dependency assumptions

- Starts in parallel with `TASK-W4A` and `TASK-W4C`.
- Must publish stable query-prefilter outputs before `TASK-W4D` is finalized.
- Must publish a baseline multi-document non-decomposition path before `TASK-W4E` begins orchestration work.

## 1. Summary

**Title**: Typed extraction, confidence calibration & legal prefilters  
**Description**: Improve deterministic answering by answer type and add soft legal-entity query prefilters for stronger baseline multi-document reasoning.  
**Status**: Planned  
**Wave**: Wave 4 -- Baseline Recovery & Structural Upgrade

## 2. Scope

- **In scope**:
  - per-type deterministic extraction upgrades
  - confidence calibration / abstention tuning
  - legal-entity extraction from question text
  - soft retrieval boosts/filters from extracted entities
  - baseline multi-document reasoning without decomposition
- **Out of scope**:
  - full question decomposition
  - parser branch integration
  - page-attribution validation policy
- **Dependencies**:
  - none for start
  - provides retrieval-facing signals to `TASK-W4D`
  - provides multi-document baseline required by `TASK-W4E`

## 3. Implementation Plan

- Define per-type extraction strategies and confidence semantics.
- Add legal-entity extraction for query-side signals and connect them to a stable retrieval-facing interface.
- Tighten type-specific spurious-span rejection, especially for names and numeric literals.
- Evaluate deterministic improvements by answer type and by high-grounding null slice.
- Integrate legal-prefilter signals as soft (non-blocking) guidance.
- Freeze the non-decomposition multi-document path before decomposition work begins.

## Source References & Adaptation Map

### Enhance in current `src/`

**Typed extractors (rework existing logic):**
- `src/answering/service.py` `_extract_boolean()` (lines 478-505) — current implementation matches affirmative/negative modals. Needs explicit polarity handling: negation detection, double-negation, and cross-case overlap where gold=false but system returns true. Baseline: 4/32 exact on boolean.
- `src/answering/service.py` `_extract_number()` (lines 430-475) — current implementation uses context scoring (duration, amount cues). Needs title-page year suppression (baseline error: extracted `2004` instead of law number `3`) and stricter literal-vs-reference disambiguation. Baseline: 5/17 exact on number.
- `src/answering/service.py` `_extract_name()` (lines 508-513) and `_extract_names()` (lines 516-533) — current implementations are near-stubs. Baseline: 0/15 name, 0/5 names. Need complete rewrite with entity-span selection logic.
- `src/answering/service.py` `_extract_date()` (lines 536-546) — current implementation supports 3 ISO formats. Needs stricter normalization and ambiguity handling.

**Confidence and abstention (rework routing logic):**
- `src/answering/service.py` `AnsweringService` routing (lines 283-297) — currently deterministic extraction requires "unanimous answer across all evidence pages" which causes 47/70 null answers. Needs per-type confidence scoring and calibrated abstention thresholds instead of binary unanimous-or-null.

### Adapt from `external/RAG-Challenge-2`

**Prompt templates and structured output schemas (adapt for legal domain):**
- `external/RAG-Challenge-2/src/prompts.py` `AnswerWithRAGContextBooleanPrompt` (lines 241-282) — chain-of-thought boolean answering with step-by-step analysis. Adapt: replace company/financial context with legal terminology (statutes, judgments, orders).
- `external/RAG-Challenge-2/src/prompts.py` `AnswerWithRAGContextNumberPrompt` (lines 144-237) — strict metric matching: "metric must EXACTLY match, no proxy or similar, no calculations, return N/A if uncertain." This discipline is exactly what baseline number extraction lacks.
- `external/RAG-Challenge-2/src/prompts.py` `AnswerWithRAGContextNamePrompt` (lines 95-140) — "extract exactly as appears in context, no extra words." Adapt for case IDs, party names, document labels.
- `external/RAG-Challenge-2/src/prompts.py` `AnswerWithRAGContextNamesPrompt` (lines 286-343) — multi-name extraction with deduplication. Adapt for multi-party legal cases.
- `external/RAG-Challenge-2/src/prompts.py` `build_system_prompt()` (lines 7-16) — pattern for building formatted prompts with JSON schema and examples. Reusable as-is via current provider abstraction.
- `external/RAG-Challenge-2/src/prompts.py` Pydantic answer schemas (e.g. `AnswerSchema` at lines 245-261) — structured output enforcement. Adapt for current answering schema contract.

**Question routing (reference, not direct port):**
- `external/RAG-Challenge-2/src/questions_processing.py` `process_question()` (lines 184-198) — routing by detected answer type plus company count. Reference for how to route legal questions by entity count (single-doc vs multi-doc).

### New code

- Legal-entity extraction from question text (`case_id`, `statute_id`, document-title cues) — no analog in either codebase. Legal-domain-specific regex + NER patterns.
- Retrieval-facing query metadata interface — bridge between entity extraction and W4D soft prefilters.
- Per-type confidence scoring and calibrated abstention thresholds — replaces current binary unanimous-or-null logic.

## 4. Working Notes

Baseline signals motivating this task:

- deterministic score is the main answer-value blocker;
- `name` and `names` are effectively zeroed out;
- many deterministic nulls already have adequate grounding;
- cross-case questions need entity-aware retrieval help even before decomposition exists.

This task should maximize score recovery from the existing retrieval stack before the project pays the complexity cost of orchestration.

## 5. Outcome

**Result target**: Stable per-type extraction logic plus retrieval-facing legal prefilters and a non-decomposition multi-document baseline.  
**Next action**: Hand retrieval-facing query metadata to `TASK-W4D` and use the stabilized multi-document baseline as the foundation for `TASK-W4E`.
