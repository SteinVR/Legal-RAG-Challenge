# [TASK-W2C] [w2c-smoke-validation]

## Metadata + Exact Request
- Logged at: 21-03-2026 10:03
- Agent identity: Codex
- Task: TASK-W2C
- Branch / worktree: `main` / `/home/xeliaray/Projects/Agentic-RAG-Challenge`
- Scope: Run smoke validation on 10 documents and confirm W2C corpus parsing behaves correctly on real warmup PDFs.
- Exact user request or delegated objective:
  > Выполни smoke тестирование на 10 документах, проверь, что все работает как нужно.

## Task Setup
- Context used:
  - `src/main.py`
  - `src/ingestion/service.py`
  - `src/ingestion/corpus_builder.py`
  - `src/common/schemas.py`
  - `data/warmup/documents/pdfs`
- Constraints:
  - Do not update Memory Bank.
  - Use the existing `.venv`.
  - Avoid polluting repo corpus artifacts if possible.
- Planned approach:
  - Resolve the real CLI and PDF paths.
  - Run smoke on 10 PDFs in an isolated temp data root.
  - Verify artifact completeness and skip-path behavior.
  - Expand to a full warmup sanity run only if the initial 10-document sample proves non-representative.

## Implementation Log
1. Confirmed the `parse-corpus` CLI, artifact paths, and real warmup PDF location under `data/warmup/documents/pdfs`.
2. Created an isolated temp data root at `/tmp/w2c-smoke-rBX8oG` with a symlinked `warmup/documents/pdfs` directory pointing to the real PDF set.
3. Ran `parse-corpus --dry-run` on a 10-document subset and confirmed planned output paths under the temp root.
4. Ran `parse-corpus` on the same 10-document subset; result was `parsed_document_count=10`, `parsed_page_count=276`, `failed_document_count=0`.
5. Verified `corpus.jsonl`, `page_map.json`, `corpus_manifest.json`, and `debug/*.md` against the selected document IDs; found no missing debug files, no empty text pages, no pages with zero blocks, and no `table_ids` mismatches.
6. Re-ran the same 10-document subset without `--force` and confirmed the service skipped all output artifacts via the fast-path.
7. Because the first 10 documents did not exercise OCR routing, ran a full warmup parse in a second temp root at `/tmp/w2c-smoke-all-EpamVm` to identify real corpus coverage boundaries.
8. Observed that all 30 warmup PDFs still resolve to `source_mode=native`; the full set contains 5 `suspicious/degraded` pages but no actual OCR-selected pages.

## Verification
- Commands run:
  - `COMPETITION_DATA_ROOT=/tmp/w2c-smoke-rBX8oG .venv/bin/python -m src.main parse-corpus --dry-run --doc-id ...`
  - `COMPETITION_DATA_ROOT=/tmp/w2c-smoke-rBX8oG .venv/bin/python -m src.main parse-corpus --doc-id ...`
  - repeat of the same subset run to confirm skip-path
  - `COMPETITION_DATA_ROOT=/tmp/w2c-smoke-all-EpamVm .venv/bin/python -m src.main parse-corpus`
- Result:
  - 10-document smoke subset: pass
  - repeat-run skip behavior: pass
  - full warmup sanity run: pass
  - no failed documents in either run

## Issues / Resolutions
- Issue: The initial 10-document subset did not exercise OCR provenance or OCR table extraction.
- How it was resolved or what remains open:
  - Resolved coverage ambiguity by running a full 30-document warmup sanity parse.
  - Remaining open: the currently available warmup PDFs do not provide a real `source_mode=ocr` or `source_mode=hybrid` smoke case, so OCR-specific behavior still depends on dedicated fixtures/tests rather than this dataset.

## Artifacts
- Files touched:
  - `/home/xeliaray/Projects/Agentic-RAG-Challenge/logs/project/reports/2026-03-21_w2c_smoke_report.md`
  - `/home/xeliaray/Projects/Agentic-RAG-Challenge/logs/agents/TASK-W2C/TASK-W2C_Codex_w2c-smoke-validation_10-03_21-03-2026.md`
- Reports, plots, logs, or other evidence:
  - `/tmp/w2c-smoke-rBX8oG/warmup/corpus/`
  - `/tmp/w2c-smoke-all-EpamVm/warmup/corpus/`
  - `/home/xeliaray/Projects/Agentic-RAG-Challenge/logs/project/reports/2026-03-21_w2c_smoke_report.md`
- Verification artifacts:
  - subset run output: `parsed_document_count=10`, `parsed_page_count=276`, `failed_document_count=0`
  - full run output: `parsed_document_count=30`, `parsed_page_count=590`, `failed_document_count=0`

## Result / Conclusions (Exact Answer to User)
> Smoke на 10 документах прошел успешно: subset parse собрал все артефакты, повторный запуск корректно ушел в skip-path, пустых страниц и битых page/table связок не обнаружено. Дополнительно я прогнал весь warmup набор из 30 PDF и подтвердил, что пайплайн стабилен на реальных входах, но сам датасет не содержит OCR-selected страниц, поэтому OCR-specific smoke этим корпусом не покрывается.
