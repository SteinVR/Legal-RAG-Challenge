# Task: TASK-003

## 1. Summary

**Title**: Document ingestion pipeline  
**Description**: Parse legal PDFs into canonical page-level corpus with page map, table serialization, and quality control.  
**Status**: Planned

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
- **Dependencies**: TASK-001 (config, corpus download), PaddleOCR-VL-1.5 model

## 3. Implementation Plan



## 4. Working Notes

PaddleOCR-VL-1.5: 0.9B, page-level inference, cross-page table merging, heading recognition.
Table serialization from ERC2: add row/column headers, units, totals, surrounding text context.
Physical 1-based page numbers are critical -- all downstream scoring depends on correct page map.

## 5. Outcome

**Result**: [Pending]  
**Next action**: implement after TASK-001
