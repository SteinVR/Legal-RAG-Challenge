# Unified Document Processing Architecture

## Purpose

This document is the canonical target architecture for the project's document-processing stack.
It combines three sources into one opinionated design:

1. `opendataloader-pdf` for layout-aware parsing, structural recovery, and parser-side sanitation.
2. `external/RAG-Challenge-2` for rich intermediate parse artifacts, benchmark-gated LLM table serialization, parent-page retrieval ideas, reranking patterns, and selective comparative decomposition.
3. The current project implementation for page-grounded canonical artifacts, cross-page table provenance, local hybrid retrieval, typed answering, validation, and submission discipline.

The goal is not to "switch parser and hope." The goal is to build a stronger, grounded, competition-grade evidence pipeline without throwing away the parts of the current stack that already solve the legal challenge correctly.

## Design Position

Offline preprocessing is free in the final eval. The stack should therefore spend preprocessing budget aggressively where the spend improves grounding, table recall, or structure recovery. That includes expensive enrichment steps such as LLM table serialization.

The correct synthesis is:

- keep the current canonical page-grounded corpus as the downstream SSOT;
- add a richer upstream parser layer with structure, coordinates, and parser arbitration;
- preserve and strengthen the current table provenance logic;
- treat LLM table serialization as a default-on enrichment track that must survive legal-domain A/B testing rather than as a permanent axiom;
- import parent-page retrieval, reranking, and selective decomposition ideas from `RAG-Challenge-2`;
- add an explicit page-attribution-precision stage between retrieval and final answer emission;
- upgrade typed extraction explicitly by answer type rather than treating extraction-first answering as "already solved";
- use question-side legal entity extraction as a retrieval prefilter signal, not as a hard one-document router;
- use parser structure to replace heuristic heading recovery where available.

This remains a grounded legal evidence engine, not a generic document chatbot.

## Source Responsibility Split

### `opendataloader-pdf`

Primary responsibility:

- layout-aware parsing;
- reading-order recovery;
- typed structural nodes;
- page and bbox attribution;
- tagged-PDF exploitation;
- parser-side sanitation.

Adopt:

- structural parse output with node types, hierarchy, page numbers, and bounding boxes;
- parser-side filtering for hidden text, off-page text, tiny non-semantic text, and related layout poison;
- born-digital/tagged-PDF specialization;
- table and heading recovery when the PDF already contains useful structure.

Adapt:

- treat it as an upstream parser branch, not the canonical downstream format;
- map its structure into the current canonical page corpus instead of replacing the corpus contract;
- use it selectively on eligible pages/documents rather than forcing it on every PDF.

Reject:

- any design that depends on `opendataloader-pdf` alone being the only parser;
- any design that downgrades page-grounded canonical artifacts in favor of parser-native JSON only.

### `external/RAG-Challenge-2`

Primary responsibility:

- rich intermediate report pattern before flattening;
- benchmark-gated LLM table serialization;
- parent-page retrieval pattern;
- reranking pattern;
- selective comparative decomposition.

Adopt:

- rich intermediate table artifacts with raw markdown, HTML, JSON, page, and bbox;
- table serialization using table HTML plus nearby context;
- semantic table blocks as first-class retrieval objects;
- parent-page expansion after initial fine-grained retrieval;
- bounded LLM reranking on a narrowed candidate set;
- selective decomposition of complex comparative questions into simpler sub-questions.

Adapt:

- convert their parent-document retrieval idea into parent-page retrieval for legal PDFs;
- convert company-style document routing into soft legal prefilter signals such as `case_id`, `statute_id`, and document-title matches;
- apply decomposition to legal question classes rather than company comparisons;
- keep structured answering prompts and page-reference validation, but subordinate them to the current extraction-first answering backbone.

Reject:

- company-routed single-report retrieval as a foundational assumption;
- per-document FAISS as the main retrieval architecture;
- LLM-first answering as the default path;
- competition shortcuts such as no tests, minimal error handling, and manually wired stage selection.

### Current Project Implementation

Primary responsibility:

- canonical page-grounded corpus artifacts;
- explicit page-level triage and OCR fallback;
- cross-page table merge with row-level provenance;
- local dense+sparse retrieval in embedded Qdrant;
- typed answering and validation discipline;
- submission correctness.

Keep authoritative:

- `corpus.jsonl`, `page_map.json`, and `corpus_manifest.json`;
- current page-grounded `CanonicalPageRecord`;
- cross-page table merge plus row provenance;
- local hybrid retrieval and page-lifting;
- typed answer routing and deterministic extraction-first logic;
- local validation, telemetry discipline, and submission packager.

## Adopt / Adapt / Reject Matrix

| Area | Take From | Decision | Unified Rule |
| --- | --- | --- | --- |
| Structural parser | `opendataloader-pdf` | Adopt + adapt | Use as structural parser branch for born-digital, tagged, and layout-complex pages. |
| OCR fallback | Current project | Keep | Current cheap native analysis plus OCR fallback stays the safety path for scan-like pages. |
| Parser-side sanitation | `opendataloader-pdf` | Adopt | Filter hidden/off-page/tiny/layout-poison text before normalization. |
| Rich intermediate parse artifact | `RAG-Challenge-2` | Adopt + adapt | Preserve rich parser outputs as sidecars, but do not flatten them away as the only truth. |
| Canonical page corpus | Current project | Keep | Downstream SSOT remains page-grounded and validator-friendly. |
| Heading recovery | `opendataloader-pdf` + current | Adapt | Structural headings override current regex heuristics; heuristics remain fallback. |
| Cross-page table continuity | Current project | Keep | Current merge and row provenance logic remains authoritative. |
| LLM table serialization | `RAG-Challenge-2` | Adapt | Run as default-on enrichment during experiments, but keep an explicit kill switch if legal-domain A/B shows net retrieval degradation. |
| Chunk families | Current project + synthesis | Adapt | Emit page, section, clause, microchunk, row-table, and semantic-table chunks. |
| Vector backend | Current project | Keep | Main backend remains local hybrid Qdrant, not per-document FAISS. |
| BM25 | Current project | Keep | Sparse retrieval remains part of the main hybrid path; do not leave it as an unused side index. |
| Parent expansion | `RAG-Challenge-2` | Adapt | Expand from retrieved chunks to parent pages after candidate narrowing. |
| Reranking | `RAG-Challenge-2` + current roadmap | Adopt + adapt | Add bounded reranking after hybrid candidate generation; do not use reranking as first-pass retrieval. |
| Query-side legal prefilters | `RAG-Challenge-2` pattern + current domain | Adapt | Use extracted `case_id`, `statute_id`, and title cues as soft retrieval filters or boosts, never as one-document lock-in. |
| Page attribution precision | Baseline-driven synthesis | Adopt | Add a dedicated minimal-evidence selection stage after retrieval and before answer finalization. |
| Comparative decomposition | `RAG-Challenge-2` | Adapt | Use selectively for legal comparison classes, not as default routing. |
| Typed answering | Current project | Keep | Stay extraction-first; borrow only prompt/schema discipline and page-reference validation. |
| Local validation | Current project | Keep | Submission correctness, telemetry validation, and page-reference discipline remain non-negotiable. |

## Unified Target Architecture

### 1. Parser Arbitration Layer

The stack should become explicitly hybrid.

Recommended routing:

1. Run the current cheap native analysis first for every document/page.
2. Route pages with broken-font signals, high replacement-character density, or OCR-dominant characteristics through the current OCR path as the default safety mechanism.
3. Route tagged PDFs through `opendataloader-pdf` with structure-tree extraction enabled as a distinct fast path.
4. Route born-digital or layout-complex pages through `opendataloader-pdf` hybrid mode as the preferred structural parser path when the Docling backend is available.
5. Use local-only `opendataloader-pdf` mode only as a fallback structural path when hybrid mode is unavailable or fails health checks.
6. If the structural parser fails, yields empty structure, or returns poor coverage, fall back to the current parser output.
7. Preserve parser provenance per page and per normalized block.

Preferred structural-parser PoC configuration:

- batch documents per `convert()` invocation to amortize JVM startup cost;
- persist JSON sidecars as the required raw output format;
- prefer `table_method="cluster"` for legal table extraction experiments;
- record whether the page used structure-tree extraction, hybrid mode, or local-only mode;
- treat Docling backend availability as an explicit infrastructure dependency of the hybrid path.

This means the future system is not "Paddle vs OpenDataLoader." It is a routed, parser-arbitrated stack.

### 2. Raw Structural Sidecars

Add a raw-parse layer before canonical corpus generation.

Recommended artifact families:

- `data/{phase}/raw_parse/current/{doc_id}.json`
- `data/{phase}/raw_parse/opendataloader/{doc_id}.json`
- optional future parser branches under the same layout

Each sidecar should preserve:

- parser name and parser version;
- document-level metadata;
- page list and page geometry;
- typed nodes/blocks in reading order;
- node text and bbox;
- heading/list/table structure;
- raw table objects including cell-level structure when available;
- parser diagnostics and route decisions.

JSON is the required sidecar format because bbox, node typing, caption links, and parser diagnostics must survive intact. Markdown, HTML, and plain-text renders can exist as debug artifacts only.

This layer exists to preserve truth and support A/B parser experiments. It is not the main retrieval contract.

### 3. Structural Normalization Layer

Normalize rich parser output into a legal-document-friendly intermediate representation before building the canonical page corpus.

Required behaviors:

- remove headers, footers, TOC noise, and layout poison;
- remove parser-visible glyph garbage and other post-parse artifacts that pollute retrieval text without carrying legal meaning;
- preserve heading hierarchy;
- preserve list semantics, nesting depth, and clause boundaries when explicit;
- preserve annex, schedule, appendix, and footnote markers;
- preserve caption-to-table or caption-to-image linkage when available so downstream table serialization can inherit local context;
- preserve page-local reading order;
- preserve source block ids and bbox for debug linkage.

Normalization should also retain parser calibration metadata when useful, including whether reading order came from tagged structure or XY-Cut-style recovery, because legal multi-column pages may require parser-tuning experiments.

When structural headings are available from the parser, they override current regex heading inference.
When they are absent, the current heuristics remain the fallback path.

### 4. Canonical Page Corpus

Keep the current canonical page corpus as the stable downstream SSOT, but produce it from richer inputs.

The canonical corpus must remain:

- page-scoped;
- grounded to physical PDF pages;
- retrieval-oriented;
- validator-friendly;
- stable enough to support existing indexing, retrieval, answering, and submission code.

Target enrichments to the canonical contract:

- parser provenance for each page;
- heading path or structural section path when known;
- source normalized block ids for debug traceability;
- optional role metadata for blocks such as `heading`, `clause`, `annex`, `footnote`, `table-context`.

### 5. Unified Table Pipeline

This is where the project should be most aggressive.

Each table should exist in three parallel forms:

1. Structural form:
   raw rows/cells, raw JSON, raw HTML, bbox, page span, and parser provenance.
2. Canonical retrieval form:
   current `TableBlock` and provenance-preserving row-level `SerializedTableBlock`.
3. Semantic enrichment form:
   LLM-serialized context-independent table entity blocks.

Required policy:

- preserve the current cross-page table merge and row-level page provenance as authoritative;
- preserve raw table HTML and JSON for every table that reaches the canonical corpus;
- run LLM table serialization over HTML tables with nearby textual context and caption-linked context when available;
- keep semantic serialized-table blocks alongside row-level table blocks;
- index both row-level and semantic table evidence;
- keep a config-level kill switch so semantic table blocks can be disabled if legal-domain A/B testing shows worse retrieval precision or poorer signal-to-noise.

LLM table serialization is still worth treating as a serious enrichment track because preprocessing budget is available and legal tables often carry decisive evidence in schedules, appendices, tariffs, sanctions tables, and fee grids. It should, however, be retained only if legal-domain A/B testing confirms a net score benefit.

### 6. Chunking and Indexing

Produce multiple chunk families from one canonical corpus.

Required chunk families:

- page chunks;
- section chunks;
- clause chunks;
- microchunks;
- row-level table chunks;
- semantic serialized-table chunks;
- optional annex/schedule chunks where the normalized structure exposes them cleanly.

Chunk sizing must be token-aware rather than character-only. The initial target should be approximately 300 tokens with approximately 50 tokens overlap for clause-like text, followed by benchmark calibration on legal PDFs with long sections and schedules.

Chunk metadata should include at minimum:

- `doc_id`;
- `page_span`;
- `chunk_type`;
- heading path;
- clause label when available;
- document family;
- parser provenance;
- table id or source block ids when relevant.

The main index backend remains the current local hybrid Qdrant stack.
Do not replace it with per-document FAISS.

The current Qwen3 embedding path remains the default baseline, but enriched chunk families such as semantic tables and clause chunks should trigger an explicit embedding-quality review before the architecture is considered stable.

### 7. Retrieval

Retrieval should combine the current hybrid backbone with imported ideas from `RAG-Challenge-2`.

Recommended flow:

1. Retrieve chunk candidates from Qdrant across multiple chunk families.
2. Preserve chunk ids, page spans, table ids, and parser provenance.
3. Rerank a bounded candidate set with an LLM or reranker model.
4. Expand top chunk candidates to parent-page context where useful.
5. Compress the final evidence set while preserving page-grounded support.

Required upgrades:

- reranking is candidate refinement, not first-pass retrieval;
- parent-page expansion happens after narrowing, not before;
- table chunks and clause chunks must survive early recall stages rather than being flattened into page text too early;
- query-side `case_id`, `statute_id`, and title signals should act as soft retrieval filters or boosts when extracted reliably;
- retrieval tuning must be asymmetric by question class: favor page precision for `case` and `statute` questions, but preserve multi-document breadth for `cross_case` questions.

### 8. Page Attribution Precision

The stack needs a dedicated two-pass stage around answering so final page attribution is both minimal and temporally consistent.

Pass A happens after retrieval and before answer finalization.
It prunes candidate pages down to the smallest evidence set that still plausibly supports extraction or generation.

Pass B happens after an answer attempt.
It finalizes the page list for the emitted answer and is the only stage that may emit an empty page list for a true no-answer outcome.

Required behaviors:

- in Pass A, choose minimal sufficient candidate pages instead of forwarding raw top-k retrieval pages;
- suppress title pages, cover pages, indexes, and repeated boilerplate unless they carry direct answer evidence;
- prefer answer-bearing pages over neighboring context pages when both are available;
- in Pass B, emit empty retrieved-page lists only when the final answer is a true no-answer and the system cannot support a grounded positive answer;
- preserve traceability from final pages back to the candidate chunks that justified them.

This stage exists because grounding precision is a score multiplier, and baseline results show that over-retrieval is currently a larger problem than missing all evidence.

### 9. Answering and Grounding Guardrails

Keep the current extraction-first typed answering backbone.

Import only these ideas from `RAG-Challenge-2`:

- explicit schema-specific prompting;
- page-reference validation against retrieved pages;
- selective comparative decomposition for hard legal question classes.

Do not convert the whole answering stack into chain-of-thought-first generation.
The current project is right to keep deterministic extraction as the default path.

Typed extraction upgrade is required, not optional.

Required typed-answer tracks:

- boolean extraction with explicit negation and polarity handling;
- number extraction with better title-page and year suppression;
- name and names extraction with canonical entity-span selection for case ids, party names, and document labels;
- date extraction with stricter normalization and ambiguity handling;
- confidence calibration so abstention is thresholded and type-aware rather than binary and overly conservative.

Recommended decomposition targets:

- amendment vs current-version comparisons;
- party A vs party B comparisons;
- jurisdiction A vs jurisdiction B comparisons;
- annex/schedule vs main body comparisons;
- temporal comparisons across versions or dates.

Cross-case and multi-document reasoning should be treated as a primary upgrade track rather than a distant edge-case optimization because the baseline already shows this slice is material.

### 10. Validation and Submission Discipline

The current project's validation discipline remains authoritative.

Keep:

- local submission validation;
- telemetry validation;
- page-reference correctness checks;
- explicit handling of unanswerable cases;
- artifact manifests and reproducible config discipline.

Imported page-reference validation from `RAG-Challenge-2` should be used as a final guardrail after retrieval and answering, not as the main grounding mechanism.

Grounding validation must degrade pages before it destroys answer content. The validator should first attempt to trim unsupported pages or downgrade page attribution confidence, and only collapse to a fallback answer when the answer text itself is not supportable.

## Target Public Contract Additions

The document implies these interface-level additions for later implementation work:

- new raw parse sidecar artifacts under `data/{phase}/raw_parse/`;
- parser provenance metadata on pages and normalized blocks;
- preserved raw table HTML and raw table JSON in canonical or sidecar-adjacent artifacts;
- semantic serialized-table blocks as a new retrieval-facing chunk family;
- heading-path metadata propagated from normalization into chunking;
- optional source block ids or normalized block ids for debug linkage from chunks back to raw parser output;
- optional query-side legal prefilter signals such as `case_id`, `statute_id`, or title matches;
- minimal-evidence page selection metadata for final grounding decisions;
- typed-extraction confidence signals that can be calibrated per answer type.

These are additive changes. The current canonical page-grounded corpus remains the stable operational contract until later code changes deliberately revise it.

## What Not To Import As-Is

Do not import these parts from `RAG-Challenge-2` as direct architecture choices:

- company-routed retrieval that narrows search to one report by question parsing;
- per-document FAISS as the main vector architecture;
- BM25 as an optional dead-end side path rather than part of the main hybrid retrieval design;
- long chain-of-thought-first answering as the default mechanism;
- document flattening so early that downstream retrieval loses structural advantages;
- competition shortcuts such as no tests, minimal error handling, and manual pipeline control.

Do not import these parts from `opendataloader-pdf` as direct architecture choices:

- parser-native JSON as the only persistent truth;
- a one-parser-for-everything policy;
- any design that weakens the current page-grounded canonical contract.

## Phased Implementation Sequence

### Phase 1. Page attribution precision and validation policy

- add Pass A minimal-evidence page pruning after retrieval and before final answer emission;
- add title-page and boilerplate suppression rules;
- align Pass B final page attribution with grounded no-answer behavior;
- change grounding validation from answer-suppression-first to page-degradation-first.

The intended mainline pipeline should include both Pass A pruning and page-degradation-first validation because they address different observed failure modes. The A/B plan separates them only to measure contribution cleanly.

### Phase 2. Typed extraction and query-side prefilters

- add per-type extraction upgrades for boolean, number, name, names, and date;
- add canonical legal entity extraction for `case_id`, `statute_id`, and document-title cues;
- feed those cues into retrieval as soft filters or boosts;
- enable baseline multi-document reasoning without decomposition: better cross-case retrieval breadth, entity-aware matching, and typed extraction over evidence from multiple documents.

### Phase 3. Raw parse sidecars and parser branch contract

- add raw parse artifact families;
- define parser provenance and route decisions;
- create one-to-one parser branch comparisons on the same documents;
- validate `opendataloader-pdf` hybrid mode, local-only mode, `table_method="cluster"`, and JVM batching assumptions on warmup legal PDFs.

### Phase 4. Structural normalization

- build the normalization layer from structural parser output to canonical legal blocks;
- replace regex heading recovery with structural headings when available;
- keep current heuristics as fallback only;
- add artifact cleaning, caption linkage preservation, and list-nesting preservation.

### Phase 5. Unified table pipeline

- preserve raw table HTML/JSON;
- keep current row-level table blocks authoritative;
- add default-on, benchmark-gated LLM table serialization;
- emit both row-level and semantic-table chunk families.

### Phase 6. Retrieval upgrade

- add reranking;
- add parent-page expansion;
- make chunk-family-aware retrieval and compression a first-class design rule;
- add asymmetric tuning by question class.

### Phase 7. Cross-case decomposition track

- add full question decomposition and orchestration for comparative or cross-case questions once the baseline multi-document path from Phase 2 is stable;
- treat it as a targeted escalation path, not a default answer route.

## Validation and A/B Plan

The unified stack should be judged on measurable competition-facing outcomes.

Primary checks:

- page parse quality on hard legal PDFs;
- heading continuity;
- annex and schedule recovery;
- cross-page table continuity;
- table-answer recall;
- page grounding precision;
- deterministic-answer accuracy;
- fallback suppression rate on answerable free-text questions;
- cross-case and multi-document slice score;
- unanswerable behavior;
- preprocessing runtime and failure rate.

Mandatory A/B comparisons:

1. Current parser baseline vs current parser + raw structural sidecars.
2. Current parser baseline vs `opendataloader-pdf` tagged fast path with structure-tree extraction on tagged PDFs.
3. Current retrieval vs retrieval + Pass A minimal-evidence page pruning.
4. Current validation policy vs page-degradation-first validation with unchanged retrieval pages.
5. Current retrieval/validation vs the combined Pass A pruning + page-degradation-first validation stack.
6. Current answering vs typed-extraction upgrade with calibrated abstention thresholds.
7. Current parser baseline vs `opendataloader-pdf` hybrid vs local-only on born-digital and tagged pages.
8. Current table pipeline vs current table pipeline + default-on LLM table serialization.
9. Current retrieval vs retrieval + reranking + parent-page expansion + query-side legal prefilters.
10. Current answering vs selective legal decomposition on suitable question slices.

## Net Takeaway

The target split of responsibility is:

- `opendataloader-pdf`: parser truth, structure, sanitation, layout semantics.
- `external/RAG-Challenge-2`: benchmark-gated table enrichment, parent-page retrieval pattern, reranking pattern, and selective decomposition pattern.
- current project: canonical grounding contract, legal page provenance, local hybrid retrieval, typed answering, validation, and submission correctness.

That is the correct synthesis for this project.

Anything weaker leaves competition upside on the table.
Anything more radical risks throwing away the parts of the current system that are already correct.
