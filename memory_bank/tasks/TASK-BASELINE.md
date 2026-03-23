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

- Подготовлен детальный отчет в `# TASK-BASELINE Extended`.
- Ключевые агрегаты пересчитаны напрямую из submission, benchmark report, traces и gold references, чтобы исключить report drift.
- Здесь оставлены только highest-signal findings; полный разбор вынесен в `# TASK-BASELINE Extended`.

## 4. Working Notes

- Headline score: `total=0.2273314942`, `det=0.1285714286`, `assistant=0.9866666667`, `grounding=0.5701853251`, `telemetry=1.0`, `ttft_multiplier=1.0328952163`.
- Corpus/index context: `30` docs, `590` pages, `6631` chunks, dense `Qwen/Qwen3-Embedding-0.6B`, sparse BM25.
- Deterministic answering - главный answer-value blocker: `9/70` exact, `47/70` predicted `null`, и `29` из этих null уже имеют `G >= 0.7`.
- Name extraction фактически не работает: `name 0/15`, `names 0/5`.
- Free-text semantics сильные (`28/30` с proxy `assistant_score=1.0`), но page attribution слабый (`free_text G=0.4598`).
- Grounding - главный мультипликативный blocker: `75/100` ответов цитируют лишние страницы, `39/100` пропускают хотя бы одну gold page, и `13` correct answers все еще имеют `G < 0.5`.
- Runtime output структурно чистый: `100/100` valid answers, `0` malformed, `0` validation errors, `telemetry=1.0`.
- Успешный build уже содержит `16` grounding-fallback warnings, что совпадает с наблюдаемым free-text suppression pattern.

# TASK-BASELINE Extended

## Контур прогона

- Фаза: `warmup`
- Канонический scored artifact: `data/warmup/submission_full/`
- Run label: `baseline-full-100q`
- Успешный build window: `2026-03-23 15:45:41Z` - `2026-03-23 15:47:54Z`
- Предшествующая failed attempt: `2026-03-23 15:44:22Z` - `2026-03-23 15:45:04Z`
- Вопросов: `100`
- Gold benchmark: `data/dev/gold/warmup100/dev-gold-warmup100-v1.benchmark.json`

## Изученные артефакты

- `data/warmup/submission_full/submission.json`
- `data/warmup/submission_full/benchmark_report.json`
- `data/warmup/submission_full/trace_manifest.json`
- `data/warmup/submission_full/traces/*.json`
- `logs/project/runtime/warmup/20260323T154422Z_build-submission_45d3ed160f1e44578d5d89c45c484629.jsonl`
- `logs/project/runtime/warmup/20260323T154541Z_build-submission_d9c740faaf9e429c834382fe9363e194.jsonl`
- `logs/project/runtime/warmup/20260323T154807Z_benchmark-summary_0094345610a44cd981d341fb7d571a81.jsonl`
- `data/dev/gold/warmup100/dev-gold-warmup100-v1.assistant_scores.json`
- `data/dev/gold/warmup100/GOLDSET_SPEC.md`
- `data/warmup/corpus/corpus_manifest.json`
- `data/warmup/index/index_manifest.json`
- `data/warmup/manifests/sync_manifest.json`
- `data/warmup/questions/questions.json`
- `configs/baseline/v001/config.yaml`
- `src/evaluation/scorer.py`

## Executive Summary

Первый полный warmup baseline является валидным и воспроизводимым 100-question run, но его score упирается не в схему и не в latency, а в deterministic extraction и page-level grounding. Общий результат составляет `0.2273314942` при `deterministic=0.1285714286`, `assistant=0.9866666667`, `grounding=0.5701853251`, `telemetry=1.0` и `ttft_multiplier=1.0328952163`.

Ключевой паттерн асимметричен:

- Free-text answering уже достаточно силен по benchmark contract: `28/30` free-text ответов получили proxy `assistant_score=1.0`.
- Основной провал по value-accuracy находится в deterministic answering: точных попаданий только `9/70`.
- Главный мультипликативный блокер score - grounding: `75/100` ответов содержат лишние страницы, `39/100` пропускают хотя бы одну gold page, и `13` benchmark-scored correct ответов все равно оказываются ниже `G=0.5`.

Это критично, потому что `total_score = (0.7 * deterministic + 0.3 * assistant) * grounding * telemetry * ttft`. При текущем состоянии именно grounding precision и deterministic extraction дадут самый быстрый рост total score.

## Контекст системы

- Размер корпуса: `30` документов, `590` страниц, `0` parse failures
- Размер индекса: `6631` chunks
- Dense encoder: `Qwen/Qwen3-Embedding-0.6B`
- Dense backend: `sentence_transformers`, normalized embeddings, local-only
- Sparse encoder: BM25 Okapi (`k1=1.5`, `b=0.75`, vocab `7681`)
- Chunk levels: `page`, `section`, `clause`, `microchunk`, `table`
- Carry-over heading context: включен
- Free-text model в traces: `gpt-5.4-mini`
- Deterministic route в traces: `deterministic-extractor`

## Декомпозиция score

### Общие метрики

| Метрика | Значение |
| --- | ---: |
| Total score | 0.2273 |
| Deterministic | 0.1286 |
| Assistant | 0.9867 |
| Grounding | 0.5702 |
| Telemetry | 1.0000 |
| TTFT multiplier | 1.0329 |
| Deterministic questions | 70 |
| Free-text questions | 30 |

### Срезы по answer type

| Срез | N | Total | Answer metric | Grounding |
| --- | ---: | ---: | ---: | ---: |
| `boolean` | 32 | 0.0615 | det `0.1250` | 0.6725 |
| `date` | 1 | 0.0000 | det `0.0000` | 0.0000 |
| `free_text` | 30 | 0.1362 | asst `0.9867` | 0.4598 |
| `name` | 15 | 0.0000 | det `0.0000` | 0.3269 |
| `names` | 5 | 0.0000 | det `0.0000` | 0.9030 |
| `number` | 17 | 0.1557 | det `0.2941` | 0.7227 |

### Наиболее показательные slice-ы

| Срез | N | Total | Комментарий |
| --- | ---: | ---: | --- |
| `source_type:statute` | 44 | 0.3802 | Сильнейший сегмент; единственный, где deterministic уже заметно помогает |
| `difficulty:easy` | 70 | 0.2573 | Текущая система живет в основном за счет easy statute и single-page кейсов |
| `source_type:cross_case` | 31 | 0.0000 | Полный провал на cross-document deterministic reasoning |
| `answer_type:name` | 15 | 0.0000 | Name extraction фактически не работает |
| `answer_type:names` | 5 | 0.0000 | Multi-name extraction фактически не работает |
| `doc_count:0` | 5 | 0.0000 | No-answer вопросы теряют grounding при непустом retrieval |

## Детальные выводы

### 1. Deterministic answering слишком консервативен и типово недоопределен

- Точных deterministic hits: `9/70`
- Предсказанных `null`: `47`
- Gold no-answer deterministic вопросов: `0`
- `null` ответов при `G >= 0.7`: `29`
- `null` ответов при идеальном grounding `G = 1.0`: `10`

Это означает, что retrieval во многих вопросах уже достаточно хорош, чтобы выдать ответ, но deterministic layer все равно уходит в abstain.

#### По deterministic answer type

| Type | N | Predicted null | Exact hits | Average det |
| --- | ---: | ---: | ---: | ---: |
| `boolean` | 32 | 20 | 4 | 0.1250 |
| `date` | 1 | 1 | 0 | 0.0000 |
| `name` | 15 | 10 | 0 | 0.0000 |
| `names` | 5 | 5 | 0 | 0.0000 |
| `number` | 17 | 11 | 5 | 0.2941 |

#### Основные deterministic failure clusters

- `name` и `names` фактически сломаны. Совокупный hit rate: `0/20`.
- `boolean` часто переворачивается в `true` на cross-case overlap вопросах, где gold равен `false`.
- `number` умеет работать на очевидных statute literals, но все равно abstain-ит в `11/17` случаях.
- У `names` grounding уже высокий (`0.9030`), но exact hits нет вообще. Это сильный сигнал, что падает не retrieval, а answer synthesis.

#### Репрезентативные wrong non-null deterministic ошибки

| Question ID | Type | Gold | Predicted | G | Failure mode |
| --- | --- | --- | --- | ---: | --- |
| `a8813f8f...` | `name` | `CFI 010/2024` | `Default Costs Certificate` | 0.5000 | Извлечен document artifact вместо case id |
| `359f1c31...` | `name` | `Onora` | `IN THE DUBAI... BETWEEN OHTLI` | 1.0000 | Span extraction захватил title-page boilerplate |
| `ff1b3575...` | `number` | `3` | `2004` | 0.0000 | Вместо law number выбран год с title page |
| `802d12a6...` | `boolean` | `false` | `true` | 1.0000 | Ошибка polarity при точном page retrieval |
| `0149374f...` | `boolean` | `true` | `false` | 0.0000 | Инверсия statute answer плюс grounding miss |

#### Репрезентативные null при уже достаточном grounding

| Question ID | Type | Gold | G | Почему важно |
| --- | --- | --- | ---: | --- |
| `358bf0ca...` | `boolean` | `false` | 1.0000 | Cross-case overlap вопрос имел идеальное evidence, но ответ не был выдан |
| `39890efe...` | `boolean` | `false` | 1.0000 | Та же проблема на другом overlap вопросе |
| `5d271fce...` | `number` | `2` | 0.8788 | Статутный literal найден, но extractor ушел в abstain |
| `2fc105ec...` | `number` | `6` | 0.8788 | Numeric literal найден, но не выдан |
| `4fa07316...` | `name` | `SCT 169/2025` | 0.9355 | Evidence для cross-case comparison уже есть, но нет canonical case-id extraction |

### 2. Free-text semantics сильные, но grounding precision слабый

- Free-text вопросов: `30`
- Средний proxy assistant score: `0.9867`
- Ответов с `assistant_score=1.0`: `28/30`
- Predicted fallback answers: `16`
- Gold no-answer cases: `5`
- Spurious fallback suppression на answerable free-text вопросах: `11`

Это сильнейшая часть системы по semantic output, но текущий grounding path либо подавляет полезный ответ, либо резко режет score из-за неверных страниц.

Важно: в `GOLDSET_SPEC.md` прямо сказано, что `assistant_scores` - это review-time proxy scores, а не универсальные gold labels для любых будущих submission. Для этого отчета они все равно релевантны, потому что анализируется тот же локальный benchmark contract, что использует `benchmark_report.json`.

#### Два разных free-text failure mode

1. Семантически приемлемый ответ, но неверные страницы
- Пример: `fa672c84...` предсказывает правильный outcome для `CFI 016/2025` в сжатом виде, получает `assistant=1.0`, но имеет `G=0.0`, потому что trace ссылается не на ту страницу.

2. Grounding-validation fallback подавляет answerable вопросы
- Пример: `ad7357a7...` и `eeffebf4...` выдают canonical unanswerable fallback, хотя gold answer в корпусе есть.

#### Free-text вопросы с sub-perfect proxy score

| Question ID | Gold summary | Predicted summary | Assistant | G |
| --- | --- | --- | ---: | ---: |
| `b982f3b3...` | dismissal плюс `USD 155,879.50` costs | dismissal плюс generic costs wording | 0.8 | 0.8788 |
| `be35b591...` | детальный outcome в `ARB 034/2025` | canonical fallback | 0.8 | 0.0000 |

### 3. Grounding precision - главный мультипликативный blocker

- Вопросов с лишними страницами: `75/100`
- Вопросов с пропущенными gold pages: `39/100`
- `extra_only`: `43`
- `missing_only`: `7`
- `both`: `32`
- `neither`: `18`
- Вопросов с `grounding_score = 0`: `29`
- Вопросов с `grounding_score < 0.5`: `35`

Доминирующая grounding-проблема - именно precision, а не только recall.

#### Почему это напрямую бьет по score

- Benchmark-scored correct answers overall: `37`
- Correct answers с extra pages: `31`
- Correct answers с missing pages: `10`
- Correct answers с `G < 0.5`: `13`

То есть система уже умеет порождать полезный content, но page attribution стирает значительную часть этого выигрыша.

#### Grounding pattern по ключевым сегментам

| Segment | Avg retrieved pages | Avg gold pages | Missing | Extra | Avg G |
| --- | ---: | ---: | ---: | ---: | ---: |
| `free_text` | 2.50 | 1.17 | 10 | 29 | 0.4598 |
| `name` | 1.87 | 1.80 | 11 | 12 | 0.3269 |
| `number` | 2.12 | 1.00 | 3 | 14 | 0.7227 |
| `case` | 2.20 | 0.92 | 10 | 22 | 0.3974 |
| `cross_case` | 1.94 | 2.35 | 21 | 16 | 0.5018 |
| `statute` | 2.23 | 1.20 | 8 | 37 | 0.7165 |

#### Ключевая интерпретация

- `case` вопросы часто answerable, но система цитирует title pages или соседние страницы вместо decisive order/conclusion page.
- `cross_case` вопросы одновременно страдают от неполного evidence и слабой synthesis-логики.
- Slice `doc_count:0` получает `0.0`, потому что gold retrieval пустой для no-answer вопросов, а система все равно приносит непустой retrieval и тем самым обнуляет `G`.

### 4. Runtime, validation и output shape не являются главным ограничением

- Validation status: `valid=true`
- Evaluated answers: `100`
- Malformed answers: `0`
- Validation errors: `0`
- Validation warnings: `0`
- Telemetry factor: `1.0`

TTFT не бесплатен, но он не является тем, что сейчас держит baseline:

| TTFT stat | Value |
| --- | ---: |
| Min | 429.4 ms |
| P50 | 780.3 ms |
| P90 | 1839.4 ms |
| P95 | 2556.1 ms |
| Max | 16017.9 ms |
| Mean | 1321.9 ms |

Распределение:

- `< 1s`: `66`
- `1s-2s`: `25`
- `2s-3s`: `4`
- `> 3s`: `5`

Средний TTFT multiplier остается положительным (`1.0329`), поэтому latency optimization - это вторичный трек после answering и grounding.

### 5. Runtime evidence из логов

Runtime logs показывают две build attempt на `2026-03-23`:

- Первая попытка завершилась ошибкой после `5` предупреждений `build_submission.question.grounding_fallback` и закончилась `command.error`.
- Вторая попытка успешно завершилась и зафиксировала `16` предупреждений `build_submission.question.grounding_fallback` перед `build_submission.complete`.

Это важно, потому что финальный scored artifact не является zero-warning path: даже успешный run уже содержит повторяющееся подавление ответов через grounding validation, и это напрямую видно в распределении итоговых answer.

## Приоритетные next actions

### 1. Сначала исправить page attribution precision

Evidence:

- `75/100` вопросов имеют extra pages
- `43` из них - extra-only failures
- `31/37` correct answers все еще содержат лишние страницы
- У free-text уже `assistant=0.9867`, но это перемножается на `G=0.4598`

Вывод:

- Нужно ужесточить выбор `retrieved_chunk_pages` до minimal-complete evidence, а не отдавать накопительный top-k.
- Нужно предпочитать answer-bearing terminal pages, а не title-page spillover.

### 2. Ослабить deterministic abstention и перейти к typed extraction

Evidence:

- `47/70` deterministic answers равны `null`
- `29` из этих null уже имеют `G >= 0.7`
- `10` имеют идеальный grounding и все равно не дают answer

Вывод:

- Во многих deterministic кейсах retrieval уже достаточен.
- Главный gap находится в typed value selection, polarity handling и thresholding.

### 3. Сделать отдельный `name` / `names` extraction track

Evidence:

- `name`: `0/15`
- `names`: `0/5`
- У `names` average grounding `0.9030` при нуле exact hits

Вывод:

- Пайплайн часто уже попадает в правильное evidence, но не умеет собрать canonical entity answer.
- Это отдельная задача, а не побочный эффект общего extractor tuning.

### 4. Ослабить или переработать free-text grounding fallback

Evidence:

- `16` predicted fallbacks против `5` реальных no-answer вопросов
- `11` spurious suppression на answerable free-text вопросах

Вывод:

- Текущий validator слишком жестко обнуляет полезный ответ из-за imperfect grounding.
- Free-text path должен деградировать page attribution, а не сразу сваливаться в canonical no-answer.

### 5. Выделить cross-case reasoning в отдельную retrieval-and-answering задачу

Evidence:

- `source_type:cross_case total=0.0`
- В этом slice `31` вопрос
- Регулярно наблюдаются boolean polarity errors и провалы в case-id extraction

Вывод:

- Cross-case вопросы требуют явной multi-document comparison logic, а не только generic hybrid retrieval.

## Bottom Line

Этот baseline уже operational и обещающий по free-text semantics, но как answering system он пока не конкурентоспособен. Score удерживают две системные проблемы:

1. deterministic extraction часто не срабатывает даже тогда, когда evidence уже достаточно;
2. grounding precision настолько слабый, что мультипликативно стирает otherwise good answers.

Кратчайший путь к заметному росту score:

1. page attribution precision;
2. deterministic extractor unfreezing;
3. dedicated name extraction;
4. free-text grounding validator tuning.

