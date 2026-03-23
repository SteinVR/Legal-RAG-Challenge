# Task: TASK-W4D

# About

This task formalizes the retrieval-side upgrade that should happen after Wave 4 establishes stronger page attribution, structured typed solving signals, and structural artifacts accepted from `TASK-W4C`. Its goal is to improve retrieval precision and coverage using richer chunking, richer query cues, question-class-aware tuning, and solver-ready evidence packaging.

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
- Retrieval outputs must preserve solver-ready evidence metadata:
  - stable page numbers;
  - chunk/page provenance;
  - parent-page relationships needed for Pass B and typed solver page reporting.
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
- Reranking and parent-page expansion are integrated without breaking typed solver page reporting or final page-attribution expectations.
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
- Retrieval regressions must include evidence-bundle integrity checks for the structured typed solver (`TASK-W4B`) and Pass B narrowing (`TASK-W4A`).
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
  - typed solver internals
  - comparative decomposition orchestration
- **Dependencies**:
  - `TASK-W4A` page-attribution contract
  - `TASK-W4B` legal prefilters
  - accepted chunk/schema outputs from `TASK-W4C`

## 3. Implementation Plan

- Freeze which chunk families and metadata are available for retrieval consumption and structured typed solving.
- Introduce token-aware chunk-size defaults and calibrate them on legal documents.
- Integrate legal-prefilter signals as soft (non-blocking) guidance.
- Tune reranking and parent expansion without violating page-attribution expectations or solver-ready evidence packaging.
- Benchmark retrieval by question class and lock the asymmetric tuning policy.

## Source References & Adaptation Map

### Enhance in current `src/`

**Chunking (extend current multi-level system):**
- `src/indexing/service.py` `build_index_chunks()` (lines 723-781) — current 5-level chunking (page, section, clause, microchunk, table). Extend with token-aware sizing. Currently microchunks use `max_sentences=2` (line 903), not token count.
- `src/indexing/service.py` `_split_microchunks()` (lines 903-913) — replace sentence-count splitting with token-aware splitting. Keep sentence boundaries as split points but enforce token budget.
- `src/indexing/service.py` `_clause_chunks_for_page()` (lines 811-850) — clause extraction via regex. If W4C provides structural clause boundaries, consume them here instead of regex.

**Retrieval (extend current hybrid pipeline):**
- `src/retrieval/service.py` `RetrievalService.retrieve()` (lines 119-210) — current pipeline: hybrid_search → rerank → compress → page_lift. Insert parent-page expansion after rerank, before compress. Add question-class-aware budget selection.
- `src/retrieval/hybrid_search.py` `QdrantHybridSearchBackend` (lines 35-142) — dense-first with RRF sparse fusion. Add prefilter payload conditions from W4B legal entities.
- `src/retrieval/reranker.py` `QwenReranker` (lines 192-254) — current Qwen3-Reranker-0.6B. Keep as-is but study RAG-Challenge-2 hybrid scoring pattern for potential improvement.
- `src/retrieval/service.py` budgets (candidate_budget=10, rerank_budget=5, evidence_budget=3) — make these per-question-class: tighter for case/statute (precision), wider for cross_case (breadth).
- `src/retrieval/service.py` evidence payloads — preserve page-stable metadata so W4B structured schemas can report `relevant_pages` and W4A can validate them.

**Embedding (evaluate, extend if needed):**
- `src/indexing/service.py` `Qwen3DenseEmbedder` (lines 227-292) — current embedder. Evaluate quality on new chunk types (semantic tables, clause chunks) from W4C. If degradation found, document and flag.

### Adapt from `external/RAG-Challenge-2`

**Token-aware chunking (adapt sizing logic):**
- `external/RAG-Challenge-2/src/text_splitter.py` `_split_page()` (lines 70-85) — uses `RecursiveCharacterTextSplitter.from_tiktoken_encoder()` with `chunk_size=300`, `chunk_overlap=50`, model `"gpt-4o"` (o200k_base tokenizer). Adapt: use same token-aware principle but with the tokenizer matching current embedding model (Qwen3), not GPT-4o. Apply to microchunk and clause splitting in current indexing.
- `external/RAG-Challenge-2/src/text_splitter.py` `count_tokens()` (lines 62-68) — tiktoken-based token counting. Reference for how to integrate token counting into current chunking.

**Reranking pattern (reference for hybrid scoring):**
- `external/RAG-Challenge-2/src/reranking.py` `LLMReranker.rerank_documents()` (lines 88-158) — combined scoring: `0.7 * llm_score + 0.3 * vector_score`. Current Qwen3-Reranker already produces scores; this pattern shows how to combine reranker scores with initial retrieval scores for better ranking.
- `external/RAG-Challenge-2/src/reranking.py` `get_rank_for_single_block()` (lines 46-62) — per-block relevance scoring (0-1). Reference for scoring granularity.

**Parent-page expansion (adapt retrieval pattern):**
- `external/RAG-Challenge-2/src/retrieval.py` `VectorRetriever.retrieve_by_company_name()` (lines 153-208) — when `return_parent_pages=True`: retrieves chunks, maps to parent pages, returns full page text. Adapt: current `src/retrieval/page_lifter.py` already does chunk-to-page lifting. Extend `PageLifter.lift()` to optionally return full parent-page text for context expansion after reranking.

### New code

- Per-question-class retrieval budget selection (case/statute precision vs cross_case breadth) — no analog in either codebase.
- Prefilter payload integration in Qdrant queries (consume W4B legal entity signals as soft filters).
- Embedding quality evaluation harness for new chunk families.

## 4. Working Notes

This task should not become a grab bag. Its job is not to solve answering; its job is to ensure the retrieval layer can exploit the new signals and structures introduced elsewhere in Wave 4.

If `TASK-W4C` produces rich artifacts that do not survive retrieval A/B, this task should consume only the accepted subset rather than forcing architecture purity.

## 5. Outcome

**Result target**: Stable retrieval/index upgrade that consumes Wave 4 signals cleanly, emits solver-ready evidence bundles, and exposes tuned behavior across question classes.  
**Next action**: Hand a stable multi-document retrieval substrate and page-stable evidence packaging to `TASK-W4B` and `TASK-W4E`.
