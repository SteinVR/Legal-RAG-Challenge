# Task: TASK-W2C

## 1. Summary

**Title**: Corpus parsing & canonicalization  
**Description**: Parse legal PDFs into canonical page-level corpus with page map, table serialization, and quality control.  
**Status**: Planned
**Wave**: Wave 2 -- Evaluation & Corpus Framing

## 2. Scope

- **In scope**:
  - Native PDF text extraction (PyMuPDF) as fast path
  - PaddleOCR-VL-1.5 as primary document parser (page-level inference)
  - Rule-based page triage (native_clean / scan / suspicious)
  - Page QC scoring (text completeness, legal markers, encoding quality)
  - Table detection and serialization into self-contained retrieval blocks (ERC2 pattern)
  - Cross-page table merging and heading continuation
  - Canonical corpus output: JSONL with page map (doc_id, page_number, text, source_mode, quality, blocks, table_ids)
  - Debug markdown output per document
  - Corpus manifest (doc_id, filename, sha256, page_count, parse_status)
- **Out of scope**: chunking, embedding, indexing
- **Dependencies**: TASK-W1A (config, corpus download), PaddleOCR-VL-1.5 model

## 3. Implementation Plan

- **SSOT rule**:
  - `src/common/schemas.py` является единственным источником истины для ingestion runtime-моделей.
  - `pdf_parser`, `table_serializer`, `corpus_builder` и `service` не вводят свои локальные runtime-контракты для page/document/table state.
- **Unified runtime contract**:
  - `ParsedDocument`: `doc_id`, `filename`, `sha256`, `page_count`, `document_title`, `document_family`, `parse_status`, `failure_reason`, `pages`.
  - `ParsedPage`: `doc_id`, `page_number`, `document_title`, `document_family`, `triage_label`, `source_mode`, `parse_status`, `text`, `native_text`, `ocr_text`, `text_blocks`, `quality_score`, `quality_flags`, `signals`, `tables`, `resolution_notes`.
  - `RawTableRecord`: `table_id`, `page_number`, `rows`, `row_page_numbers`, `has_header`, `header_signature`, `caption`, `footnotes`, `preceding_context`, `following_context`, `raw_markdown`, `raw_html`.
- **Parser resolution flow**:
  - Native parse -> triage -> optional OCR parse -> resolve final text/text_blocks/tables -> resolve provenance -> compute quality -> update first-page metadata -> aggregate document status.
  - `source_mode` вычисляется только в parser по фактическому финальному источнику текста.
  - `hybrid` допустим только если финальный текст реально собран из native и OCR; полная замена suspicious-page OCR результатом считается `ocr`.
- **Table canonicalization**:
  - Первая строка не считается header по умолчанию.
  - `header_signature` сохраняет позиционную ширину таблицы и не схлопывает пустые ячейки.
  - Headerless tables не теряют первую строку данных.
  - Merged table row blocks обязаны сохранять `source_page_number` реальной физической страницы.
- **Artifact completeness**:
  - `parse-corpus` может skip-нуть работу только при полном наборе declared outputs: `corpus.jsonl`, `page_map.json`, `corpus_manifest.json`, `debug/`, `debug/{doc_id}.md` для всех выбранных parsed docs.
  - Отсутствие любого declared output вызывает rebuild без требования `--force`.
- **Delegation plan**:
  - Lead integrator: task file, schemas, parser, OCR contract, provenance semantics.
  - `apm-engineer` A: table serializer and exports.
  - `apm-engineer` B: corpus builder, artifact completeness service path, CLI touchpoints if needed.
  - `apm-sdet`: invariant-based test matrix across parser/serializer/builder/service/CLI.
- **Quality gate**:
  - После реализации обязателен `apm-code-simplifier`, затем verify, затем `apm-code-reviewer`, затем еще один независимый final review на интегрированном результате.


## 4. Working Notes

PaddleOCR-VL-1.5: 0.9B, page-level inference, cross-page table merging, heading recognition.
Table serialization from ERC2: add row/column headers, units, totals, surrounding text context.
Physical 1-based page numbers are critical -- all downstream scoring depends on correct page map.

### Contract Invariants

- Exact physical page attribution is non-negotiable: page records and table row blocks must point to real 1-based PDF pages only.
- `source_mode` must describe the real final text source, not merely which branches were attempted.
- No silent table row loss is allowed during header detection, normalization, or cross-page merge.
- OCR-selected pages may emit canonical table blocks and resolved first-page metadata.
- One OCR engine instance per `parse-corpus` run.
- Skip-path is valid only for a complete artifact set.

### Acceptance Criteria

- W2C runtime uses one schema-level contract across parser, serializer, builder, and service.
- Headerless and blank-leading-header tables serialize without dropping the first data row or shifting columns.
- Multi-page merged tables keep per-row `source_page_number` and never re-emit rows on the wrong page.
- Missing debug outputs trigger rebuild instead of false skip success.
- Full invariant test matrix is green together with targeted and full verification.

## 5. Outcome

**Result**: [Pending]  
**Next action**: execute clean rebuild with unified contracts, invariant-driven tests, and final quality gate
