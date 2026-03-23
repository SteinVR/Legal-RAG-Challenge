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

## 4. Working Notes

This task is not justified by parse failure rate alone. Its value is structural recovery, better legal layout semantics, and stronger table handling.

The task must remain disciplined: richer parser artifacts are useful only if they preserve the current corpus contract and feed later retrieval work without breaking Wave 3 compatibility.

## 5. Outcome

**Result target**: Stable structural parser branch plus additive canonical enrichments and benchmark-gated table enrichment artifacts.  
**Next action**: Freeze any accepted schema/chunk additions for `TASK-W4D` consumption.
