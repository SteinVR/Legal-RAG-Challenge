# Часть I. Baseline Roadmap

## 1. Целевое назначение baseline

Baseline должен быть не минимальным, а **наиболее надёжным, воспроизводимым и конкурентоспособным** решением, которое:

- корректно проходит формат и telemetry validation
- даёт высокий grounding за счёт strong recall на candidate retrieval и жёсткого evidence compression перед submission;
- устойчиво работает на heterogeneous legal PDFs;
- не зависит от исследовательских гипотез, которые могут не окупиться до финальных сабмитов.


## 2. Базовый технический стек

**Документный слой.**  
Primary strategy: native PDF text extraction first; rule-based page triage; OCR fallback only для scan/suspicious pages; canonical structured intermediate format; table serialization в самостоятельные retrieval blocks. Для OCR в baseline рекомендуется использовать **PaddleOCR-VL-1.5** как основной fallback-парсер: модель официально позиционируется как 0.9B document parser, поддерживает page-level parsing через официальный inference path, automatic cross-page table merging и cross-page heading recognition, что хорошо совпадает с юридическими PDF и задачей page-grounded retrieval. ([Hugging Face](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.5?utm_source=chatgpt.com "PaddlePaddle/PaddleOCR-VL-1.5 · Hugging Face"))

**Retrieval слой.**  
Primary stack: lexical retrieval + dense retrieval + reranking + parent-page lifting + support-page compression. В baseline рекомендуется использовать **Qwen3-Embedding-0.6B** как основной dense retriever и **Qwen3-Reranker-0.6B** как основной reranker, поскольку серия официально даёт согласованную линейку embedding/reranking-моделей размера 0.6B, 32K context и instruction-aware режим, что удобно для единого retrieval stack без лишней интеграционной сложности. Parent retrieval и page-reference validation переносятся из победного решения ERC2 как обязательные паттерны baseline. ([GitHub](https://github.com/QwenLM/Qwen3-Embedding?utm_source=chatgpt.com "GitHub - QwenLM/Qwen3-Embedding"))

**Answering слой.**  
Primary strategy: typed solvers для `number / boolean / name / names / date / null`; короткий grounded generator только для `free_text` и действительно сложных кейсов; structured outputs везде, где это возможно. Поскольку final score опирается на `(0.7 * S_det + 0.3 * S_asst) * G * T * F`, а `free_text` ограничен 280 символами, baseline должен опираться прежде всего на retrieval quality, exact extraction, page attribution и null policy, а не на всеобщую агентность.

**Инфраструктурный слой.**  
Baseline обязан включать versioned configs, trace logging, consistency testing, локальный evaluator, telemetry validator и submission packager. Идея versioned evolution configs и trace-oriented debugging берётся из решений ERC3 и адаптируется под legal RAG как управляемый контур изменений. ([GitHub](https://github.com/IlyaRice/Enterprise-RAG-Challenge-3-AI-Agents "GitHub - IlyaRice/Enterprise-RAG-Challenge-3-AI-Agents: Implementation of my AI agent system for ERC 3: https://erc.timetoact-group.at · GitHub"))

---

## Stage B0. Управление проектом, версиями и артефактами

**Цель.**  
Создать стабильный каркас проекта, исключающий хаотические изменения и потерю управляемости.

**Состав работ.**

1. Утвердить monorepo-структуру: `ingestion/`, `ocr/`, `serialization/`, `indexing/`, `retrieval/`, `answering/`, `evaluation/`, `submission/`, `configs/`, `experiments/`.
2. Ввести versioned config system:
    - `configs/baseline/v001/...`
    - `configs/experiments/eXXX/...`
    - отдельные policy-файлы для OCR routing, chunking, retrieval, page selection, null policy, free-text style.
    
3. Ввести единый run manifest:
    - config version;
    - corpus phase;
    - model backends;
    - thresholds;
    - hashes generated artifacts.
        
4. Ввести обязательный trace ID на каждый прогон и на каждый вопрос.
    
5. Разделить артефакты на:
    - reproducible data artifacts;
    - debug artifacts;
    - submission artifacts.

**Выходы этапа.**

- Зафиксированная структура репозитория.
- Версионируемая конфигурационная система.
- Единый формат trace/log metadata.
- Политика изменения baseline: baseline-ветка и experiment-ветки.

**Критерий завершения.**

- Любой запуск pipeline может быть однозначно воспроизведён по config version и run manifest. ([GitHub](https://github.com/maddness/erc3-agents "GitHub - maddness/erc3-agents: Sample agents for Enterprise RAG Challenge 3: AI Agents in Action · GitHub"))

---

## Stage B1. Контракт соревнования, local evaluator и validator

**Цель.**  
Реализовать локальный контур валидации, полностью повторяющий критичные правила challenge.

**Состав работ.**

1. Реализовать parser схемы `submission.json`.
2. Реализовать строгий validator для:
    - `question_id`;
    - `answer_type`;
    - JSON-типов ответов;
    - `doc_id`;
    - `page_numbers` как physical 1-based PDF pages;
    - `ttft_ms <= total_time_ms`;
    - non-negative usage/timing.
        
3. Реализовать local scorer для:
    - `number` (±1%);
    - `boolean` exact;
    - `name` normalized exact match;
    - `names` Jaccard;
    - `date` exact ISO 8601;
    - `null` policy;
    - grounding по F-beta с β=2.5;
    - telemetry factor;
    - TTFT factor.
        
4. Реализовать dev free-text evaluator как proxy judge:
    - rubric-based manual review mode;
    - pairwise comparison mode;
    - optional LLM-assist mode для ранжирования вариантов.

5. Зафиксировать ambiguity policy для unanswerable retrieval:
    - в документации есть конфликт между требованием `retrieved_chunk_pages = []` для unanswerable и правилом telemetry validation про non-empty retrieval;
    - baseline должен явно хранить это место как unresolved rule и поддерживать переключаемую policy через config.


**Выходы этапа.**
- `local_score.py`
- `submission_validator.py`
- `telemetry_validator.py`
- `free_text_review_template.md`
- `rules/ambiguities.md`

**Критерий завершения.**

- На любом локальном submission validator даёт детализированный отчёт по формату, telemetry и scoring-компонентам.

---

## Stage B2. Корпус, phase isolation и dev benchmark

**Цель.**  
Изолировать warm-up и final corpora, организовать reproducible data pipeline и создать локальный gold/silver set для разработки.

**Состав работ.**

1. Реализовать phase-aware corpus manager:
    - отдельные директории для warm-up и final;
    - отдельные индексы;
    - запрет на смешение фаз.
2. Зафиксировать corpus manifest:
    - `doc_id`;
    - filename;
    - sha256/size;
    - page count;
    - parse status.
3. Создать dev benchmark в двух слоях:
    - **Silver set**: все warm-up вопросы с автооценкой и ручным spot-check;
    - **Gold set**: вручную размеченный поднабор вопросов с ответами и минимальными support pages.
4. Разделить gold set на типовые корзины:
    - deterministic single-page;
    - deterministic multi-page;
    - comparative;
    - multi-document;
    - negative/unanswerable;
    - free_text.
5. Ввести run protocol: baseline меняется только после прогона по gold/silver sets.

**Выходы этапа.**
- `corpora/warmup_manifest.json`
- `corpora/final_manifest.json`
- `eval/dev_silver.json`
- `eval/dev_gold.json`

**Критерий завершения.**

- Warm-up corpus обрабатывается отдельно от final corpus; baseline оценивается локально на фиксированном наборе вопросов.

---

## Stage B3. Ingestion и canonical intermediate format

**Цель.**  
Построить единый промежуточный формат документов, пригодный для retrieval, page attribution и дебага.

**Состав работ.**

1. Реализовать ingestion pipeline:
    - extract native PDF text layer;
    - extract page images/thumbnails when needed;
    - detect page count, order, page geometry;
    - preserve raw parser outputs.
        
2. Спроектировать canonical schema на уровне:
    - document;
    - page;
    - block;
    - heading;
    - table;
    - clause;
    - chunk;
    - evidence link.
        
3. На каждый page object сохранять:
    - `doc_id`, `page_number`;
    - `source_mode` (`native`, `ocr`, `hybrid`);
    - `raw_text`, `normalized_text`;
    - `quality_metrics`;
    - `layout_flags`;
    - `blocks`;
    - `table_ids`;
    - `clause_ids`.
        
4. На каждый chunk сохранять:
    - parent page span;
    - parent section/clause;
    - normalized metadata;
    - retrieval fields;
    - provenance.
        
5. Генерировать два output-слоя:
    - **structured source of truth**: JSONL/Parquet;
    - **human-readable debug layer**: markdown/HTML snapshots.
        

**Выходы этапа.**
- `parsed_pages.parquet`
- `parsed_blocks.parquet`
- `chunks.parquet`
- `debug_docs/*.md`

**Критерий завершения.**
- Любой retrieved chunk может быть без потерь отображён обратно в конкретный документ, страницу и блок.

---

## Stage B4. OCR routing и page quality control

**Цель.**  
Построить простой, устойчивый и дешёвый по риску механизм выбора режима parsing/OCR.

**Состав работ.**

1. Реализовать **offline rule-based page triage**; online routing не используется.
2. Ввести базовые классы страниц:
    - `native_clean`;
    - `scan_or_image_dominant`;
    - `suspicious_layout`.
        
3. Вычислять page-level features:
    - символы/слова в native text;
    - printable ratio;
    - garbage ratio;
    - raster coverage;
    - table density;
    - multi-column flag;
    - rotated/skewed flag;
    - heading continuity flag.
        
4. Политика baseline:
    - `native_clean` → принять native parse;
    - `scan_or_image_dominant` → OCR fallback;
    - `suspicious_layout` → выполнить native + OCR, выбрать лучший результат по QC score.
        
5. Реализовать QC score:
    - text completeness;
    - legal marker density;
    - table integrity;
    - heading continuity;
    - absence of encoding garbage.
        
6. Для OCR fallback в baseline использовать **PaddleOCR-VL-1.5** через официальный page-level inference path.
7. Сохранять parse provenance и quality scores для каждого page.

**Выходы этапа.**
- `page_routing_manifest.json`
- `page_quality_scores.parquet`
- `ocr_outputs/`
    

**Критерий завершения.**

- Каждая страница корпуса имеет зафиксированный mode, QC score и provenance. Challenge прямо требует поддержку digitally-born и scanned PDFs; PaddleOCR-VL-1.5 поддерживает page-level parsing, cross-page table merging и heading recognition, поэтому он подходит для baseline fallback. ([Hugging Face](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.5?utm_source=chatgpt.com "PaddlePaddle/PaddleOCR-VL-1.5 · Hugging Face"))

---

## Stage B5. Таблицы, структура документа и metadata enrichment

**Цель.**  
Превратить таблицы и правовую структуру документов в retrieval-friendly объекты.

**Состав работ.**

1. Реализовать detection и нормализацию:
    - titles;
    - sections;
    - subsections;
    - clauses;
    - annexes/schedules;
    - cross-references;
    - case numbers;
    - dates;
    - parties/entities.
        
2. Реализовать **table serialization** по образцу сильного решения ERC2:
    - брать HTML/structured table;
    - добавлять текст до/после таблицы;
    - превращать таблицу в self-contained information blocks.
        
3. Для каждой таблицы сохранять:
    - caption/title;
    - page span;
    - row/column headers;
    - units/currency;
    - totals/footnotes;
    - serialized blocks.
        
4. Реализовать cross-page linkage:
    - continued tables;
    - continued headings;
    - annex references.
        
5. Сформировать metadata views:
    - `entities_view`
    - `dates_view`
    - `sections_view`
    - `tables_view`
        

**Выходы этапа.**
- `tables_serialized.parquet`
- `sections.parquet`
- `entities.parquet`
- `dates.parquet`
    

**Критерий завершения.**

- Любая таблица может быть извлечена как самостоятельный retrieval object, а структура документа доступна на уровне section/clause/table. Такой подход непосредственно опирается на паттерн `serialize-tables` из победного RAG-Challenge-2. ([GitHub](https://github.com/IlyaRice/RAG-Challenge-2 "GitHub - IlyaRice/RAG-Challenge-2: Implementation of my RAG system that won all categories in Enterprise RAG Challenge 2 · GitHub"))

---

## Stage B6. Chunking, metadata binding и index building

**Цель.**  
Построить многоуровневое chunk representation, пригодное для hybrid retrieval и page-grounding.

**Состав работ.**

1. Реализовать иерархию представлений:
    - page chunks;
    - section chunks;
    - clause chunks;
    - microchunks;
    - serialized table blocks.
        
2. Для каждого chunk хранить:
    - parent page/page span;
    - parent section/clause;
    - neighboring headings;
    - normalized entities/dates;
    - lexical text;
    - dense text.
        
3. Построить индексы baseline:
    - lexical BM25/FTS index;
    - dense vector index;
    - metadata lookup index;
    - page-parent map.
        
4. Dense retriever baseline: **Qwen3-Embedding-0.6B**.
    
5. Reranker baseline: **Qwen3-Reranker-0.6B**.
    
6. Внедрить parent-page lifting:
    - retrieve on chunk level;
    - aggregate on parent page / parent section level.
        
7. Внедрить retrieval budgets:
    - candidate budget;
    - rerank budget;
    - evidence budget.
        

**Выходы этапа.**

- `index_lexical/`
- `index_dense/`
- `index_metadata/`
- `page_parent_map.json`

**Критерий завершения.**

- Для любого вопроса retrieval pipeline выдаёт candidate pages, candidate chunks и parent-page aggregates. Qwen3 official stack даёт 0.6B embedding+rereanker с 32K context и instruction-aware режимом; parent retrieval подтверждён как рабочий паттерн в победном решении ERC2. ([GitHub](https://github.com/QwenLM/Qwen3-Embedding?utm_source=chatgpt.com "GitHub - QwenLM/Qwen3-Embedding"))

---

## Stage B7. Query routing и answer planning

**Цель.**  
Направлять вопрос в правильный solving path без избыточной агентности.

**Состав работ.**

1. Ввести router по двум осям:
    - `answer_type`;
    - query shape.
2. Query shape baseline:
    - single-document extraction;
    - comparative;
    - multi-document;
    - negative/unanswerable;
    - free_text assistant.
3. Реализовать lightweight comparative decomposition:

    - detect comparison cues;
    - split into subquestions;
    - run subquestions independently;
    - aggregate final answer.
        
4. Реализовать deterministic planners:
    
    - number solver;
    - boolean solver;
    - name solver;
    - names solver;
    - date solver;
    - null detector.
        
5. Реализовать free_text planner:
    
    - retrieve;
    - compress evidence;
    - generate short grounded answer;
    - enforce 280-char limit.
6. Все intermediate outputs оформлять через structured schema.

**Выходы этапа.**

- `router.py`
- `solvers/*.py`
- `schemas/*.json`
    

**Критерий завершения.**

- Каждый вопрос детерминированно попадает в конкретный path; comparative routing и structured output перенимают идеи из RAG-Challenge-2 и ERC3 agent architecture. ([GitHub](https://github.com/IlyaRice/RAG-Challenge-2 "GitHub - IlyaRice/RAG-Challenge-2: Implementation of my RAG system that won all categories in Enterprise RAG Challenge 2 · GitHub"))


---

## Stage B8. Evidence compression, support-page validation и telemetry packing

**Цель.**  
Минимизировать noise в `retrieved_chunk_pages` без потери required evidence.

**Состав работ.**

1. Ввести явное разделение:
    - candidate retrieval;
    - final evidence set.
        
2. Реализовать **support-page validator**:
    - финальные pages должны быть подмножеством реально retrieved pages;
    - pages, не подтверждённые retrieval, удаляются;
    - при недостатке pages добираются top pages из reranked evidence pool.
        
3. Реализовать **support-page compressor**:
    - дедуп по page;
    - greedy remove-test;
    - separate budgets for deterministic vs free_text.

4. Реализовать null/unanswerable page policy.
    
5. Реализовать telemetry packer:
    
    - timing;
    - usage;
    - retrieval;
    - model name.
        
6. Реализовать pre-submit sanity checks:
    
    - page indices;
    - unknown doc_id detection;
    - timing consistency;
    - telemetry completeness.
        

**Выходы этапа.**

- `evidence_selector.py`    
- `telemetry_packer.py`
- `pre_submit_checks.py`


**Критерий завершения.**

- `retrieved_chunk_pages` содержит только реально использованные physical pages и удовлетворяет локальному telemetry validator. Этот модуль прямо соответствует правилам challenge и использует сильнейшую практику из `questions_processing.py` победителя ERC2. ([GitHub](https://raw.githubusercontent.com/IlyaRice/RAG-Challenge-2/main/src/questions_processing.py "raw.githubusercontent.com"))
    
---

## Stage B9. Answer generation, style enforcement и confidence policy

**Цель.**  
Сформировать финальные ответы в формате, оптимальном под scoring.

**Состав работ.**

1. Deterministic answers:

    - извлечение из evidence;
    - normalization;
    - final validation against answer type.
        
2. Free_text answers:
    - grounded only;
    - no new facts outside evidence;
    - compact style;
    - max 280 chars;
    - calibrated uncertainty wording.
        
3. Ввести answer self-check:
    - answer type compatibility;
    - contradiction check against evidence;
    - null gate;
    - length gate.
        
4. Разделить backend generation policy:
    - deterministic paths по возможности без генерации;
    - генерация только для aggregation, rewriting, free_text.
        
5. Abstract model backend:
    - public remote backend через допустимый публичный интерфейс;
    - interchangeable provider layer;
    - optional fallback backend.

**Выходы этапа.**

- `answer_formatter.py`
- `free_text_templates.py`
- `self_check.py`
- `providers/`


**Критерий завершения.**

- Все ответы соответствуют expected answer format; free_text сохраняет grounded и concise profile, что соответствует правилам judge и ограничениям challenge.

---

## Stage B10. Regression harness, traces, consistency testing и submission operations

**Цель.**  
Обеспечить управляемую эволюцию baseline и качественную подготовку сабмитов.

**Состав работ.**

1. Реализовать regression harness:
    
    - full dev benchmark;
    - slice-by-slice metrics;
    - failure clustering.

2. Реализовать consistency testing:    
    - repeated runs on same task set;
    - variance analysis;
    - unstable question detection.
    
3. Реализовать trace export:
    - retrieval trace;
    - rerank trace;
    - answer trace;
    - telemetry trace.
        
4. Реализовать packaging:
    - `submission.json`;
    - `code_archive.zip`;
    - architecture summary.

5. Ввести submit gate:
    - no malformed telemetry;
    - no unknown doc_id;
    - code archive size limit respected;
    - reproducible config attached.
        
6. Ввести leaderboard log:
    
    - submission UUID;
    - config version;
    - expected deltas;
    - observed deltas.
        

**Выходы этапа.**

- `regression_report.html/json`
- `trace_exports/`
- `pack_submission.py`
- `submit_gate.py`


**Критерий завершения.**

- Baseline end-to-end проходит demo corpus, генерирует валидный submission package и даёт стабильные результаты на repeated runs. Submission API требует `submission.json` и code archive; code archive ограничен 25 MB; количество сабмитов ограничено, поэтому regression gate обязателен. ([GitHub](https://github.com/IlyaRice/Enterprise-RAG-Challenge-3-AI-Agents "GitHub - IlyaRice/Enterprise-RAG-Challenge-3-AI-Agents: Implementation of my AI agent system for ERC 3: https://erc.timetoact-group.at · GitHub"))


---

# Часть II. Эксперименты и рассмотрение альтернатив

## 1. Принцип ведения экспериментальной части

Эксперименты запускаются **только после freeze baseline**.  
Каждое изменение проходит через:

1. isolated branch/config version;
    
2. one-variable-at-a-time evaluation;
    
3. comparison against fixed baseline on the same dev slices;
    
4. merge only if выигрывает по основным приоритетам: grounding, deterministic score, telemetry health, затем TTFT.
    

---

## Track E1. OCR и document parsing alternatives

**Назначение.**  
Улучшение hard-page coverage поверх baseline OCR routing.

**Кандидаты.**

1. **DeepSeek-OCR-2** как hard-page fallback для very difficult pages.  
    Использовать только после baseline, поскольку официальный модельный стек описывает dynamic resolution, markdown/document conversion и 3B-class model footprint; это потенциально полезно для сложных layout-heavy страниц, но риск по ресурсу и сложности интеграции выше, чем у baseline fallback. ([Hugging Face](https://huggingface.co/deepseek-ai/DeepSeek-OCR-2/blob/main/README.md?utm_source=chatgpt.com "README.md · deepseek-ai/DeepSeek-OCR-2 at main"))
    
2. **Docling-based parsing** как альтернативный parser branch.  
    Победитель ERC2 использовал custom PDF parsing with Docling; branch целесообразен как controlled parser comparison, а не как baseline replacement по умолчанию. ([GitHub](https://github.com/IlyaRice/RAG-Challenge-2 "GitHub - IlyaRice/RAG-Challenge-2: Implementation of my RAG system that won all categories in Enterprise RAG Challenge 2 · GitHub"))
    
3. **MinerU / RAG-Anything style parser layer**.  
    RAG-Anything декларирует end-to-end multimodal pipeline, universal document support, multimodal knowledge graph и adaptive processing modes; branch имеет смысл только если warm-up покажет значимый вклад таблиц, изображений и формул в ответы. ([GitHub](https://github.com/HKUDS/RAG-Anything?utm_source=chatgpt.com "GitHub - HKUDS/RAG-Anything: \"RAG-Anything: All-in-One RAG Framework\""))
    

**Что измерять.**

- page parse quality;
    
- table continuity;
    
- heading continuity;
    
- impact on grounding;
    
- ingestion cost;
    
- support-page precision.
    

---

## Track E2. Dense retriever alternatives

**Назначение.**  
Повышение retrieval recall и/или снижение resource cost.

**Кандидаты.**

1. **pplx-embed-v1-0.6B** как challenger dense retriever.  
    Perplexity официально позиционирует `pplx-embed-v1` как dense retrieval model, а `pplx-embed-context-v1` — как contextualized embeddings for document chunks; оба семейства доступны в 0.6B и 4B, поддерживают 32K context, MRL и INT8/BINARY embeddings. Это сильный экспериментальный кандидат, но не baseline, так как экосистема и эксплуатационный контур пока менее консервативны, чем у Qwen stack. ([research.perplexity.ai](https://research.perplexity.ai/articles/pplx-embed-state-of-the-art-embedding-models-for-web-scale-retrieval?utm_source=chatgpt.com "pplx-embed: State-of-the-Art Embedding Models for Web-Scale Retrieval"))
    
2. **pplx-embed-context-v1-0.6B** для hierarchical/legal chunks из одного документа.  
    Использовать только в controlled experiment для chunk families, где важен surrounding document context. ([research.perplexity.ai](https://research.perplexity.ai/articles/pplx-embed-state-of-the-art-embedding-models-for-web-scale-retrieval?utm_source=chatgpt.com "pplx-embed: State-of-the-Art Embedding Models for Web-Scale Retrieval"))
    
3. **EmbeddingGemma** как speed/footprint branch.  
    Google официально описывает EmbeddingGemma как 308M multilingual embedding model, 2K context, flexible dimensions 768→128 и low-RAM deployment with quantization. Это хороший вариант для fast/cheap local indexing branch и fallback scenario. ([Google AI for Developers](https://ai.google.dev/gemma/docs/embeddinggemma?utm_source=chatgpt.com "EmbeddingGemma model overview  |  Google AI for Developers"))
    
4. **jina-embeddings-v4** как multimodal retrieval branch.  
    Jina v4 официально описана как model с max sequence length 32768, single-vector 2048 и multi-vector 128, ориентированная на retrieval/text-matching/code; branch разумен только для мультимодального корпуса, не как baseline. ([Hugging Face](https://huggingface.co/jinaai/jina-embeddings-v4?utm_source=chatgpt.com "jinaai/jina-embeddings-v4 · Hugging Face"))
    

**Что измерять.**

- recall@k на dev gold;
    
- grounding delta;
    
- storage cost;
    
- indexing speed;
    
- retrieval stability by answer type.
    

---

## Track E3. Reranking, late interaction и evidence scoring alternatives

**Назначение.**  
Повышение final evidence quality без потери recall.

**Кандидаты.**

1. Larger reranker branch внутри Qwen family (`4B`) — только remote/API path.
    
2. Separate page scorer after reranking:
    
    - chunk score;
        
    - page aggregation score;
        
    - evidence utility score.
        
3. Multi-vector retrieval branch при необходимости визуально/таблично богатых документов.
    
4. Dual-stage reranking:
    
    - fast reranker for candidate pruning;
        
    - stronger reranker for final evidence set.
        

**Что измерять.**

- grounding precision;
    
- number of irrelevant pages per answer;
    
- final evidence set size;
    
- TTFT impact.
    

---

## Track E4. Exact-match и sidecar indexing alternatives

**Назначение.**  
Усиление retrieval на именах, номерах дел, датах, ссылках на статьи, редких формулировках.

**Кандидаты.**

1. Lightweight exact-match sidecar index:
    
    - trigram/FTS;
        
    - regex layer;
        
    - article/clause reference index.
        
2. **Infini-gram-mini inspired** branch:
    
    - не полный перенос paper;
        
    - а точечное тестирование идеи exact string retrieval и memory-efficient side index для highly specific legal references.
        
3. Dedicated metadata retrievers:
    
    - date retriever;
        
    - case number retriever;
        
    - party name retriever.
        

**Что измерять.**

- uplift на deterministic `name/date/number`;
    
- uplift на negative/adversarial cases;
    
- impact on support-page minimality.
    

**Решение по статусу.**

- exact-match sidecar — допустимый ранний experiment;
    
- full FM-index-like integration — только после baseline и только при реальной необходимости.
    

---

## Track E5. Graph, light-graph и multimodal retrieval alternatives

**Назначение.**  
Усиление multi-hop и structure-aware retrieval.

**Кандидаты.**

1. **Light graph layer**:
    
    - section → subsection → clause;
        
    - definition → mentions;
        
    - main body → annex;
        
    - table → footnote;
        
    - clause → cited clause.
        
2. Metadata graph for legal references.
    
3. **RAG-Anything-inspired multimodal branch**:
    
    - dual-mode parsing;
        
    - multimodal knowledge graph;
        
    - hybrid retrieval across text/tables/images.
        
4. Full graph DB — только как поздняя экспериментальная ветка, не baseline.
    

**Что измерять.**

- multi-document and multi-hop uplift;
    
- complexity overhead;
    
- evidence stability;
    
- page attribution quality.
    

**Решение по статусу.**

- light graph — допустимая среднеприоритетная экспериментальная ветка;
    
- full graph DB / full multimodal framework — только после доказанного value. ([GitHub](https://github.com/HKUDS/RAG-Anything?utm_source=chatgpt.com "GitHub - HKUDS/RAG-Anything: \"RAG-Anything: All-in-One RAG Framework\""))
    

---

## Track E6. Query decomposition и selective agentic escalation

**Назначение.**  
Улучшение hard comparative и complex free-text cases без превращения всего пайплайна в agent-first system.

**Кандидаты.**

1. Расширенный comparative decomposition beyond baseline:
    
    - party-by-party;
        
    - document-by-document;
        
    - time-slice comparison;
        
    - amendment-vs-current comparison.
        
2. **Selective agentic escalation**:
    
    - включается только если deterministic/standard path даёт low confidence.
        
3. **Pre-execution validation** для agentic branch:
    
    - validate retrieval plan;
        
    - validate selected pages;
        
    - validate null decision;
        
    - validate answer schema.
        
4. **Dynamic context selection** before final generation:
    
    - выбирать только релевантные context blocks.
        
5. Краткая memory policy:
    
    - хранить только successful execution path;
        
    - отбрасывать failed validation loops.
        

**Что измерять.**

- uplift на hard free_text;
    
- reduction of unsupported claims;
    
- TTFT impact;
    
- regression risk for deterministic questions.
    

**Решение по статусу.**

- query decomposition — ранний experiment;
    
- full agent loop — поздний experiment;
    
- multi-agent orchestration — только при явном дефиците baseline на определённом классе задач. Идеи для этого трека напрямую следуют из Plan ReAct + step validation + dynamic context selection из ERC3 solutions. ([GitHub](https://github.com/IlyaRice/Enterprise-RAG-Challenge-3-AI-Agents "GitHub - IlyaRice/Enterprise-RAG-Challenge-3-AI-Agents: Implementation of my AI agent system for ERC 3: https://erc.timetoact-group.at · GitHub"))
    

---

## Track E7. Provider/model backend alternatives для generation

**Назначение.**  
Сохранить качество generation при ограничениях по локальному железу и эксплуатационным лимитам.

**Кандидаты.**

1. Primary remote public backend.
    
2. Secondary remote public backend.
    
3. Local fallback backend только для:
    
    - extraction support;
        
    - emergency degraded mode;
        
    - offline dev.
        
4. Provider abstraction:
    
    - unified request/response schema;
        
    - timing/usage normalization;
        
    - retry policy;
        
    - caching layer.
        

**Что измерять.**

- free_text quality;
    
- cost/availability;
    
- token telemetry availability;
    
- stability on batch runs;
    
- TTFT.
    

**Решение по статусу.**

- provider abstraction обязателен;
    
- выбор primary backend делается после baseline validation и load testing;
    
- generation backend не должен быть жёстко зашит в retrieval pipeline. Challenge разрешает public APIs/public models и допускает approximate tokenization при отсутствии provider-reported counts.
    

---

## Track E8. Context pruning и answer verification alternatives

**Назначение.**  
Снизить hallucination risk и избыточный evidence noise.

**Кандидаты.**

1. Learned evidence compressor.
    
2. Answer-conditioned page selection.
    
3. Minimal hitting-set page selector.
    
4. Post-answer contradiction check.
    
5. Double-pass free_text:
    
    - first answer;
        
    - factual support audit;
        
    - compressed final answer.
        

**Что измерять.**

- grounding precision;
    
- free_text grounding criterion;
    
- answer brevity/clarity;
    
- over-pruning failures.
    

---

## Track E9. Performance engineering alternatives

**Назначение.**  
Улучшить throughput и TTFT после стабилизации качества.

**Кандидаты.**

1. Query batching for embeddings/reranking.
    
2. Async retrieval + generation orchestration.
    
3. Artifact caching:
    
    - page parses;
        
    - embeddings;
        
    - rerank features;
        
    - solved subquestions.
        
4. Parallel ingestion.
    
5. Lightweight per-answer telemetry aggregation.
    

**Что измерять.**

- mean TTFT;
    
- p95 TTFT;
    
- total throughput on 100-question dev run;
    
- reproducibility under concurrency.
    

TTFT влияет на итоговый score, но остаётся вторичным относительно grounding и correctness; поэтому этот трек не должен подменять собой quality work.

---

# Итоговая граница между Baseline и Experiment

## В baseline включается обязательно

1. Local evaluator + validator.
    
2. Phase-isolated corpus manager.
    
3. Canonical structured intermediate format.
    
4. Rule-based OCR routing.
    
5. Native parse + PaddleOCR-VL-1.5 fallback.
    
6. Table serialization.
    
7. Clause-aware hierarchical chunking.
    
8. BM25 + Qwen3-Embedding-0.6B + Qwen3-Reranker-0.6B.
    
9. Parent-page lifting.
    
10. Support-page validator/compressor.
    
11. Typed solvers + free_text generator.
    
12. Versioned configs.
    
13. Trace logging + consistency testing.
    
14. Submission packager + submit gate. ([Hugging Face](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.5?utm_source=chatgpt.com "PaddlePaddle/PaddleOCR-VL-1.5 · Hugging Face"))
    

## В baseline не включается

1. Full graph DB.
    
2. Full multi-agent orchestration.
    
3. Full multimodal embeddings stack.
    
4. DeepSeek-OCR-2 as default OCR.
    
5. Jina v4 as default retriever.
    
6. Full RAG-Anything adoption.
    
7. Full Infini-gram style index integration.
    
8. Research-heavy self-reflection loops.
    

## В experiments отправляется в первую очередь

1. pplx-embed-v1 / pplx-embed-context-v1.
    
2. EmbeddingGemma speed branch.
    
3. DeepSeek-OCR-2 hard-page fallback.
    
4. Light graph / exact-match sidecar.
    
5. Selective agentic escalation with validation.
    
6. Multimodal branch only при доказанной необходимости. ([research.perplexity.ai](https://research.perplexity.ai/articles/pplx-embed-state-of-the-art-embedding-models-for-web-scale-retrieval?utm_source=chatgpt.com "pplx-embed: State-of-the-Art Embedding Models for Web-Scale Retrieval"))

---

# Управляющее правило проекта

Любая новая гипотеза допускается к интеграции только при выполнении трёх условий:

1. не ломает формат, telemetry и page attribution;
2. улучшает baseline на фиксированном dev benchmark;
3. не ухудшает grounding-first профиль системы.