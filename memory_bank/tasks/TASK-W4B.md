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

- All answer types use Structured Output with per-type Pydantic schemas via OpenAI API.
- Every schema includes `step_by_step_analysis`, `reasoning_summary`, `relevant_pages`, and typed `final_answer`.
- `relevant_pages` from model output is available as a page-attribution signal for W4A Pass B.
- Typed extraction no longer behaves as a mostly binary abstain system.
- `name` and `names` have explicit extraction logic rather than relying on generic span capture.
- Boolean extraction has explicit polarity and negation handling.
- Number extraction can suppress title-page years and similar spurious literals.
- Query-side legal entities are available to retrieval as soft (non-blocking) guidance.
- Reasoning effort is configurable per answer type via config.
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
  - Structured Output with per-type Pydantic schemas (boolean, number, name, names, date, free_text)
  - step_by_step_analysis + reasoning_summary + relevant_pages in every schema
  - per-type deterministic extraction upgrades
  - confidence calibration / abstention tuning
  - reasoning effort configuration per answer type
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

## Structured Output + Per-Type Schemas (high-impact upgrade)

### Why this matters

The current generation path (`src/providers/codex_provider.py`) uses a 2-line generic system prompt, no type-awareness, no reasoning, no page-reference discipline, and parses free-form JSON via `json.loads()`. RAG-Challenge-2 won the competition with detailed per-type Pydantic schemas enforced through Structured Output, chain-of-thought reasoning, and model-reported `relevant_pages`. This is the single highest-leverage change available.

gpt-5.4-mini is a reasoning model with configurable reasoning effort. Its thinking tokens improve answer quality on multi-step extraction and polarity questions. TTFT includes thinking time, but the baseline TTFT (P50=780ms) leaves headroom, and accuracy gains from reasoning outweigh the TTFT penalty at current score levels (det=0.129 has massive upside).

### Implementation

**Replace the current plain-text JSON generation with OpenAI Structured Output API:**
- Current: `src/providers/codex_provider.py` sends `_SYSTEM_PROMPT` (lines 23-27) → model returns free-form text → `json.loads()` parse (line 245).
- Target: send `response_format={"type": "json_schema", "json_schema": {...}}` with per-type Pydantic schemas → model returns guaranteed-valid structured output. No parse failures, no missing keys.

**Define per-type Pydantic answer schemas adapted from RAG-Challenge-2:**

Each schema must include these fields in this order (reasoning before answer forces the model to think first):

1. `step_by_step_analysis: str` — detailed chain-of-thought (5+ steps, 150+ words). Not included in submission, but improves model accuracy. For legal domain: replace financial/company framing with legal terminology (statutes, judgments, orders, parties).
2. `reasoning_summary: str` — concise 50-word summary of reasoning.
3. `relevant_pages: list[int]` — pages from evidence that directly support the answer. This is the **key page-attribution signal**: model-reported pages become a candidate input for W4A Pass B, potentially replacing or augmenting the current top-k retrieval pages in `retrieved_chunk_pages`.
4. `final_answer` — typed per answer type (see below).

**Per-type schema targets (adapt from RAG-Challenge-2 `prompts.py`):**

| Type | Source reference | `final_answer` type | Key adaptation for legal domain |
|---|---|---|---|
| `boolean` | `AnswerWithRAGContextBooleanPrompt` (lines 241-282) | `bool` | Add explicit negation/polarity rules for legal questions: "does the statute prohibit X" → check for double negation. Add cross-case overlap rules. |
| `number` | `AnswerWithRAGContextNumberPrompt` (lines 144-237) | `float \| int \| Literal["N/A"]` | Keep strict metric matching discipline. Add legal-specific rules: article numbers vs years, penalty amounts vs case IDs, statutory numbers vs page references. |
| `name` | `AnswerWithRAGContextNamePrompt` (lines 95-140) | `str \| Literal["N/A"]` | Adapt for case IDs (e.g. `CFI 010/2024`, `SCT 169/2025`), party names, document titles. Add rule: extract exactly as appears, no title-page boilerplate. |
| `names` | `AnswerWithRAGContextNamesPrompt` (lines 286-343) | `list[str] \| Literal["N/A"]` | Adapt for multi-party legal cases, multiple case references. Output as unordered list. |
| `date` | New (no RAG-Challenge-2 equivalent) | `str \| Literal["N/A"]` | ISO 8601 format. Add rules for legal date extraction: judgment dates, filing dates, effective dates. |
| `free_text` | Enhance current path | `str` | Keep 280-char limit. Add `relevant_pages` for page-attribution signal. |

**`relevant_pages` as page-attribution signal:**
- The model reports which evidence pages it actually used to derive the answer.
- This signal feeds into W4A Pass B: model-reported pages can be intersected with retrieval-backed pages to produce minimal-evidence `retrieved_chunk_pages`.
- RAG-Challenge-2's `_validate_page_references()` (lines 87-119) validates that reported pages are a subset of retrieved pages. Same validation applies here.

**Reasoning effort configuration:**
- gpt-5.4-mini supports configurable reasoning effort (low/medium/high).
- For deterministic types (boolean, number, name, names, date): use higher reasoning effort — accuracy is the primary goal, TTFT penalty is acceptable given det=0.129 baseline.
- For free_text: use medium reasoning effort — asst=0.987 is already near-perfect, marginal gains don't justify TTFT cost.
- Expose reasoning effort as config parameter per answer type.

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

**Schema discipline and extraction constraints (reference only, not execution model):**
- `external/RAG-Challenge-2/src/prompts.py` `AnswerWithRAGContextBooleanPrompt` (lines 241-282) — reference for explicit polarity discipline and page-backed answer schema. Adapt the boolean decision rules into deterministic extraction and validation logic; do **not** port the chain-of-thought runtime path.
- `external/RAG-Challenge-2/src/prompts.py` `AnswerWithRAGContextNumberPrompt` (lines 144-237) — reference for exact-match numeric discipline: no proxy metrics, no derived values, no "close enough" spans. Translate these rules into deterministic extractor scoring and rejection logic.
- `external/RAG-Challenge-2/src/prompts.py` `AnswerWithRAGContextNamePrompt` (lines 95-140) — reference for exact-span extraction and no-extra-tokens discipline. Adapt the constraints to case IDs, party names, and document labels in the current extraction-first pipeline.
- `external/RAG-Challenge-2/src/prompts.py` `AnswerWithRAGContextNamesPrompt` (lines 286-343) — reference for multi-entity deduplication and exact-surface-form extraction. Adapt for legal multi-party answers, but keep outputs as unordered lists in the current deterministic contract.
- `external/RAG-Challenge-2/src/prompts.py` `build_system_prompt()` (lines 7-16) and nested Pydantic `AnswerSchema` classes (e.g. lines 245-261) — reference for documenting answer schemas, examples, and validation expectations. Do **not** import them as the primary runtime mechanism for W4B.

**Question routing (reference, not direct port):**
- `external/RAG-Challenge-2/src/questions_processing.py` `process_question()` (lines 184-198) — reference for using entity-count signals during question analysis. In W4B, use this only to expose retrieval-breadth hints and multi-document likelihood signals; do **not** port company-style hard routing or decomposition decisions into this task.

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
