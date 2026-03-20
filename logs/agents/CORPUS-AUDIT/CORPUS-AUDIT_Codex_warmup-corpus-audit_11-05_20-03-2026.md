# [CORPUS-AUDIT] [warmup-corpus-audit]

## Metadata + Exact Request
- Logged at: 20-03-2026 11:05 MSK
- Agent identity: Codex
- Task: CORPUS-AUDIT
- Branch / worktree: `main` / `/home/xeliaray/Projects/Agentic-RAG-Challenge`
- Scope: Audit the locally available challenge document corpus and write a representative report for further project work.
- Exact user request or delegated objective:
  > Рассказать про корпус документов соревнования: все ли документы скачаны, в каком они формате, есть ли сканы, есть ли изображения, из чего состоят документы и какие RAG-проблемы это создает; оформить подробный отчет в `docs/about_challenge`.

## Task Setup
- Context used:
  - `AGENTS.md`
  - `memory_bank/ARCHITECTURE.md`
  - `memory_bank/TASKS.md`
  - `docs/about_challenge/about_challenge.md`
  - local `data/warmup/` artifacts and sync manifest
- Constraints:
  - Do not modify Memory Bank files.
  - Use the local uv environment / project venv.
  - Keep conclusions evidence-based and tied to reproducible artifacts.
- Planned approach:
  - Inspect local phase coverage and manifest state.
  - Run a reproducible PDF audit over the warmup corpus.
  - Write a detailed Markdown report and save the raw audit artifact.

## Implementation Log
1. Inspected project context, challenge docs, sync service, and actual `data/` directories to determine which phases are locally present.
2. Confirmed that only `warmup` is populated locally and that `final` / `dev` are empty except for placeholders.
3. Added `scripts/audit_challenge_corpus.py` to compute archive integrity, phase coverage, question mix, PDF text extractability, images, tables, and document-level summary signals.
4. Ran the audit script against `data/warmup/documents/pdfs` and wrote `docs/about_challenge/artifacts/warmup_corpus_audit.json`.
5. Wrote `docs/about_challenge/about_challenge_CORPUS_AUDIT.md` with measured findings, limitations, and RAG implementation implications.

## Verification
- `./.venv/bin/python scripts/audit_challenge_corpus.py --phase warmup --documents-dir data/warmup/documents/pdfs --archive-path data/warmup/documents/documents.zip --questions-path data/warmup/questions/questions.json --manifest-path data/warmup/manifests/sync_manifest.json --data-root data --output docs/about_challenge/artifacts/warmup_corpus_audit.json`
- `./.venv/bin/python -m py_compile scripts/audit_challenge_corpus.py`
- Manual cross-check of the report against `docs/about_challenge/artifacts/warmup_corpus_audit.json`

## Issues / Resolutions
- `uv run` attempted to resolve build dependencies from the network, which is unavailable in the sandbox.
- Switched to the existing `.venv/bin/python`, which already includes `PyMuPDF`.
- `PyMuPDF` emitted a noisy layout-analysis suggestion during table detection.
- Suppressed stdout/stderr around `page.find_tables()` to keep the audit script clean on reruns.

## Artifacts
- Files touched:
  - `scripts/audit_challenge_corpus.py`
  - `docs/about_challenge/artifacts/warmup_corpus_audit.json`
  - `docs/about_challenge/about_challenge_CORPUS_AUDIT.md`
  - `logs/agents/CORPUS-AUDIT/CORPUS-AUDIT_Codex_warmup-corpus-audit_11-05_20-03-2026.md`
- Reports, plots, logs, or other evidence:
  - `docs/about_challenge/artifacts/warmup_corpus_audit.json`
  - `docs/about_challenge/about_challenge_CORPUS_AUDIT.md`
- Verification artifacts:
  - successful script rerun over warmup corpus
  - successful Python bytecode compilation for the new audit script

## Result / Conclusions (Exact Answer to User)
> Локально полностью скачан только warmup-набор: 30 PDF и 100 вопросов, зафиксированные в `data/warmup/manifests/sync_manifest.json` от 18-03-2026. Полный соревновательный корпус не скачан локально, потому что `data/final/` пуст. На текущем warmup все документы имеют формат PDF, все 590 страниц дают извлекаемый текст, признаки scan-only или OCR-backed scan страниц не обнаружены, а изображения выглядят как мелкие декоративные элементы, а не как носители содержания. Реальные RAG-риски сейчас в длинных юридических документах, таблицах, отсутствии PDF bookmarks, хэшированных именах файлов и связанных судебных актах по одному делу. Подробный отчет сохранен в `docs/about_challenge/about_challenge_CORPUS_AUDIT.md`, а сырой воспроизводимый аудит лежит в `docs/about_challenge/artifacts/warmup_corpus_audit.json`.
