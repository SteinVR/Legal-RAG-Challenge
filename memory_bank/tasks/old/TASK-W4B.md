# Task: TASK-W4B

# About

This task formalizes the second baseline-recovery track: schema-first typed solving, deterministic validation, and query-side legal prefilters. The baseline shows that post-retrieval answering is underperforming mainly because typed answers are too conservative, `name`/`names` are effectively broken, and cross-document questions lack strong entity-aware retrieval cues.

This task owns answer-type-specific structured solving, deterministic guardrails, and lightweight question understanding that improves retrieval. It explicitly does not own full question decomposition or parser/ingestion upgrades.

# Specification

## Target behavior

- Upgrade typed answering by answer type rather than treating all abstention the same.
- Improve typed solving quality for:
  - boolean;
  - number;
  - name;
  - names;
  - date.
- Use schema-bound solving for `free_text` through the same provider abstraction.
- Introduce canonical legal-entity extraction from the question for:
  - `case_id`;
  - `statute_id`;
  - document-title cues.
- Expose those extracted cues as soft retrieval filters or boosts, not as one-document routing locks.
- Enable a baseline multi-document reasoning path without decomposition.

## Required interfaces and artifacts

- A schema registry must exist for:
  - boolean;
  - number;
  - name;
  - names;
  - date;
  - free_text.
- Every schema must expose:
  - `is_answerable`;
  - typed `final_answer`;
  - `relevant_pages`;
  - short `reasoning_summary`.
- Deterministic typed schemas must allow `final_answer=null` when `is_answerable=false`.
- Free-text schema must preserve the current canonical no-information sentence when `is_answerable=false`.
- The provider contract must support:
  - schema-bound structured outputs;
  - per-type schema dispatch;
  - configurable reasoning effort.
- Typed answering must surface per-type confidence or decision metadata sufficient for calibrated abstention.
- Retrieval-facing query metadata must distinguish:
  - extracted legal entities;
  - whether each entity is strong enough for boosting/filtering;
  - whether the question likely requires multi-document breadth.
- Config must support:
  - per-type reasoning-effort defaults;
  - per-type thresholding or calibration controls.
- The output contract must remain compatible with current answer schema and validation expectations.

## Development rules and non-goals

- Do not implement full comparative-question decomposition here.
- Do not let legal-entity extraction force hard single-document routing.
- Do not require long exposed chain-of-thought fields such as mandatory 150-word `step_by_step_analysis`.
- Do not turn model-reported pages into a new source of truth; they may only narrow W4A Pass B after retrieval-backed validation.
- Use deterministic logic as:
  - candidate generation;
  - validation;
  - normalization;
  - rejection;
  not as the sole typed solver.
- Treat baseline multi-document reasoning as:
  - better candidate retrieval;
  - better evidence matching;
  - better typed solving across multiple documents;
  not as orchestration across subquestions.
- Name extraction must explicitly handle:
  - case ids vs title-page artifacts;
  - party names vs surrounding boilerplate;
  - multi-name outputs as unordered lists.

## Acceptance criteria

- All answer types use schema-bound structured outputs through the provider abstraction.
- Every schema includes `is_answerable`, `relevant_pages`, short `reasoning_summary`, and typed `final_answer`.
- Deterministic unanswerable outputs remain `null`; free-text unanswerable outputs remain the canonical no-information sentence.
- `relevant_pages` from solver output is available as a W4A Pass B narrowing signal only after retrieval-backed validation.
- Typed solving no longer behaves as a mostly binary abstain system.
- `name` and `names` have explicit solver and validator logic rather than relying on generic span capture.
- Boolean solving has explicit polarity and negation handling.
- Number solving can suppress title-page years and similar spurious literals.
- Query-side legal entities are available to retrieval as soft (non-blocking) guidance.
- Reasoning effort is configurable per answer type via config, with required defaults:
  - `high` for boolean, name, names;
  - `medium` for number, date, free_text.
- The task produces a stable non-decomposition multi-document baseline that `TASK-W4E` can build on.

## Test and evaluation expectations

- Unit coverage per answer type:
  - schema parsing and normalization;
  - boolean polarity and negation;
  - number normalization and spurious-literal rejection;
  - name / names entity selection;
  - date normalization;
  - typed unanswerable handling.
- Regression slices must include:
  - `name` and `names` questions from the warmup baseline;
  - high-grounding deterministic nulls;
  - cross-case questions without decomposition;
  - statute-number and case-id questions where soft prefilters should help.
  - page-attribution narrowing from solver-reported pages.
- Evaluation should report both:
  - deterministic score movement;
  - null-rate reduction by answer type;
  - page-signal precision after Pass B narrowing.

## Dependency assumptions

- Starts in parallel with `TASK-W4A` and `TASK-W4C`.
- Must publish stable query-prefilter outputs before `TASK-W4D` is finalized.
- Must publish a baseline multi-document non-decomposition path before `TASK-W4E` begins orchestration work.

## Stabilized Contract

- `extract_query_metadata(question)` returns only:
  - `legal_entities`
  - `document_title_cues`
  - `likely_multi_document`
- Query metadata is retrieval guidance only. It may boost or steer candidates, but it must not hard-route to one document.
- `StructuredProvider.generate_structured(...)` returns a unified structured payload with:
  - `is_answerable`
  - typed `final_answer`
  - `relevant_pages`
  - `reasoning_summary`
- Deterministic typed no-answer remains `final_answer=null`; free-text no-answer remains the canonical no-information sentence.
- `relevant_pages` are solver-reported support pages only. They may narrow final page attribution after W4A validation, but they may not add unsupported pages.
- Provider, schema registry, and answering service must share one wire contract for all answer types.

## Definition of Done

- All answer types run through the schema-bound structured-provider path with a stable output contract.
- Per-type validation and normalization are applied after structured solving without breaking the unified provider contract.
- Query metadata is available end-to-end to retrieval and remains soft guidance only.
- Cross-document baseline questions can use the same contract without full W4E decomposition.
- Contract tests cover provider output shape, typed no-answer semantics, query metadata forwarding, and page-narrowing boundaries.

## 1. Summary

**Title**: Structured typed solving, validation & legal prefilters  
**Description**: Make schema-first typed solving the primary post-retrieval answer path, keep deterministic validation as the guardrail layer, and add soft legal-entity query prefilters for stronger baseline multi-document reasoning.  
**Status**: Done (stabilized 2026-03-25, commits d673a0b + 1c412da)
**Wave**: Wave 4 -- Baseline Recovery & Structural Upgrade

## 2. Scope

- **In scope**:
  - Structured Output with per-type Pydantic schemas (boolean, number, name, names, date, free_text)
  - `is_answerable` + `final_answer` + `relevant_pages` + short `reasoning_summary` in every schema
  - per-type structured solving
  - deterministic validation and normalization
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

- Define per-type structured schemas, solver dispatch, and confidence semantics.
- Add legal-entity extraction for query-side signals and connect them to a stable retrieval-facing interface.
- Tighten type-specific validation and spurious-span rejection, especially for names and numeric literals.
- Evaluate deterministic improvements by answer type and by high-grounding null slice.
- Integrate legal-prefilter signals as soft (non-blocking) guidance.
- Freeze the non-decomposition multi-document path before decomposition work begins.

## Structured Typed Solver + Per-Type Schemas (high-impact upgrade)

### Why this matters

The current typed path is constrained by deterministic unanimity logic and weak type-specific extraction. RAG-Challenge-2 demonstrated the leverage of per-type schemas, schema-bound answering, and model-reported supporting pages. For our challenge, the most promising adaptation is not free-form generation, but schema-first typed solving with deterministic validation layered after retrieval.

Reasoning-capable models plus configurable reasoning effort are valuable here because the main score deficit is typed answer quality, not TTFT. The baseline TTFT headroom is sufficient to spend extra thinking budget on high-value typed questions.

### Implementation

**Replace the current plain-text typed-answer path with schema-bound structured solving through the provider abstraction:**
- Current: the typed path is dominated by deterministic extraction and the provider path is generic free-form JSON.
- Target: the provider layer must support per-type schema dispatch, structured output validation, and reasoning effort controls without hard-coding one low-level API transport shape in the spec.

**Define per-type Pydantic answer schemas adapted from RAG-Challenge-2:**

Each schema must include these fields:

1. `is_answerable: bool` — explicit abstention signal.
2. `final_answer` — typed per answer type. For deterministic types this may be `null` only when `is_answerable=false`.
3. `relevant_pages: list[int]` — pages from retrieved evidence that directly support the answer.
4. `reasoning_summary: str` — short internal/debug summary only.

Do not make long exposed chain-of-thought a mandatory runtime field.

**Per-type schema targets (adapt from RAG-Challenge-2 `prompts.py`):**

| Type | Source reference | `final_answer` type | Key adaptation for legal domain |
|---|---|---|---|
| `boolean` | `AnswerWithRAGContextBooleanPrompt` (lines 241-282) | `bool \| null` | Add explicit negation/polarity rules for legal questions and keep `null` for retrieval-backed unanswerable typed cases. |
| `number` | `AnswerWithRAGContextNumberPrompt` (lines 144-237) | `float \| int \| null` | Keep strict metric matching discipline. Add legal-specific rules: article numbers vs years, penalty amounts vs case IDs, statutory numbers vs page references. |
| `name` | `AnswerWithRAGContextNamePrompt` (lines 95-140) | `str \| null` | Adapt for case IDs, party names, document titles. Add exact-surface-form and title-page boilerplate rejection rules. |
| `names` | `AnswerWithRAGContextNamesPrompt` (lines 286-343) | `list[str] \| null` | Adapt for multi-party legal cases and multiple case references. Output as unordered list. |
| `date` | New (no RAG-Challenge-2 equivalent) | `str \| null` | ISO 8601 format. Add rules for judgment dates, filing dates, and effective dates. |
| `free_text` | Enhance current path | `str` | Keep 280-char limit. When `is_answerable=false`, emit the canonical no-information sentence instead of `null`. |

**`relevant_pages` as page-attribution signal:**
- The model reports which evidence pages it actually used to derive the answer.
- This signal feeds into W4A Pass B only as a narrowing signal: model-reported pages must be intersected with retrieval-backed pages to produce minimal-evidence final references.
- `relevant_pages` must never add pages beyond retrieval-backed evidence or replace retrieval-grounded truth.
- RAG-Challenge-2's `_validate_page_references()` (lines 87-119) validates that reported pages are a subset of retrieved pages. Reuse the subset discipline, not its min-pages backfill behavior.

**Reasoning effort configuration:**
- Use a reasoning-capable structured-output model through the provider abstraction.
- Required defaults:
  - `high` for boolean, name, names;
  - `medium` for number, date, free_text.
- Expose reasoning effort as config parameter per answer type.

## Source References & Adaptation Map

### Enhance in current `src/`

**Structured solver and deterministic guardrails:**
- `src/providers/codex_provider.py` — current generic free-form provider path should be generalized into a schema-aware provider interface with per-type schema dispatch and reasoning-effort controls.
- `src/answering/service.py` `_extract_boolean()` (lines 478-505) — reuse as polarity-validation and contradiction-check logic after structured solving.
- `src/answering/service.py` `_extract_number()` (lines 430-475) — reuse as candidate generation and spurious-literal rejection logic after structured solving.
- `src/answering/service.py` `_extract_name()` (lines 508-513) and `_extract_names()` (lines 516-533) — replace stub-like behavior with candidate/validator support for schema-first solving.
- `src/answering/service.py` `_extract_date()` (lines 536-546) — reuse as normalization and ambiguity filter after structured solving.
- `src/answering/service.py` `AnsweringService` routing (lines 283-297) — replace binary unanimous-or-null typed routing with schema-first solving plus post-solver validation and calibrated abstention.

### Adapt from `external/RAG-Challenge-2`

**Schema registry and runtime glue:**
- `external/RAG-Challenge-2/src/prompts.py` `AnswerWithRAGContextBooleanPrompt` (lines 241-282) — source for boolean schema shape and polarity-oriented answer instructions.
- `external/RAG-Challenge-2/src/prompts.py` `AnswerWithRAGContextNumberPrompt` (lines 144-237) — source for strict numeric matching and no-proxy discipline.
- `external/RAG-Challenge-2/src/prompts.py` `AnswerWithRAGContextNamePrompt` (lines 95-140) — source for exact-surface-form name extraction.
- `external/RAG-Challenge-2/src/prompts.py` `AnswerWithRAGContextNamesPrompt` (lines 286-343) — source for multi-entity list output discipline.
- `external/RAG-Challenge-2/src/prompts.py` `build_system_prompt()` (lines 7-16) and nested Pydantic `AnswerSchema` classes — source for schema registry shape and prompt/schema pairing.
- `external/RAG-Challenge-2/src/api_requests.py` `_build_rag_context_prompts()` (lines 422-453) — the actual runtime glue that maps answer type → prompt → Pydantic schema. This is the primary adaptation reference for W4B schema dispatch.
- `external/RAG-Challenge-2/src/api_requests.py` `get_answer_from_rag_context()` (lines 408-419) — reference for provider-side structured-answer invocation.

**Question routing (reference, not direct port):**
- `external/RAG-Challenge-2/src/questions_processing.py` `process_question()` (lines 184-198) — reference for using entity-count signals during question analysis. In W4B, use this only to expose retrieval-breadth hints and multi-document likelihood signals; do **not** port company-style hard routing or decomposition decisions into this task.

### New code

- Legal-entity extraction from question text (`case_id`, `statute_id`, document-title cues) — no analog in either codebase. Legal-domain-specific regex + NER patterns.
- Retrieval-facing query metadata interface — bridge between entity extraction and W4D soft prefilters.
- Schema registry and typed solver dispatch for boolean/number/name/names/date/free_text.
- Deterministic post-solver validator layer for polarity, numeric normalization, entity filtering, and null policy.
- Per-type confidence scoring and calibrated abstention thresholds — replaces current binary unanimous-or-null logic.

## 4. Working Notes

Baseline signals motivating this task:

- deterministic score is the main answer-value blocker;
- `name` and `names` are effectively zeroed out;
- many deterministic nulls already have adequate grounding;
- cross-case questions need entity-aware retrieval help even before decomposition exists.

This task should maximize score recovery from the existing retrieval stack before the project pays the complexity cost of orchestration.

## 5. Outcome

**Result target**: Stable schema-first typed solving plus deterministic validation, retrieval-facing legal prefilters, and a non-decomposition multi-document baseline.  
**Next action**: Hand retrieval-facing query metadata to `TASK-W4D` and use the stabilized multi-document baseline as the foundation for `TASK-W4E`.
