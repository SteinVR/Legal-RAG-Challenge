# Task: TASK-W4D

# About

This task formalizes the retrieval-side upgrade that should happen after Wave 4 establishes stronger page attribution, typed extraction signals, and structural artifacts accepted from `TASK-W4C`. Its goal is to improve retrieval precision and coverage using richer chunking, richer query cues, and question-class-aware tuning.

This task owns retrieval/index behavior. It does not own parser routing, typed solver internals, or full question decomposition orchestration.

# Specification

## Target behavior

- Upgrade retrieval to exploit Wave 4 inputs without losing the current hybrid Qdrant backbone.
- Support richer chunk families and token-aware chunk sizing.
- Use query-side legal prefilters from `TASK-W4B` as soft retrieval guidance.
- Combine reranking, parent-page expansion, and question-class-aware tuning without breaking the page-attribution contract from `TASK-W4A`.

## Required interfaces and artifacts

- Retrieval must consume:
  - current and accepted new chunk families from `TASK-W4C`;
  - query-side legal prefilter signals from `TASK-W4B`;
  - page-attribution contract from `TASK-W4A`.
- Chunking/index config must expose:
  - token-aware sizing and overlap;
  - chunk-family enable/disable controls;
  - retrieval budgets for at least `case`, `statute`, `cross_case`, and `free_text`.
- Retrieval telemetry must make visible:
  - chunk-family participation;
  - prefilter usage;
  - reranking effect;
  - parent-page expansion effect.

## Development rules and non-goals

- Keep local hybrid Qdrant as the main backend.
- Do not convert query-side prefilters into hard single-document routing.
- Treat reranking as candidate refinement, not first-pass retrieval.
- Treat parent-page expansion as post-narrowing context expansion, not broad recall.
- Retrieval tuning must be asymmetric:
  - prioritize precision for `case` and `statute`;
  - preserve breadth for `cross_case`.
- Do not implement comparative decomposition in this task.

## Acceptance criteria

- Retrieval can use accepted Wave 4 chunk families without contract drift.
- Token-aware chunk sizing is explicitly defined and benchmarked.
- Query-side legal entities can influence retrieval as soft boosts/filters.
- Retrieval behavior is measurably tunable by question class.
- Reranking and parent-page expansion are integrated without breaking final page-attribution expectations.
- Embedding quality is evaluated on the chunk families that `TASK-W4C` freezes as accepted. If the current embedding model degrades on semantic-table or clause-heavy chunks, the degradation is documented explicitly and flagged for resolution.

## Test and evaluation expectations

- Indexing/retrieval regressions must cover:
  - existing Wave 3 chunk families;
  - accepted new chunk families from `TASK-W4C`;
  - with and without prefilter signals from `TASK-W4B`.
- Evaluation must include:
  - retrieval with vs without legal prefilters;
  - retrieval with vs without reranking;
  - retrieval with vs without parent-page expansion;
  - question-class-specific slices for `case`, `statute`, and `cross_case`.
- Chunk-size experiments must compare the baseline against the initial token-aware target and justify the retained default.

## Dependency assumptions

- Depends on stable query-prefilter outputs from `TASK-W4B`.
- Depends on the chunk families and schema enrichments that `TASK-W4C` freezes as accepted.
- Must remain compatible with the page-attribution contract from `TASK-W4A`.
- Must publish a stable multi-document retrieval path before `TASK-W4E` is accepted.

## 1. Summary

**Title**: Retrieval upgrade, chunk calibration & asymmetric tuning  
**Description**: Strengthen hybrid retrieval with token-aware chunking, richer chunk families, soft legal prefilters, reranking, parent-page expansion, and question-class-aware tuning.  
**Status**: Planned  
**Wave**: Wave 4 -- Baseline Recovery & Structural Upgrade

## 2. Scope

- **In scope**:
  - token-aware chunk sizing
  - accepted new chunk families
  - retrieval use of legal prefilters
  - reranking and parent-page expansion integration
  - asymmetric tuning by question class
  - retrieval telemetry for later ablations
- **Out of scope**:
  - parser branch ownership
  - typed extraction internals
  - comparative decomposition orchestration
- **Dependencies**:
  - `TASK-W4A` page-attribution contract
  - `TASK-W4B` legal prefilters
  - accepted chunk/schema outputs from `TASK-W4C`

## 3. Implementation Plan

- Freeze which chunk families and metadata are available for retrieval consumption.
- Introduce token-aware chunk-size defaults and calibrate them on legal documents.
- Integrate legal-prefilter signals as soft (non-blocking) guidance.
- Tune reranking and parent expansion without violating page-attribution expectations.
- Benchmark retrieval by question class and lock the asymmetric tuning policy.

## 4. Working Notes

This task should not become a grab bag. Its job is not to solve answering; its job is to ensure the retrieval layer can exploit the new signals and structures introduced elsewhere in Wave 4.

If `TASK-W4C` produces rich artifacts that do not survive retrieval A/B, this task should consume only the accepted subset rather than forcing architecture purity.

## 5. Outcome

**Result target**: Stable retrieval/index upgrade that consumes Wave 4 signals cleanly and exposes tuned behavior across question classes.  
**Next action**: Hand a stable multi-document retrieval substrate to `TASK-W4E`.
