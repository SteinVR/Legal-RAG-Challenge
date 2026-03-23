# Unified Ingestion Stack Synthesis

## Purpose

This document defines the target ingestion and retrieval-facing document-processing stack for the legal challenge system by combining three sources:

1. `opendataloader-pdf` as the primary source of layout-aware parsing and parser-side sanitation.
2. `external/RAG-Challenge-2` as the primary source of table serialization, parent-page retrieval patterns, and comparative question decomposition ideas.
3. The current project implementation as the source of truth for page-grounded canonical artifacts, cross-page table provenance, local hybrid retrieval, typed answering, validation, and submission discipline.

The goal is not to replace the current system wholesale. The goal is to produce a stronger unified stack that preserves what is already correct and hard-won in the current codebase while adding the structural advantages that the current baseline does not yet capture.

## Design Position

The correct move is not "switch parser and hope for better answers." The correct move is:

- keep the current canonical page-grounded corpus contract as the downstream operational spine;
- add a richer upstream parse layer with structure, coordinates, and parser arbitration;
- preserve and strengthen the current table provenance logic;
- import table-to-text serialization and parent-page retrieval from `RAG-Challenge-2`;
- use parser structure to replace current heuristic heading recovery where possible.

This means the future system remains a grounded legal evidence engine, not a generic document chatbot.

## What To Keep From The Current Implementation

The current implementation already has several things that should remain authoritative:

- page-grounded canonical corpus artifacts:
  - `corpus.jsonl`
  - `page_map.json`
  - `corpus_manifest.json`
- explicit page-level parse routing and OCR fallback logic in `src/ingestion/pdf_parser.py`;
- deterministic quality signals and triage in `src/ingestion/page_triage.py`;
- cross-page table merge plus row-level page provenance in `src/ingestion/table_serializer.py`;
- canonical page records and submission-facing page references in `src/common/schemas.py`;
- local dense+sparse retrieval with Qdrant in `src/indexing/` and `src/retrieval/`;
- typed answer routing and extraction-first answer handling in `src/answering/`;
- local validation and submission packaging discipline in `src/evaluation/` and `src/submission/`.

These are not side details. They are the main reason the current system is competition-viable. Any imported ideas must fit around them.

## What To Take From `opendataloader-pdf`

### 1. Layout-aware parsing as a first-class upstream layer

Use `opendataloader-pdf` to produce a rich document structure layer for eligible PDFs or pages. The important gain is not "more text." The gain is:

- typed document nodes;
- explicit reading order;
- page and bounding box attribution;
- better heading/list/table/cell recovery;
- tagged-PDF exploitation when available;
- parser-side content sanitation for hidden or layout-poisoning text.

This should become a new raw parse sidecar, not a replacement for the current canonical corpus contract.

### 2. Parser-side sanitation

Adopt parser-side filtering of:

- hidden text;
- off-page text;
- tiny non-semantic text;
- hidden OCG content;
- other visually irrelevant artifacts that can poison retrieval.

This is useful even if the retrieval gain is modest, because it directly reduces garbage evidence entering the corpus.

### 3. Tagged/born-digital specialization

Use `opendataloader-pdf` as the preferred structural parser for:

- tagged PDFs;
- born-digital PDFs with strong layout semantics;
- complex multi-column pages;
- pages where heading/list/table structure matters more than OCR.

Do not force it as the only parser for scanned or OCR-dominant cases.

### 4. Structural outputs to preserve

The unified stack should preserve from `opendataloader-pdf`:

- page number;
- node type;
- node text;
- bounding box;
- parent-child relationships when available;
- reading-order position;
- table and cell structure;
- heading depth/label semantics;
- parser metadata and quality or source notes when available.

## What To Take From `RAG-Challenge-2`

### 1. Rich parse artifact pattern

`RAG-Challenge-2` gets one important thing exactly right: it keeps a rich intermediate report before flattening. Their `JsonReportProcessor` stores:

- `metainfo`;
- `content`;
- `tables`;
- `pictures`;
- page and bbox metadata.

We should take that intermediate-artifact idea, but not their later flattening as the main long-term contract.

### 2. Table serialization workflow

This is the most valuable import from `RAG-Challenge-2`.

Use their pattern:

- extract table HTML plus nearby textual context;
- serialize each table into context-independent `information_block` records;
- store serialized output alongside raw/markdown/HTML table representations;
- index serialized table blocks as independent retrieval objects.

This should be added on top of the current table pipeline, not instead of it.

### 3. Parent-page retrieval pattern

Their parent-document retrieval idea is useful and should be adapted into parent-page retrieval for legal PDFs:

- retrieve fine-grained chunks first;
- then expand selected chunks to parent page context;
- preserve original fine-grained evidence anchors;
- answer with parent-page context only after candidate narrowing.

This fits our scoring much better than raw parent-document expansion.

### 4. Comparative decomposition

Take the decomposition idea, but re-target it for legal questions rather than company comparisons. The useful pattern is:

- rewrite one comparative question into multiple simpler sub-questions;
- retrieve/answer them independently;
- combine answers into a final comparative or synthesis answer.

In our domain this applies to:

- amendment vs current-version questions;
- party A vs party B questions;
- jurisdiction A vs jurisdiction B questions;
- annex/schedule vs main body questions;
- temporal comparisons across legal versions or dates.

### 5. Page-reference validation

Keep their idea of validating claimed page references against retrieved pages. This should be used as a final guardrail in our answering stage, not as the main grounding mechanism.

## What Not To Take From `RAG-Challenge-2`

Do not import these parts as-is:

- the assumption that retrieval can be narrowed to one document by company-name routing;
- per-document FAISS as the main retrieval architecture;
- OpenAI `text-embedding-3-large` as the default embedding path;
- answer generation that relies primarily on long chain-of-thought rather than deterministic extraction-first logic;
- the production shortcuts:
  - no tests
  - minimal error handling
  - pipeline stages wired through uncommented scripts and manual flows.

These were good competition shortcuts for ERC2. They are not the right backbone for the current project.

## Unified Target Architecture

### Stage 1. Dual-layer parse architecture

Introduce two layers instead of one.

#### A. Raw structural parse layer

New raw parse artifacts per document should preserve the richest available representation from the chosen parser branch.

Recommended artifact families:

- `raw_parse/current/{doc_id}.json`
- `raw_parse/opendataloader/{doc_id}.json`
- optional future parser branches under the same pattern

Each raw parse artifact should contain:

- parser name and version;
- document-level metadata;
- page list;
- typed nodes/blocks with bbox and reading order;
- tables with raw structural form;
- parser diagnostics;
- source page references.

This layer is for truth preservation and parser experiments.

#### B. Canonical page corpus layer

Keep the current canonical page corpus as the stable downstream contract, but enrich how it is produced.

The canonical corpus remains:

- page-scoped;
- grounded to physical PDF pages;
- retrieval-oriented;
- validator-friendly.

The current `CanonicalPageRecord` stays the operational SSOT, but its inputs become richer.

### Stage 2. Parser arbitration

The unified system should not choose one parser for every page. It should arbitrate.

Recommended routing:

1. Run the current cheap native analysis first for every document/page.
2. If the page is scan-like or OCR-dominant, keep the current OCR route as the default safety path.
3. If the page is born-digital, tagged, or layout-complex, prefer `opendataloader-pdf` as the structural parser.
4. If `opendataloader-pdf` fails or produces low-confidence/empty structure, fall back to the current parser output.
5. Preserve parser provenance per page or block in the raw parse layer.

This makes the system hybrid by design instead of forcing one global parser bet.

### Stage 3. Text and structure normalization

Build a normalization layer that converts rich parser nodes into canonical legal document structure.

This layer should:

- drop header/footer/TOC noise;
- preserve heading hierarchy;
- preserve list semantics;
- preserve clause boundaries when explicitly available;
- preserve annex/schedule markers;
- preserve page-local reading order;
- retain bbox on normalized blocks for debugging and future layout-aware retrieval.

When structural headings are available from the parser, they override our current regex-based heading inference.
When they are not available, the current heuristics remain as fallback.

### Stage 4. Unified table pipeline

This is where the current project and `RAG-Challenge-2` should be combined most aggressively.

#### Keep from the current project

- cross-page table merge logic;
- row-level provenance;
- header inference discipline;
- no silent row loss;
- canonical `TableBlock` and `SerializedTableBlock` discipline.

#### Add from `RAG-Challenge-2`

- preserve raw table JSON and HTML in the raw parse layer;
- run LLM serialization over HTML tables with local textual context;
- generate context-independent table entity blocks;
- index those serialized table entity blocks separately from plain page text.

#### Unified output policy

Each table should have three forms:

1. Structural form:
   - raw rows/cells
   - cell structure
   - bbox
   - page span

2. Canonical retrieval form:
   - current `TableBlock`
   - row-level provenance-preserving serialized rows

3. Semantic enrichment form:
   - `RAG-Challenge-2`-style LLM table serialization blocks

This is the correct place to be redundant. Tables are too valuable in legal corpora to keep only one representation.

### Stage 5. Chunking and indexing

The unified stack should produce multiple chunk families from one canonical corpus.

Recommended chunk families:

- page chunks;
- section chunks;
- clause chunks;
- microchunks;
- row-level table chunks;
- semantic serialized-table chunks;
- optional annex/schedule chunks.

Chunk metadata should include:

- `doc_id`;
- `page_span`;
- `chunk_type`;
- structural heading path;
- clause label;
- document family;
- parser provenance;
- optional bbox summary or block ids for debug linkage.

The current Qdrant dense+sparse stack remains the main index backend.
Do not replace it with per-document FAISS.

### Stage 6. Retrieval

Retrieval should combine:

- current dense+sparse candidate generation;
- `RAG-Challenge-2`-style LLM reranking on the narrowed candidate set;
- parent-page expansion after chunk retrieval;
- page-level dedupe and evidence compression;
- chunk-family diversity so table evidence and clause evidence can both survive early recall stages.

Recommended retrieval flow:

1. Retrieve top chunk candidates from Qdrant across chunk families.
2. Preserve original chunk ids and page spans.
3. Rerank a bounded candidate set with an LLM or reranker model.
4. Expand the top candidates to parent page context where useful.
5. Compress to the final evidence set while keeping page-grounded support.

### Stage 7. Answering

Keep the current typed answering backbone.

Import only these ideas from `RAG-Challenge-2`:

- explicit schema-specific prompting;
- reference validation against retrieved pages;
- comparative question decomposition for selected hard question classes.

Do not turn the whole answering stack into open-ended chain-of-thought generation.
The current project is right to stay extraction-first wherever possible.

## Exact Integration Decisions

### Decision 1. `opendataloader-pdf` is an upstream parser branch, not the canonical format

We take its parsing and sanitation strengths, but the project's canonical downstream format stays ours.

### Decision 2. Current table merge/provenance logic remains authoritative

`RAG-Challenge-2` table serialization is added as enrichment. It does not replace the current `TableBlock` contract.

### Decision 3. Rich parser structure should replace regex heading recovery when available

The current regex heading inference stays only as fallback.

### Decision 4. Retrieval remains local hybrid Qdrant, not per-document FAISS

We can borrow parent-page and reranking patterns without adopting their storage architecture.

### Decision 5. Comparative decomposition becomes a selective legal track

It is not a default path for every question. It is a targeted escalation path.

## Implementation Sequence

### Phase 1. Raw parse sidecar support

Add raw-parse artifact support without touching the current canonical outputs.

Deliverables:

- parser branch metadata;
- raw structural parse sidecars;
- document/page-level parser provenance;
- debug tooling to compare parser branches on the same document.

### Phase 2. Structural normalization

Build the adapter that converts layout-rich nodes into canonical page blocks and heading context.

Deliverables:

- normalized structural blocks;
- header/footer/TOC filtering;
- direct heading-path extraction;
- fallback to current heuristics when structure is missing.

### Phase 3. Unified table pipeline

Add semantic table serialization while preserving current table contracts.

Deliverables:

- raw table HTML/JSON preservation;
- current row-level `TableBlock` pipeline unchanged or strengthened;
- new semantic serialized-table blocks;
- chunk emission for both row-level and semantic table evidence.

### Phase 4. Retrieval upgrade

Wire in:

- candidate reranking;
- parent-page expansion;
- chunk-family-aware retrieval and compression.

### Phase 5. Comparative/decomposition track

Add selected legal decomposition patterns only after the parser and retrieval upgrades land.

## Validation And A/B Plan

The unified stack should be judged on measurable outcomes, not aesthetics.

Primary checks:

- page parse quality on hard legal PDFs;
- heading continuity;
- annex/schedule recovery;
- cross-page table continuity;
- table-answer recall;
- page grounding precision;
- deterministic-answer accuracy;
- unanswerable behavior;
- ingestion runtime and failure rate.

Mandatory A/B comparisons:

1. Current parser baseline vs current parser + raw structural sidecars.
2. Current parser baseline vs `opendataloader-pdf` branch on born-digital/tagged pages.
3. Current table pipeline vs current table pipeline + semantic table serialization.
4. Current retrieval vs retrieval + reranking + parent-page expansion.
5. Current answering vs selective comparative decomposition on suitable legal question slices.

## Net Takeaway

The unified stack should be built around this split of responsibility:

- `opendataloader-pdf`: parser truth, structure, sanitation, layout semantics.
- `RAG-Challenge-2`: table enrichment, parent-page retrieval pattern, reranking pattern, comparative decomposition pattern.
- Current project: canonical grounding contract, legal page provenance, local hybrid retrieval, typed answering, validation and submission correctness.

That is the correct synthesis.

Anything weaker leaves competition upside on the table.
Anything more radical risks throwing away the parts of the current system that are already correct.
