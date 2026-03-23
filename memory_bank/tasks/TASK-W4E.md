# Task: TASK-W4E

# About

This task formalizes the most complex Wave 4 track: full cross-case decomposition and orchestration for comparative or multi-document questions. It is intentionally last because it should build on a stronger non-decomposition baseline rather than trying to compensate for weak extraction or weak retrieval.

This task owns orchestration for decomposed multi-document reasoning only. It does not own the baseline typed extractors, parser branch, or retrieval fundamentals.

# Specification

## Target behavior

- Add a selective escalation path for comparative or cross-case questions that are not well served by the baseline multi-document path.
- Detect when decomposition is warranted.
- Split the question into smaller subquestions or evidence probes.
- Execute retrieval and answering per subquestion.
- Recompose the final answer and final page attribution from the sub-results.

## Required interfaces and artifacts

- The task must consume:
  - stable baseline multi-document answering signals from `TASK-W4B`;
  - stable retrieval behavior from `TASK-W4D`;
  - final page-attribution contract from `TASK-W4A`.
- Decomposition flow must preserve:
  - mapping from original question to subquestions;
  - evidence provenance per subquestion;
  - final page-list recomposition rules.
- Config must expose:
  - decomposition trigger policy;
  - maximum subquestion budget;
  - recomposition policy.

## Development rules and non-goals

- This is an escalation path, not the default path for all questions.
- Do not use decomposition to mask weak baseline extraction or retrieval behavior that should be solved in `TASK-W4B` or `TASK-W4D`.
- Preserve final grounding discipline:
  - final answer pages must still obey the page-attribution contract;
  - decomposed flows must not emit page unions mechanically without minimization.
- Do not move parser or chunking ownership into this task.

## Acceptance criteria

- The system can distinguish between:
  - questions that should stay on the baseline path;
  - questions that should escalate to decomposition.
- Decomposed flows preserve evidence provenance through recomposition.
- Final answer text and final pages can be reconstructed from sub-results without breaking validation.
- The task measurably improves cross-case or comparative slices relative to the non-decomposition baseline.

## Test and evaluation expectations

- Regression and benchmark slices must include:
  - cross-case questions;
  - comparative legal questions;
  - amendment-vs-current style questions, with presence verified in the warmup gold set and synthetic test cases added if the warmup set does not contain them;
  - multi-document questions that should not trigger decomposition.
- Evaluation must compare:
  - baseline multi-document path from `TASK-W4B`/`TASK-W4D`;
  - selective decomposition path;
  - trigger-policy precision so decomposition is not overused.

## Dependency assumptions

- Depends on stable baseline multi-document support from `TASK-W4B`.
- Depends on stable retrieval behavior and query-prefilter integration from `TASK-W4D`.
- Depends on stable page-attribution finalization from `TASK-W4A`.

## 1. Summary

**Title**: Cross-case decomposition & multi-document orchestration  
**Description**: Add a selective decomposition path for hard comparative and cross-case questions once the non-decomposition multi-document baseline is stable.  
**Status**: Planned  
**Wave**: Wave 4 -- Baseline Recovery & Structural Upgrade

## 2. Scope

- **In scope**:
  - decomposition trigger policy
  - subquestion generation / orchestration
  - subquestion retrieval and answering flow
  - evidence and page-attribution recomposition
  - comparative / cross-case benchmark slices
- **Out of scope**:
  - baseline typed extraction
  - parser branch ownership
  - retrieval backbone tuning outside decomposition needs
- **Dependencies**:
  - `TASK-W4A` page-attribution finalization contract
  - `TASK-W4B` baseline multi-document path
  - `TASK-W4D` stable retrieval path

## 3. Implementation Plan

- Define trigger rules for when decomposition is allowed.
- Define subquestion and sub-result interfaces that preserve provenance.
- Integrate subquestion execution with the stabilized retrieval and answering stack.
- Define final answer and final page recomposition rules.
- Validate that decomposition improves hard multi-document slices without becoming the default execution path.

## Source References & Adaptation Map

### Adapt from `external/RAG-Challenge-2`

**Comparative decomposition (primary source, adapt for legal domain):**
- `external/RAG-Challenge-2/src/questions_processing.py` `process_comparative_question()` (lines 453-518) — the core decomposition flow:
  1. Line 461: calls LLM to rephrase comparative question into per-entity sub-questions.
  2. Lines 470-481: helper function to process one entity's sub-question (retrieve + answer).
  3. Lines 483-506: parallel execution via `ThreadPoolExecutor`.
  4. Lines 509-514: calls LLM to produce comparative answer combining individual results.
  - **Adapt:** replace "company name" entity with legal entities (`case_id`, `statute_id`, party names) from W4B. Replace per-company FAISS retrieval with per-entity filtered Qdrant retrieval from W4D.

**Question decomposition prompt (adapt):**
- `external/RAG-Challenge-2/src/prompts.py` `RephrasedQuestionsPrompt` (lines 18-70) — decomposes "Compare company A and B on X" into individual sub-questions. Schema: `RephrasedQuestion` with `company_name` + `rephrased_question` (lines 25-28).
  - **Adapt:** replace `company_name` field with `legal_entity` (case ID, statute number, party). Replace company-comparison framing with legal-comparison framing (amendment vs current, party A vs party B, jurisdiction A vs B).

**Comparative answer recomposition (adapt):**
- `external/RAG-Challenge-2/src/prompts.py` `ComparativeAnswerPrompt` (lines 345-403) — takes individual answers + original question → produces comparative synthesis.
  - **Adapt:** legal comparison language and answer types (current schema outputs boolean/number/name, not just free-text).

**Entity extraction for routing (adapt pattern):**
- `external/RAG-Challenge-2/src/questions_processing.py` `_extract_companies_from_subset()` (lines 163-182) — matches entity names from a lookup table (CSV, sorted by length). Simple but effective.
  - **Adapt:** use legal-entity extraction from W4B instead of CSV company lookup. Routing logic: 1 entity → single-doc path, 2+ entities → decomposition candidate.

### Enhance in current `src/`

**Answering pipeline (extend with decomposition path):**
- `src/submission/pipeline.py` `_answer_question()` (line ~420) — add decomposition routing before single-pass answering. If trigger fires → decompose → parallel sub-question execution → recompose → Pass B page finalization via W4A.
- `src/answering/service.py` `AnsweringService` — currently handles one question at a time. Decomposition requires calling retrieval + answering per sub-question, then aggregating.

**Page attribution recomposition:**
- `src/retrieval/page_lifter.py` `PageLifter.to_page_references()` (lines 94-109) — produces deduplicated page lists. For decomposition: must merge page lists from sub-questions, then apply W4A Pass A minimal-evidence pruning to the merged set (not union mechanically).

### New code

- Decomposition trigger policy — decides which questions escalate. Candidates: questions with 2+ legal entities from W4B extraction, questions classified as `cross_case` by question metadata, questions where baseline non-decomposition path returns null.
- Sub-question interface and provenance tracking (mapping original question → sub-questions → sub-results → final answer).
- Page-list recomposition with minimization (not mechanical union of sub-question pages).
- Legal-domain decomposition targets: amendment vs current-version, party A vs party B, jurisdiction A vs B, annex/schedule vs main body, temporal comparisons.

## 4. Working Notes

This task should be judged narrowly. It is successful only if it improves hard cross-case reasoning while staying selective and grounded.

It must not become a general fallback for ordinary retrieval or extractor failures. If the non-decomposition path is still weak, that is a problem for earlier Wave 4 tasks, not for this one.

## 5. Outcome

**Result target**: Selective, grounded decomposition/orchestration path for hard cross-case and comparative questions.  
**Next action**: Use as a selective escalation path after the baseline multi-document path is stable.
