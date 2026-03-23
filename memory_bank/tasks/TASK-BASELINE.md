# Task: TASK-BASELINE

## 1. Summary

**Title**: Первый postmortem warmup100 baseline  
**Description**: Детально разобрать первый полный 100-question gold benchmark run по score outputs, traces, runtime logs, manifests и answer-level behavior.  
**Status**: Done  
**Wave**: Post-Baseline Analysis

## 2. Scope

- **In scope**:
  - `data/warmup/submission_full/` как scored artifact set
  - `logs/project/runtime/warmup/*.jsonl` как runtime evidence
  - warmup corpus/index manifests и активный baseline config
  - gold benchmark metadata и proxy assistant-score contract
- **Out of scope**:
  - code changes
  - config tuning
  - rerunning the pipeline
- **Dependencies**: успешный warmup100 submission и локальный gold benchmark package

## 3. Implementation Plan

- Подготовлен детальный отчет в `logs/project/reports/TASK-BASELINE.md`.
- Ключевые агрегаты пересчитаны напрямую из submission, benchmark report, traces и gold references, чтобы исключить report drift.
- Здесь оставлены только highest-signal findings; полный разбор вынесен в `logs/project/reports/`.

## 4. Working Notes

- Headline score: `total=0.2273314942`, `det=0.1285714286`, `assistant=0.9866666667`, `grounding=0.5701853251`, `telemetry=1.0`, `ttft_multiplier=1.0328952163`.
- Corpus/index context: `30` docs, `590` pages, `6631` chunks, dense `Qwen/Qwen3-Embedding-0.6B`, sparse BM25.
- Deterministic answering - главный answer-value blocker: `9/70` exact, `47/70` predicted `null`, и `29` из этих null уже имеют `G >= 0.7`.
- Name extraction фактически не работает: `name 0/15`, `names 0/5`.
- Free-text semantics сильные (`28/30` с proxy `assistant_score=1.0`), но page attribution слабый (`free_text G=0.4598`).
- Grounding - главный мультипликативный blocker: `75/100` ответов цитируют лишние страницы, `39/100` пропускают хотя бы одну gold page, и `13` correct answers все еще имеют `G < 0.5`.
- Runtime output структурно чистый: `100/100` valid answers, `0` malformed, `0` validation errors, `telemetry=1.0`.
- Успешный build уже содержит `16` grounding-fallback warnings, что совпадает с наблюдаемым free-text suppression pattern.

## 5. Outcome

**Result**: Completed on `2026-03-23`; baseline postmortem зафиксирован в `logs/project/reports/TASK-BASELINE.md`.  
**Next action**: Использовать отчет для `TRACK-GROUNDING`, `TRACK-NAME-EXTRACT`, `TRACK-DET-EXTRACT` и `TRACK-FT-GROUNDING` именно в таком порядке.
