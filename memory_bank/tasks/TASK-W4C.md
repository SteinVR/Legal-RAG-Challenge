# Task: TASK-W4C

# About

This task formalizes the ingestion-side structural upgrade from the canonical architecture document. Its purpose is to add a richer parser branch and richer table/structure artifacts without replacing the existing canonical page-grounded corpus contract that the baseline pipeline already depends on.

This task owns the `opendataloader-pdf` branch, raw sidecars, structural normalization details, and benchmark-gated table enrichment. It does not own retrieval tuning, typed answer extraction, or comparative orchestration.

# Specification

## Target behavior

- Add a structural parser branch that complements, rather than replaces, the current parser stack.
- Preserve raw structural truth in sidecars while keeping the current canonical page corpus as downstream SSOT.
- Normalize structural outputs into legal-friendly blocks with better headings, list nesting, caption linkage, and artifact cleaning.
- Preserve raw table structure and support semantic table enrichment behind a benchmark gate.

## Required interfaces and artifacts

- Raw sidecars under `data/{phase}/raw_parse/...` for the current parser and the structural parser branch.
- Required sidecar format: JSON.
- Sidecars must preserve:
  - parser provenance;
  - page geometry;
  - typed nodes;
  - bbox;
  - diagnostics and route decisions;
  - raw table objects and linked context from parser output, with `null` values when the active parser does not provide them.
- Canonical corpus enrichments must remain additive:
  - parser provenance;
  - heading/section path from parser output, with `null` when not detected;
  - source block ids for traceability;
  - block role annotations such as `heading`, `clause`, `annex`, `footnote`, and `table-context`.
- Table enrichment must support:
  - raw HTML/JSON retention;
  - current authoritative row-level table blocks;
  - semantic serialized-table blocks behind a config-level kill switch.

## Development rules and non-goals

- Use `opendataloader-pdf` hybrid mode as the required default path for born-digital and layout-complex pages when the Docling backend is reachable. If the backend is unreachable at parse time, fall back to local-only mode and log a degradation warning.
- Treat local-only mode as fallback, not peer default.
- Use tagged structure-tree extraction as a distinct fast path for PDFs where the parser auto-detects a valid structure tree.
- Batch parser invocations to amortize JVM startup.
- Use `table_method="cluster"` as the required default table method for Wave 4 implementation and parser comparison. Any deviation must be justified by a measured regression on legal PDFs.
- Keep semantic table serialization default-on for experiments, but benchmark-gated for production acceptance.
- Do not revise the canonical corpus into parser-native JSON only.
- Do not move retrieval or answer logic into this task.

## Acceptance criteria

- The project has a documented parser-arbitration contract that distinguishes OCR fallback, tagged fast path, hybrid structural path, and local-only fallback.
- Raw JSON sidecars preserve enough structure for later A/B and debugging.
- Normalization can carry over heading hierarchy, list nesting, caption linkage, and artifact cleaning into canonical outputs.
- Table enrichment preserves all three forms:
  - structural;
  - canonical row-level;
  - semantic serialized.
- Config can disable semantic table chunks cleanly if benchmark results are negative.

## Test and evaluation expectations

- Parser comparison slices must include:
  - tagged PDFs;
  - born-digital legal PDFs;
  - layout-complex pages;
  - table-heavy pages.
- Evaluation must separately compare:
  - hybrid vs local-only;
  - tagged fast path vs non-tagged parsing;
  - current parser baseline vs structural branch;
  - row-level tables vs row-level + semantic serialization.
- Normalization regression checks must cover:
  - heading carry-over;
  - list nesting;
  - caption-linked table context;
  - artifact cleaning.

## Dependency assumptions

- Starts in parallel with `TASK-W4A` and `TASK-W4B`.
- Any new chunk families or schema enrichments consumed by `TASK-W4D` must be frozen before `TASK-W4D` is accepted.

## 1. Summary

**Title**: Structural parser branch, normalization & table enrichment  
**Description**: Add a routed structural parser branch with JSON sidecars, richer normalization, and benchmark-gated semantic table enrichment while preserving the canonical page corpus.  
**Status**: Planned  
**Wave**: Wave 4 -- Baseline Recovery & Structural Upgrade

## 2. Scope

- **In scope**:
  - `opendataloader-pdf` parser branch contract
  - tagged fast path, hybrid-vs-local routing, JVM batching assumptions
  - JSON raw sidecars
  - structural normalization upgrades
  - raw/canonical/semantic table artifact preservation
  - benchmark-gated semantic table serialization
- **Out of scope**:
  - retrieval tuning
  - typed answer extraction
  - cross-case orchestration
- **Dependencies**:
  - none for start
  - downstream schema/chunk consumers: `TASK-W4D`

## 3. Implementation Plan

- Define parser routing and provenance surfaces.
- Add JSON sidecar persistence and debug/trace linkage.
- Implement normalization rules for headings, lists, captions, and parser-visible artifacts.
- Preserve table artifacts in structural, canonical, and semantic forms.
- Run parser and table-enrichment comparisons to decide which enrichments graduate into stable downstream use.

## Source References & Adaptation Map

### Integrate from `external/opendataloader-pdf`

**Python API (direct integration):**
- `external/opendataloader-pdf/python/opendataloader-pdf/src/opendataloader_pdf/__init__.py` — public API: `opendataloader_pdf.convert()`. Call with: `input_path=[list of PDFs]`, `output_dir=sidecar_dir`, `format="json"`, `table_method="cluster"`, `reading_order="xycut"`, `hybrid="docling"` (or `"docling-fast"`), `hybrid_mode="auto"`, `hybrid_fallback=True`.
- `external/opendataloader-pdf/schema.json` — full JSON output schema. Key node types: `paragraph`, `heading` (with `heading level`), `table` (with `rows`, `cells`, `row span`, `column span`, `previous table id`, `next table id`), `list` (with `numbering style`, nested `list items`), `caption` (with `linked content id`), `image`, `header`, `footer`. Every element has `page number` and `bounding box [left, bottom, right, top]`.
- `external/opendataloader-pdf/options.json` — full CLI option reference. Key flags: `use-struct-tree` (tagged PDF fast path), `table-method` (default vs cluster), `hybrid` (off/docling-fast/docling), `content-safety-off` (filter control).
- `external/opendataloader-pdf/python/opendataloader-pdf/src/opendataloader_pdf/wrapper.py` — Python-Java bridge. Each `convert()` call spawns a JVM process. Batch all documents in one invocation.

**Integration pattern:**
1. Call `opendataloader_pdf.convert()` with batch of PDFs → JSON sidecars in `data/{phase}/raw_parse/opendataloader/`.
2. Parse JSON sidecars using schema.json structure → extract typed nodes with bbox, page numbers, heading levels, table structure, caption links.
3. Map parsed nodes into current `CanonicalPageRecord` enrichments (parser provenance, heading path, block roles, source block IDs).

### Adapt from `external/RAG-Challenge-2`

**Table serialization (port and adapt):**
- `external/RAG-Challenge-2/src/tables_serialization.py` `TableSerializer._send_serialization_request()` (lines 106-134) — sends HTML table + context to GPT-4o-mini with structured output. Adapt: replace direct OpenAI API call with current `src/providers/` abstraction.
- `external/RAG-Challenge-2/src/tables_serialization.py` `TableSerialization.system_prompt` (lines 315-319) — "Create set of contextually independent blocks based on table and surrounding text." Reusable prompt pattern.
- `external/RAG-Challenge-2/src/tables_serialization.py` `SerializedInformationBlock` schema (lines 321-337) — output: `subject_core_entity` + `information_block`. Adapt field names to match current `SerializedTableBlock` contract in `src/common/schemas.py`.
- `external/RAG-Challenge-2/src/tables_serialization.py` `_get_table_context()` (lines 50-104) — extracts preceding/following text blocks around a table. Current `src/ingestion/table_serializer.py` already captures `preceding_context` and `following_context` (lines in `detect_tables()`), so the context capture is compatible.

**Block merging and normalization (reference):**
- `external/RAG-Challenge-2/src/parsed_reports_merging.py` `_apply_formatting_rules()` (lines 189-327) — groups tables with headers/footnotes, groups list items, handles block type transitions. Reference for how to merge opendataloader-pdf typed nodes into coherent legal blocks.
- `external/RAG-Challenge-2/src/parsed_reports_merging.py` `_clean_text()` (lines 118-179) — regex-based glyph/artifact cleaning. Adapt patterns for legal document artifacts.

**PDF parsing reference (study, not port):**
- `external/RAG-Challenge-2/src/pdf_parsing.py` — how Docling output is converted to intermediate JSON. Useful as reference for mapping opendataloader-pdf JSON output to internal structures, since both use Docling as backend in hybrid mode.

### Enhance in current `src/`

**Ingestion pipeline (extend, not replace):**
- `src/ingestion/service.py` `CorpusParseService.parse_corpus()` (lines 86-240) — add parser routing: check PDF for structure tree → route to opendataloader-pdf tagged/hybrid/local → fallback to current PyMuPDF parser.
- `src/ingestion/pdf_parser.py` `parse_pdf_document()` (lines 65-161) — current PyMuPDF parser stays as fallback path. Add parallel opendataloader-pdf path.
- `src/ingestion/table_serializer.py` `serialize_document_tables()` (lines 48-78) — current row-level serialization stays authoritative. Add semantic serialized-table blocks alongside, behind kill switch.
- `src/ingestion/corpus_builder.py` `build_canonical_page_records()` (lines 25-53) — extend `CanonicalPageRecord` with parser provenance, heading path, block role annotations.
- `src/common/schemas.py` — add new fields to `CanonicalPageRecord`: `parser_provenance`, `heading_path`, `block_roles`, `source_block_ids`.

### New code

- Parser arbitration router (routes PDFs/pages to tagged, hybrid, local-only, or current parser based on structure tree presence, Docling health, and triage signals).
- JSON sidecar persistence layer (write/read `data/{phase}/raw_parse/` artifacts).
- Structural normalization layer (typed nodes from opendataloader-pdf JSON → legal-friendly blocks with heading hierarchy, list nesting, caption linkage, artifact cleaning).
- Benchmark gate for semantic table serialization (A/B comparison, kill switch).

## 4. Working Notes

This task is not justified by parse failure rate alone. Its value is structural recovery, better legal layout semantics, and stronger table handling.

The task must remain disciplined: richer parser artifacts are useful only if they preserve the current corpus contract and feed later retrieval work without breaking Wave 3 compatibility.

## 5. Outcome

**Result target**: Stable structural parser branch plus additive canonical enrichments and benchmark-gated table enrichment artifacts.  
**Next action**: Freeze any accepted schema/chunk additions for `TASK-W4D` consumption.
