# Review: unified_document_processing_architecture.md

## 1. Обзор архитектурного документа

Документ сильный и хорошо структурированный. Adopt/Adapt/Reject матрица, фазовая последовательность, и разделение ответственности между тремя источниками — все это грамотно. Но есть пробелы.

## 2. Что пропущено или недоучтено из источников

### Из `external/RAG-Challenge-2`

**a) Table serialization в winning config была ОТКЛЮЧЕНА.**
Документ делает LLM table serialization "mandatory". Но победившая конфигурация RAG-Challenge-2 (`max_nst_o3m`) **отключила** serialization — Docling markdown оказался достаточно хорош, а serialized chunks **снижали** signal-to-noise ratio для vector retriever. Документ должен это отметить как risk/caveat: mandatory serialization — это гипотеза, которую нужно подтвердить на legal-домене, а не аксиома.

**b) Broken font / encrypted font detection.**
RAG-Challenge-2 содержит детекцию "broken font" (зашифрованный/обфусцированный текст в PDF), которая триггерит OCR fallback. Текущий pipeline использует `bad_char_ratio` как proxy, но explicit broken-font detection из RAG-Challenge-2 не упомянут в секции parser-side sanitation.

**c) Artifact cleaning (regex glyph removal).**
RAG-Challenge-2 делает post-parse очистку артефактов: удаление glyph-мусора, command substitution patterns. Это другой уровень sanitation, чем описанный в документе (hidden text, off-page text, tiny text). Нужно добавить в Structural Normalization Layer.

**d) Token-aware chunking.**
RAG-Challenge-2 использует ~300 token chunks с 50 token overlap, считая по GPT-4o tokenizer. Документ описывает chunk families, но не специфицирует token-aware sizing. Для legal документов с длинными clause-ами это может быть критично.

**e) Embedding model strategy отсутствует.**
RAG-Challenge-2 использует `text-embedding-3-large` (3072 dim), текущий проект — `Qwen3-Embedding-0.6B`. Документ говорит "keep local hybrid Qdrant" но молчит о том, подходит ли текущая embedding model для обогащенных chunk families (semantic tables, clause chunks). Это архитектурное решение заслуживает хотя бы упоминания.

**f) Question routing по document-level metadata.**
RAG-Challenge-2 извлекает company name из вопроса и маршрутизирует к конкретному report DB. Документ правильно отвергает "company-routed retrieval", но в legal-домене есть аналог: извлечение case ID / statute number / document title из вопроса для pre-filtering. Стоит упомянуть как адаптацию.

### Из `opendataloader-pdf` (external/opendataloader-pdf)

Библиотека изучена. Java-based (veraPDF core) с Python wrapper, Apache 2.0. #1 по benchmark accuracy (0.90 hybrid). Архитектурный документ правильно идентифицирует её ключевые capabilities, но пропускает несколько критичных деталей:

**g) JVM dependency и deployment implications.**
opendataloader-pdf — Java-библиотека (Java 11+). Каждый вызов `convert()` из Python **порождает новый JVM-процесс** через subprocess. Это значит:
- startup overhead на каждый batch;
- нет in-process интеграции с текущим Python pipeline;
- нужно batch-ить все документы в один `convert()` вызов для эффективности.
Архитектурный документ должен учесть это в Phase 2: интеграция — это не просто "вызвать парсер", а JVM-процесс management.

**h) Local mode vs Hybrid mode — качество принципиально разное.**
Это самый важный пропуск. Vendor self-reported benchmarks из README opendataloader-pdf (200 real-world PDFs, **не наши замеры**):

| Mode | Overall | Table TEDS | Speed |
|---|---|---|---|
| Local (Java only) | 0.72 | **0.49** | 0.05s/page |
| Hybrid (+ Docling backend) | **0.90** | **0.93** | 0.43s/page |
| Docling standalone | 0.86 | 0.89 | 0.73s/page |
| PyMuPDF4LLM | 0.57 | 0.40 | 0.09s/page |

**Caveat:** это vendor benchmarks на их dataset-е; на наших legal PDF-ах результаты могут отличаться. Тем не менее, разница между local (0.49 table TEDS) и hybrid (0.93) настолько велика, что её нужно учитывать при планировании. Hybrid mode требует запущенный Docling сервер (FastAPI на localhost:5002). Архитектурный документ говорит "use opendataloader-pdf as structural parser" — но **какой** mode? Документ должен явно указать: **hybrid mode предпочтителен** для legal PDFs с таблицами (что влечёт infra-зависимость от Docling backend), а local-only mode — только как fallback. Точные цифры нужно верифицировать на наших warmup PDFs в Phase 2 PoC.

**i) Cluster table method — не включён по умолчанию.**
Два метода таблиц: `default` (border-based) и `cluster` (border + clustering). По vendor benchmarks cluster даёт значительно лучший результат на таблицах, но **не является default**. Документ должен зафиксировать: `table_method="cluster"` рекомендован в конфиге, с верификацией на наших PDFs.

**j) Output format decision отсутствует.**
opendataloader-pdf выдаёт JSON, Markdown, HTML, Text, Annotated PDF, Tagged PDF. JSON содержит полную структуру с bbox для каждого элемента. Markdown теряет bbox. План "raw structural sidecars" в архитектурном документе должен потреблять **JSON**, не Markdown. Это нужно зафиксировать.

**k) Tagged PDF fast path.**
Для PDF/UA-compliant документов (`use_struct_tree=True`) парсер извлекает структуру напрямую из PDF structure tree — без эвристик, с правильным reading order и семантическими типами (headings, lists, tables). Это самый быстрый и точный путь для born-digital документов с тегами. Архитектурный документ упоминает "tagged-PDF exploitation" но не выделяет это как **отдельный routing path** в Parser Arbitration Layer.

**l) Richer node types чем описано.**
opendataloader-pdf выдаёт: Paragraph, Heading (с уровнями), Caption (привязан к table/image по `linked content id`), Table (с cell-level rowspan/colspan), List (ordered/bulleted/nested с уровнями), Image, Formula (LaTeX), Header/Footer. Особенно важны:
- **Caption linking** — связь caption → table/image. Ценно для table context при serialization.
- **List с nesting и level detection** — критично для legal clause structure (numbered articles, sub-paragraphs).
- **Strikethrough detection** (experimental) — потенциально полезно для legal amendments.

**m) XY-Cut++ reading order — настраиваемый алгоритм.**
Reading order recovery реализован через XY-Cut++ (arXiv:2504.10258) с tunable параметрами: density threshold, gap threshold, beta для cross-layout detection. Для legal документов с multi-column layouts и sidebars может потребоваться calibration. Документ упоминает "reading-order recovery" как feature, но не как tunable system.

**n) Content safety filters перекрывают текущий pipeline.**
opendataloader-pdf фильтрует: hidden text (transparent/zero-size fonts), off-page content, tiny text, hidden OCG layers. Это **тот же набор**, что описан в архитектурном документе как "parser-side sanitation". Но opendataloader-pdf также предлагает PII sanitization (email, phone, credit cards, etc.) — не нужно для challenge, но стоит отметить что content safety уже встроена.

**o) CID-keyed font detection.**
При отсутствии ToUnicode mappings (>30% U+FFFD символов) библиотека логирует WARNING и рекомендует OCR fallback. Это аналог "broken font detection" из RAG-Challenge-2, реализованный другим способом. Полезно для routing decision в Parser Arbitration Layer.

## 3. Что добавить по результатам baseline (самое критичное)

Baseline даёт `total=0.2273` при формуле `(0.7*det + 0.3*asst) * G * T * ttft`. Результат показывает, что **answering quality и grounding precision — главные блокеры**, а не parsing. Документ почти полностью молчит об этих проблемах.

### 3.1. Grounding precision (G=0.570) — главный мультипликативный блокер

**Проблема:** 75/100 ответов содержат лишние страницы, 39/100 пропускают gold pages. 31 из 37 correct answers всё равно теряют score из-за extra pages.

**Что отсутствует в документе:**
- Нет механизма **minimal-evidence page selection** — система отдаёт top-k страниц из retrieval вместо minimal-sufficient набора.
- Нет **title-page / boilerplate suppression** — система регулярно цитирует title pages и соседние страницы вместо answer-bearing pages.
- Нет **empty-retrieval policy для no-answer вопросов** — 5 вопросов с `doc_count:0` получают `G=0.0` потому что система всё равно возвращает непустой retrieval.

**Рекомендация:** Добавить секцию "**10. Page Attribution Precision**" между секциями 7 (Retrieval) и 8 (Answering). Это post-retrieval, pre-answering этап: reranker сузил candidate set, теперь нужно выбрать *minimal complete* page evidence для финального ответа.

### 3.2. Deterministic extraction (det=0.129) — главный value blocker

**Проблема:** 47/70 deterministic answers = null. 29 из них при G >= 0.7. Evidence уже есть, но extractor abstain-ит.

**Что отсутствует в документе:**
- Секция 8 говорит "keep extraction-first typed answering", но не описывает **как** улучшить typed extraction.
- Нет планов по **name/names extraction** (0/15 и 0/5 соответственно).
- Нет анализа **boolean polarity errors** — система переворачивает true/false на cross-case overlap вопросах.
- Нет плана по **threshold tuning** — extractor слишком строго уходит в abstain.

**Рекомендация:** Добавить секцию или подсекцию "**Typed Extraction Upgrade**" в секцию 8. Включить:
- Per-type extraction strategies (boolean, number, name, names, date).
- Explicit name/entity extraction track.
- Confidence threshold calibration вместо binary abstain.
- Polarity/negation handling для boolean.

### 3.3. Free-text grounding fallback слишком агрессивен

**Проблема:** 16 fallback-ов при 5 реальных no-answer вопросах. 11 semantically correct ответов подавлены.

**Что отсутствует:** Документ говорит "keep local validation", но текущий validator *уничтожает* правильные ответы. Нужно добавить в секцию 9: grounding validation должен **деградировать** page attribution, а не **обнулять** ответ.

### 3.4. Cross-case / multi-document reasoning (total=0.0 на 31 вопросе)

**Проблема:** Slice `source_type:cross_case` = 0.0 на 31 вопросе.

**Что в документе:** Секция 8 упоминает "selective comparative decomposition" и даже перечисляет decomposition targets. Но baseline показывает, что cross-case — это **31% всех вопросов**, а не edge case. Фаза 6 (decomposition) стоит последней, но по impact это должно быть раньше — или как минимум параллельно с Phase 5.

### 3.5. Retrieval precision по сегментам

Baseline показывает:
- `case` вопросы: avg retrieved 2.20 pages vs avg gold 0.92 → **over-retrieval в 2.4x**.
- `statute`: avg retrieved 2.23 vs gold 1.20 → **over-retrieval в 1.9x**.
- `cross_case`: avg retrieved 1.94 vs gold 2.35 → **under-retrieval**.

Документ говорит "rerank + parent-page expand", но не адресует **asymmetric retrieval tuning** по question/document type.

## 4. Резюме рекомендаций

### По результатам baseline (score blockers)

| # | Что добавить | Куда | Приоритет |
|---|---|---|---|
| 1 | Секция "Page Attribution Precision" (minimal-evidence selection, title-page suppression, empty-retrieval policy) | Между 7 и 8 | **Критический** — G является мультипликатором |
| 2 | Подсекция "Typed Extraction Upgrade" (per-type strategies, name extraction track, threshold calibration, polarity handling) | В секцию 8 | **Критический** — det=0.129 |
| 3 | Grounding validation degradation policy (degrade pages, не убивать ответ) | В секцию 9 | Высокий |
| 4 | Cross-case decomposition поднять в Phase 5 или параллельно, т.к. это 31% вопросов | В Phased Implementation | Высокий |
| 5 | Asymmetric retrieval tuning по question/document type (case over-retrieves, cross_case under-retrieves) | В секцию 7 | Средний |

### По `external/RAG-Challenge-2`

| # | Что добавить | Куда | Приоритет |
|---|---|---|---|
| 6 | Caveat о table serialization: в winning config была отключена; mandatory — гипотеза для legal домена | В секцию 5 | Средний |
| 7 | Question-level document pre-filtering (case ID / statute number extraction) | В секцию 7 | Средний |
| 8 | Token-aware chunk sizing specification | В секцию 6 | Средний |
| 9 | Embedding model strategy note | В секцию 6 | Низкий |
| 10 | Broken-font detection + artifact regex cleaning | В секции 1 и 3 | Низкий |

### По `opendataloader-pdf`

| # | Что добавить | Куда | Приоритет |
|---|---|---|---|
| 11 | **Hybrid mode предпочтителен** — по vendor benchmarks local-only значительно слабее на таблицах. Указать infra-зависимость от Docling backend, верифицировать на наших PDFs | В секцию 1 (Parser Arbitration) | **Критический** — без этого интеграция рискованна |
| 12 | `table_method="cluster"` рекомендован в конфиге (по vendor benchmarks значительно лучше default border-based) | В секцию 1 | Высокий |
| 13 | Raw parse sidecars должны потреблять **JSON** output (сохраняет bbox), не Markdown | В секцию 2 | Высокий |
| 14 | Tagged PDF path (`use_struct_tree=True`) как отдельный routing в Parser Arbitration Layer | В секцию 1 | Средний |
| 15 | JVM dependency: Java 11+, каждый `convert()` = new JVM process, batch-ить все документы в один вызов | В секцию 1 и Phased Implementation | Средний |
| 16 | XY-Cut++ reading order — tunable алгоритм, может потребовать calibration для legal docs | В секцию 3 | Средний |
| 17 | Caption linking (caption → table/image), list nesting с level detection — использовать для legal clause structure | В секции 3 и 4 | Средний |
| 18 | CID-keyed font detection (>30% U+FFFD) как сигнал для OCR routing | В секцию 1 | Низкий |

## 5. Главные выводы

**Вывод 1 (baseline):** Документ отлично покрывает *инфраструктурную* часть (parsing → normalization → indexing → retrieval). Но baseline показывает, что главные блокеры score лежат в *post-retrieval answering quality*: page selection precision (G=0.570), typed extraction (det=0.129), и grounding validation (11 spurious suppressions). Эти три области почти не затронуты в документе, хотя именно они дадут самый быстрый рост total score.

**Вывод 2 (opendataloader-pdf):** По vendor self-reported benchmarks, local-only mode opendataloader-pdf значительно слабее hybrid mode на таблицах. Документ должен явно зафиксировать: hybrid mode + cluster table method — рекомендованная конфигурация (infra-зависимость от Docling backend server). Точные цифры нужно верифицировать на наших warmup PDFs перед принятием архитектурного решения.

**Вывод 3 (приоритизация фаз):** Текущая фазовая последовательность ставит parsing upgrades (Phases 2-4) перед answering/retrieval upgrades (Phases 5-6). Baseline показывает обратный приоритет: fixing page attribution precision и deterministic extraction даст больший score lift, чем улучшение парсинга, потому что free-text semantics уже сильные (asst=0.987), а парсинг уже работает (0 parse failures на 590 страницах). Рекомендация: выделить параллельный answering-quality track, не блокированный parsing phases.
