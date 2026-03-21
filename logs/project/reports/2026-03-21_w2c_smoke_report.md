# 2026-03-21 - Test Execution Report: W2C Smoke Validation
**Tester:** Codex
**Trigger:** Manual request: "Выполни smoke тестирование на 10 документах, проверь, что все работает как нужно."

## Executive Summary
- **Overall Status:** 🟢 PASS with dataset caveat
- **Total Tests:** 4
- **Passed:** 4 | **Failed:** 0 | **Skipped:** 0
- **Code Coverage:** N/A for smoke execution

## Failure Analysis (The "Fix List")
> No smoke failures observed.

## Test Scope Breakdown
### Unit Level
- Not part of this run. Existing unit/integration coverage was not re-executed here.

### Integration Level
- Ran `parse-corpus --dry-run` on an isolated temp data root with a 10-document subset symlinked from `data/warmup/documents/pdfs`.
- Ran `parse-corpus` on the same 10-document subset and verified corpus artifacts were written successfully.
- Re-ran the same 10-document subset without `--force` and confirmed the skip fast-path activated on a complete artifact set.
- Validated artifact consistency across `corpus.jsonl`, `page_map.json`, `corpus_manifest.json`, and `debug/*.md`.

### E2E Level (if applicable)
- Ran a full warmup parse of all 30 available PDFs in an isolated temp data root to understand real corpus coverage and verify that the 10-document smoke did not hide systemic issues.

## Risks & Recommendations
- **Risk:** The available warmup corpus did not exercise `source_mode=ocr` or `source_mode=hybrid`. Across all 30 PDFs, all 590 parsed pages resolved to `native`.
- **Risk:** The only non-clean cases in the warmup corpus are 5 `suspicious` pages that resolved to `native/degraded`; real OCR provenance cannot be smoke-validated against this dataset alone.
- **Recommendation:** Add or retain a dedicated scanned/OCR fixture pack for smoke/e2e validation so OCR routing, provenance, and table extraction are exercised on every release.

## Instruction for Developer / Architect (if neccecary)
- **Observation:** The real warmup dataset currently validates native parsing, table serialization, artifact completeness, and skip behavior well, but it is not sufficient as a release smoke for OCR-specific guarantees.

## Artifacts
- Temp root for 10-document smoke: `/tmp/w2c-smoke-rBX8oG`
- Temp root for full warmup sanity run: `/tmp/w2c-smoke-all-EpamVm`
- Full-run outputs inspected:
  - `/tmp/w2c-smoke-rBX8oG/warmup/corpus/corpus.jsonl`
  - `/tmp/w2c-smoke-rBX8oG/warmup/corpus/page_map.json`
  - `/tmp/w2c-smoke-rBX8oG/warmup/corpus/corpus_manifest.json`
  - `/tmp/w2c-smoke-rBX8oG/warmup/corpus/debug/`

## Observed Results
- 10-document smoke subset:
  - `parsed_document_count=10`
  - `parsed_page_count=276`
  - `failed_document_count=0`
  - manifest/page_map/corpus/debug doc sets matched the selected subset
  - `source_modes={"native": 276}`
  - `parse_statuses={"parsed": 275, "degraded": 1}`
  - `triage={"native_clean": 275, "suspicious": 1}`
  - `empty_text_page_count=0`
  - `pages_with_no_blocks_count=0`
  - `table_block_count=426`
  - `table_id_mismatch_count=0`
  - `page_count_mismatch_count=0`
- Repeat run on the same subset:
  - `skipped_paths` returned for all corpus artifacts
- Full 30-document warmup sanity run:
  - `document_count=30`
  - `failed_document_count=0`
  - `page_count=590`
  - `debug_file_count=30`
  - `source_modes={"native": 590}`
  - `parse_statuses={"parsed": 585, "degraded": 5}`
  - `triage={"native_clean": 585, "suspicious": 5}`
  - `empty_text_page_count=0`
  - `pages_with_no_blocks_count=0`
  - `table_id_mismatch_count=0`
