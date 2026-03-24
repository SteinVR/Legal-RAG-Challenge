# 0: Inital My Query
Давай обсудим следующее сореванование - Agentic RAG Challenge (документы о нем прикрепил: "about_challenge.md и два других").
Сразу обозначу - я ориентируюсь на призовые места, поэтому не стоит ограничиваться только классическими подходами (они призерство не обеспечат)
Насколько я понял из предоставленных материалов (перепроверь), recall важнее precision (но лучше не упарываться), а точность важнее TTFT (если я правильно понял там максимальный штраф всего 15%). Кроме того, учитывается только TTFT, а время на предобработку, ембеддинг, формирование бд - нет.

По исполнению - вот предварительный сгрупированный список отдельных частей работы:
1. Разработка блока обработки - пайплайна обработки данных и формирования более удобного формата для дальнейшей работы (по моему мнению один из самых важных)
	- Обработка:
		1) Обработка выделяемого текста
		2) Обработка сканов
		3) Обработка таблиц
		4) Обработка дат
		5) Обработка изображений, графиков (если есть)
2. Формирование одной или нескольких бд из обработанных документов (изучить применимость статьи INFINI-GRAM MINI)
	- Гибридная (Векторная + Лексическая)
	- Графовая
	- Obsidian like .md
3. Разбитие на чанки, функционал привязки метаданных к чанкам.
	- Чанки:
		- Подобрать метод разбития на чанки (фиксированный - не катит)
		- Большие чанки - маленькие подчанки
		- Подмешивание контекста к чанкам для лучших скоров
4. OCR:
	- DeepSeek-OCR2
	- PaddleOCR-VL-1.5
	- или другие
5. Embedding (изучи каждый вариант подробно)
	1. Diffusion-Pretrained Dense and Contextual Embeddings (Perplexity) (изучи работу)
		- **`pplx-embed-v1`**
		- **`pplx-embed-context-v1`**
	2. EmbeddingGemma
	3. jina-embeddings-v4
	4. Qwen3-Embedding
	5. или другие
6. Дополнительные инженерные фичи и доп. функционал для потенциальных агентов (на потом)
	1. Reranker
	2. и другое
7. Generation (или)
	1. Classic LLM + SO + Schema Guided Reasoning (если брать локалку)
	2. Agent (думаю взять уже готовую реализацию условного opencode)
	3. Multi-Agent (думаю взять уже готовую реализацию условного opencode)

Дополнительно мои мысли и информация:
- Первые 3 пункта по моему мнению самые важные, от них зависит качество всего пайплайна. 
- Возможно нужно будет делать ставку на OCR, чтобы корректно выделять сегменты из документов и корректно их связывать.
- Мое железо - AMD Ryzen 7 7840h, RTX 4060 8gb, ram 32gb.
- По поводу агентов и LLM - лучше брать по api или еще лучше - через oauth (работает с opencode или codec cli), поскольку железо у меня не топовое и это скажется на результате. 
- Модели второстепенных моделей (embedding, ocr, reranking и т.д.) лучше брать компактные и быстрые (мало времени на обработку всего корпуса из 1000 документов, а железно не топовое)
- Есть уже готовые фреймворки по работе с RAG - можно попробовать использовать их, модифицировать под свои нужды. (RAG-Anything, A-RAG, и другие)

От тебя я прошу:
- Кропотливо изучить детали соревнования.
- Изучить представленные дополнительные материалы - модели, исследования и т.д.
- Сформировать свое видение проекта, соревнования
- Вникнуть в мой список - пайплайн, возможно доработать, дополнить, конкретизировать, поскольку что-то я мог пропустить, чего то я могу не знать. Может ты знаешь варианты чего-то лучше.
- Отписаться мне - обсудим.

# 1: Обзор и комментарии по соревнованию

Итоговый score считается как `(0.7 * S_det + 0.3 * S_asst) * G * T * F`, где `G` — grounding multiplier, `T` — telemetry factor, `F` — TTFT factor. То есть базу дают корректные ответы, но именно grounding может “обнулить” почти всё остальное. Для retrieval используется `F-beta` с `β = 2.5`, так что recall действительно заметно важнее precision. На цифрах это видно очень хорошо: при `precision=1, recall=0.5` получается `G≈0.537`, а при `precision=0.5, recall=1` — уже `G≈0.879`. Но в precision тоже нельзя проваливаться: даже при `recall=1`, если `precision≈0.2`, grounding падает до `≈0.644`. То есть твое “recall важнее, но не упарываться” — по сути верно.

Отсюда главный практический вывод: оптимизировать надо не “precision вместо recall” и не “recall вместо precision”, а **high recall на candidate stage + aggressive evidence compression на final stage**. Это идеально бьется с API-правилом: в telemetry нужно указывать только те страницы, которые реально использовались для ответа; лишние страницы ухудшают grounding. Иными словами: внутри системы ты можешь искать широко, но наружу должен отдавать минимальный support set. Это, на мой взгляд, самый важный инженерный инсайт всей задачи.

По TTFT ты тоже в целом прав. Бонус/штраф относительно умеренный: `<1s` даёт `1.05`, `1–2s` — `1.02`, `2–3s` — `1.00`, а после `3s` начинается штраф вплоть до `0.85`. То есть TTFT важен, но он точно **вторичен** относительно ingestion/retrieval/grounding. При этом на длинной серии из 900 вопросов медленный пайплайн всё равно будет заметно проседать, так что его нельзя игнорировать совсем.

И да: preprocessing/indexing/build embeddings/index DB **не скорятся**. Платформа не вызывает твою систему; ты сам скачиваешь документы и вопросы, строишь всё локально, а в score идёт только per-answer telemetry. Причём TTFT меряешь ты сам; если стриминга нет, `ttft_ms = total_time_ms`. Это открывает очень жирное окно для тяжелой предобработки корпуса, многослойных индексов и offline enrichment.

Есть один неприятный нюанс в документации, который я бы сразу вынес в список рисков. В `EVALUATION.md` для unanswerable-вопросов дважды сказано возвращать `retrieved_chunk_pages: []`, и тогда при пустом gold set grounding будет `1.0`. Но в секции telemetry validation там же есть фраза про `retrieved_chunk_pages present and non-empty`. Это внутренне противоречиво. Для score-оптимизации пустой массив всё равно выглядит единственно правильным поведением на truly unanswerable кейсах, потому что подставить фиктивные страницы — значит почти наверняка получить `G=0` на этих вопросах. Но это место я бы **обязательно** отдельно уточнил у организаторов до финальных сабмитов.

Теперь по сути проекта. Мой вывод такой: это соревнование не столько про “красивого агента”, сколько про **corpus compiler + evidence attribution engine**. Победная система, скорее всего, будет не “самой агентной”, а той, которая лучше всех превращает разнородные legal PDFs в структурированный, page-grounded, answerable corpus.

Что я бы добавил в твой список как отдельные first-class блоки.

**0. Local evaluation harness и telemetry validator.**  
Это не “мелочь”, а обязательный модуль. У тебя всего 10 warm-up сабмитов и 2 private-stage сабмита; без локальной проверки submission JSON, page numbering, doc_id, null-policy и support pages очень легко проиграть не модели, а формату. Плюс deterministic-типы жёсткие: `date` — exact ISO 8601, `name` — normalized exact match, `names` — Jaccard over sets, `number` — ±1%, `null` — полноценный валидный ответ.

**1. Ingestion pipeline — это действительно центр тяжести.**  
С тобой согласен: первые 3 пункта у тебя самые важные. Но я бы в ingestion явно включил не только OCR/text/table parsing, а ещё: page map, heading tree, clause IDs, cross-references, annex/schedule linkage, dedup headers/footers/TOC, table continuation across pages, raw+normalized dates, raw+normalized entity names, and support-span-to-page mapping. Причина простая: scoring идёт по physical PDF pages, а не по твоим chunk IDs. `doc_id` — это SHA-like PDF filename, а `page_numbers` — физические 1-based страницы PDF.

Я бы делал канонический intermediate format не просто “markdown”, а **структурированный JSON/Parquet + markdown-представление для дебага**. Obsidian-like `.md` — отличная идея как human-readable слой, но не как единственный source of truth. В source of truth должны жить page-level и span-level связи, иначе потом будет больно делать evidence pruning.

**2. OCR: не просто “лучший текст”, а лучший layout-aware parser.**  
Для твоего железа я бы сделал **PaddleOCR-VL-1.5 дефолтным OCR/Doc Parsing слоем**, а не DeepSeek-OCR2. У PaddleOCR-VL-1.5 компактный размер `0.9B`, он заточен именно под document parsing, заявляет `94.5%` на OmniDocBench v1.5, улучшения по table/formula/text recognition, поддержку irregular-shaped localization, текст-споттинга, печатей, а также автоматическое cross-page table merging и cross-page heading recognition. Причём сами авторы пишут, что официальный inference path быстрее и поддерживает page-level parsing лучше, чем пример через `transformers`. Для legal PDFs это очень сильное попадание в задачу. ([Hugging Face](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.5 "https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.5"))

**DeepSeek-OCR-2** я бы не выбрасывал, но использовал бы как **fallback на hard pages**: старые сканы, tiny text, сложные multi-column страницы, проблемные таблицы. У него есть режим “convert the document to markdown”, dynamic resolution и сильные результаты на отдельных подзадачах olmOCR-bench, включая table tests, multi-column и long tiny text. Но по факту модель тяжелее: на Hugging Face веса занимают около `6.8 GB`, так что на RTX 4060 8GB это уже намного менее комфортный default, особенно если хочешь параллелить preprocessing. ([Hugging Face](https://huggingface.co/deepseek-ai/DeepSeek-OCR-2 "https://huggingface.co/deepseek-ai/DeepSeek-OCR-2"))

Мой практический рецепт тут такой:  
native PDF text layer first → layout reconstruction → PaddleOCR-VL-1.5 on suspicious/scan pages → DeepSeek-OCR-2 only on flagged hard pages.  
Так ты получаешь и скорость, и устойчивость.

**3. DB/индексы: не одна база, а 4 канала retrieval.**  
Я бы не спорил “гибридная или графовая или markdown-like”. Для призового решения я бы делал сразу несколько представлений:

- lexical index по clause/section text;
    
- dense index по hierarchical chunks;
    
- metadata index по title/section/case number/date/party names;
    
- exact-match channel для фраз, имен, номеров дел, статей, пунктов.
    

Полноценный graph layer — **опционально вторичный**, не основной. На корпусе порядка `~300` документов полный GraphRAG/Neo4j-центричный дизайн может дать меньше, чем стоит по времени и шуму extraction. Намного практичнее light graph/adacency map: section → subsection → clause, definition → usage, main body → annex, table fragment → continued page.

**4. INFINI-GRAM MINI — полезная идея, но, по-моему, не точка приложения сил.**  
Сам paper очень сильный: FM-index, размер индекса `0.44x` корпуса, возможность сжать до `0.26x`, `18x` ускорение индексации против SDSL, `83TB` проиндексировано, exact-match search и document retrieval за секунды. Но это решение для internet-scale exact string search. Для challenge с `~300` legal docs я бы не тратил драгоценное время на полноценную интеграцию FM-index-стека. Ценность paper для нас — не “внедрить как есть”, а взять идею отдельного **exact-match retriever** и byte/metadata-oriented indexing. На практике здесь хватит lightweight exact-match канала: SQLite FTS5/trigram/ripgrep-style index поверх clause files.

**5. Chunking: у тебя направление правильное, но нужно сделать его иерархическим и answer-aware.**  
Фиксированные окна действительно “не катят”. Я бы делал минимум 4 уровня: `document → section → clause → microchunk`. Для retrieval хранить и clause-level embedding, и parent-context text. Для длинных секций — large chunk + child chunks. Для таблиц — отдельные row-level и table-summary chunks. Для определения/support pages каждый chunk должен знать exact page span. Это ключевой момент: retrieval у тебя chunk-level, а evaluation — page-level.

Ещё одна важная деталь: because `name` и `date` score’ятся жёстко, делай search-time normalization, но answer-time **surface-form extraction**. То есть искать можно по нормализованным именам/датам, а отвечать нужно той формой, которая реально сидит в доказательственном фрагменте, иначе можно потерять exact match.

**6. По embedding-моделям мой shortlist такой.**  
Если смотреть на твое железо и цель “не просто baseline, а шанс на призы”, я бы первым делом A/B-тестил **pplx-embed-v1-0.6B** и **Qwen3-Embedding-0.6B**. У `pplx-embed-v1` есть очень сильный аргумент: paper показывает, что 0.6B-версия обгоняет `Qwen3-Embedding-0.6B` на MTEB Multilingual и MTEB Code, а также выглядит сильно на web-scale recall-oriented внутренних бенчмарках; при этом семейство по умолчанию выдаёт INT8 embeddings и не требует instruction prefixes. Плюс `pplx-embed-context-v1` именно для contextual chunk embeddings и на ConTEB показывает state-of-the-art `81.96` для 4B версии. Для длинных legal docs это очень созвучно задаче.

У **Qwen3-Embedding** свои плюсы: размеры `0.6B/4B/8B`, `32K` context, instruction-aware режим, MRL, поддержка `100+` языков и, что важно, в том же семействе есть **Qwen3-Reranker** `0.6B/4B/8B`. Это очень удобная экосистема, если хочешь плотную связку retriever+rereanker. Минус — instruction management и потенциально чуть более сложный runtime. ([GitHub](https://github.com/QwenLM/Qwen3-Embedding "https://github.com/QwenLM/Qwen3-Embedding"))

**EmbeddingGemma** я бы держал как speed/efficiency baseline, а не как основной кандидат на топ-3. Он очень привлекателен инженерно: `308M`, `2K` context, flexible dimensions `768→128`, `<200MB RAM` с quantization, `100+` языков. Для on-device это шикарно. Но для реально тяжёлого legal retrieval на длинных структурных фрагментах у меня ожидание, что более сильные 0.6B-class retrievers будут выигрывать по recall. ([Google AI for Developers](https://ai.google.dev/gemma/docs/embeddinggemma "https://ai.google.dev/gemma/docs/embeddinggemma"))

**jina-embeddings-v4** — очень интересный вариант, если warm-up покажет, что в корпусе реально много visually rich pages и page-image retrieval даёт профит. Он мультимодальный, `3.8B`, поддерживает text+image, single-vector и late-interaction multi-vector retrieval, рассчитан на tables/charts/diagrams/screenshots и имеет `32,768` токенов текста. Но для локального рантайма на 4060 8GB это почти наверняка слишком тяжёлая база. Я бы рассматривал его либо как API/remote option, либо как исследовательскую ветку, а не как первый боевой выбор. ([Jina AI](https://jina.ai/models/jina-embeddings-v4/ "https://jina.ai/models/jina-embeddings-v4/"))

Если свести это к практическому порядку тестов, я бы шёл так:

1. `pplx-embed-v1-0.6B`
    
2. `Qwen3-Embedding-0.6B`
    
3. `pplx-embed-context-v1-0.6B` на long-document subset
    
4. `EmbeddingGemma` как ultra-fast baseline
    
5. `jina-embeddings-v4` только если warm-up реально требует multimodal retrieval.
    

**7. Рерэнкер я бы не откладывал “на потом”.**  
Не как первый модуль, но как следующий после работающего hybrid retriever — да. Особенно потому, что guide прямо рекомендует dense + reranking + hybrid search, а Qwen3 уже даёт тебе готовую линейку reranker-моделей. Я бы смотрел прежде всего на компактный reranker уровня `0.6B`, и отдельно строил **support-page selector**, потому что reranker и evidence compressor — это не одно и то же. Первый упорядочивает кандидатов, второй выкидывает лишние страницы перед telemetry. ([GitHub](https://github.com/QwenLM/Qwen3-Embedding "https://github.com/QwenLM/Qwen3-Embedding"))

**8. Generation/agentic: здесь я бы был консервативнее тебя.**  
Я бы не ставил full agent или multi-agent в основу v1. У challenge fixed corpus, page-grounded scoring и очень короткий output (`free_text` до `280` символов). Это значит, что сильнее всего работают **typed solvers**: отдельная логика для `number / boolean / name / names / date / null`, плюс короткий grounded summarizer для `free_text`. Агентность я бы включал **селективно**, только для hard multi-hop/free-text кейсов после router-а.

Из готовых framework-идей я бы брал не “как есть”, а как доноров паттернов. **A-RAG** интересен тем, что формализует agentic retrieval как `keyword_search + semantic_search + chunk_read` и строится вокруг иерархических retrieval interfaces/ReAct-loop. Это очень похоже на то, что может пригодиться в юридической multi-hop задаче. Но сам по себе он — не legal-doc parser и не page-grounding engine. **RAG-Anything** интересен с другой стороны: dual-graph + cross-modal hybrid retrieval по тексту, изображениям, таблицам и формулам; это хороший источник идей для multimodal corpus compiler, но как full stack он, на мой взгляд, слишком широкий и тяжёлый для первой боевой итерации. ([GitHub](https://github.com/Ayanami0730/arag "https://github.com/Ayanami0730/arag"))

**9. По поводу OpenCode / OAuth.**  
Для runtime submission-пайплайна я бы OpenCode не делал частью системы. Но как девелоперский инструмент — да, вполне. OpenCode provider-agnostic, а GitHub в январе 2026 официально добавил поддержку аутентификации через Copilot subscription в OpenCode через `/connect` и device login. То есть для разработки/экспериментов это нормальный workflow. Но в самой соревновательной системе тебе нужен не coding agent, а жёсткий, воспроизводимый retrieval/answering pipeline. ([GitHub](https://github.com/anomalyco/opencode/ "https://github.com/anomalyco/opencode/"))

Если сжать всё до одного “моего” варианта старта под твоё железо, он был бы таким:

1. **Ingestion-first**: native PDF extraction + PaddleOCR-VL-1.5 as default page parser + DeepSeek-OCR-2 only on flagged hard pages.
    
2. **Canonical corpus**: structured JSON/Parquet + debug markdown, обязательный page/span map.
    
3. **Retrieval**: BM25 + dense retriever (`pplx-embed-v1-0.6B` vs `Qwen3-Embedding-0.6B` A/B) + metadata/exact-match channel.
    
4. **Post-retrieval**: compact reranker + support-page selector.
    
5. **Answering**: typed deterministic solvers + very short grounded free-text generator + null detector.
    
6. **Agentic escalation**: только для сложных multi-hop/free-text, не для всех вопросов подряд.
    

Итоговый тезис у меня такой: твой список хороший, но я бы поднял на верх не “агентов”, а **evidence compression, page attribution, typed answering и telemetry QA**. Именно это, а не “магический multi-agent”, больше всего похоже на то, что даст призовой upside в этом конкретном challenge.

---
# 2: Дополнительные комментарии

### a) Как делать dynamic OCR routing

Да, это отдельный механизм, но ключевой момент в том, **где он живёт**. Его не нужно крутить в online-loop на каждый вопрос. По документации платформа не вызывает твой сервис, ты сам локально скачиваешь корпус, строишь индексы и потом уже отвечаешь; offline ingestion/indexing не скорятся, в score идёт только per-answer telemetry и TTFT. Поэтому классификацию страниц и выбор OCR/парсера надо делать **один раз на этапе ingestion** и сохранять в page manifest на весь корпус фазы. У warm-up и final свои корпуса, их всё равно нужно индексировать независимо.

Я бы для baseline вообще **не делал ML-классификатор страниц**. Достаточно rule-based triage. Самая практичная схема такая:

`native parse -> quality check -> accept / OCR fallback -> quality check -> accept / hard-page fallback`

То есть “flagged hard page” — это не исходный класс, а **эскалация после QC**, если обычный путь не дал приемлемого текста.

Какие признаки я бы считал на страницу после native extraction:

1. количество извлечённых символов/слов;
    
2. доля printable characters и доля мусора вроде replacement chars, одиночных токенов, битой кодировки;
    
3. покрытие страницы растровым изображением;
    
4. число текстовых блоков и грубые признаки поломанного reading order;
    
5. флаги `table_heavy`, `multi_column`, `tiny_text`, `rotated`.
    

Дальше routing можно задать очень просто:

- **native-clean**: текстовый слой есть и он вменяемый → оставляем native;
    
- **scan/image-dominant**: текста почти нет, а page image dominates → сразу OCR;
    
- **suspicious**: текст есть, но он плохой или layout тяжёлый → прогоняем и native, и OCR, потом выбираем лучший результат по quality score.
    

Именно quality score тут важнее “класса страницы”. На suspicious-страницах я бы не гадал заранее, а сравнивал два результата и выбирал победителя по простому набору метрик: полнота текста, связность строк, число найденных legal-маркеров (`Section`, `Article`, `Clause`, даты, case numbers), заполненность таблиц, отсутствие мусора.

Для первого baseline я бы ещё сильнее упростил: **не делать full dynamic ensemble**. Достаточно двух режимов:  
native по умолчанию, OCR только если text layer отсутствует или явно битый.  
А вот DeepSeek как hard-page fallback — это уже ветка “после baseline”, не часть стартовой системы.

### b) Про OAuth, ChatGPT-подписку, OpenCode и вообще “можно ли так жить”

Твоя логика здесь в основе верная. По официальным материалам OpenAI, ChatGPT и API — это **разные биллинговые контуры**; подписка ChatGPT не переносится в API и API биллится отдельно. При этом Codex сейчас включён в ChatGPT Plus/Pro, и официальный Codex CLI можно авторизовать через ChatGPT-аккаунт, а не только через API key. OpenAI также отдельно документирует non-interactive/CI сценарий для ChatGPT-managed auth, хотя прямо пишет, что для автоматизации API keys — дефолтно более рекомендуемый путь. ([OpenAI Help Center](https://help.openai.com/en/articles/8156019-how-can-i-move-my-chatgpt-subscription-to-the-api "https://help.openai.com/en/articles/8156019-how-can-i-move-my-chatgpt-subscription-to-the-api"))

С OpenCode картина тоже не выдуманная: у него на сайте прямо заявлен вход через OpenAI для использования ChatGPT Plus/Pro аккаунта, а CLI поддерживает программный вызов через `opencode run ...`, то есть как non-interactive исполнитель он действительно годится. При этом в основной документации OpenCode сильнее акцентирует обычный provider/API-key flow, так что auth path через аккаунт надо проверить руками как можно раньше, а не считать “по умолчанию стабильным”. ([OpenCode](https://opencode.ai/ "https://opencode.ai/"))

Мой вывод здесь такой:

- **как dev-инструмент** — да, это отличная идея;
    
- **как runtime backend для generation** — тоже да, но я бы ранжировал варианты так:  
    **официальный Codex CLI > OpenCode с нативной поддержкой OpenAI login > community OAuth plugins**.
    

Почему я так осторожно формулирую. Не потому что подход плохой, а потому что у него есть 4 реальных риска:

1. у ChatGPT/Codex есть плановые usage limits, это не бесконечный ресурс;
    
2. токены и usage могут быть менее прозрачны, чем в API, хотя challenge разрешает approximate tokenization, если provider exact counts не даёт;
    
3. надо проверить headless-refresh и устойчивость длинного батча на 100/900 вопросов;
    
4. challenge просит использовать только public APIs/public models, и по духу подписочный публичный Codex, скорее всего, проходит, но формулировка не идеально буквальна. ([OpenAI Help Center](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan "https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan"))
    

Поэтому моя позиция не “не использовать OAuth”, а другая: **это нормальный кандидат на боевой backend**, просто его надо очень рано провалидировать на стабильность и один раз письменно уточнить у организаторов в Discord, что subscription-backed Codex/OpenCode usage считается допустимым как public model/public access path. Это дешёвое уточнение, которое снимает юридический риск.

### c) Про baseline-first вместо исследований

С этим я согласен почти полностью. Для такого challenge baseline-first — не просто разумный подход, а, по сути, обязательный. Документы прямо толкают в сторону production realism: ingestion, grounding, hybrid retrieval, telemetry correctness; плюс сабмитов мало — 10 на warm-up и 2 на private stage. То есть нельзя позволить себе месяц “исследовать красоту”.

Я бы жёстко разделил вещи на две корзины.

**Должно войти в baseline:**

- page-level ingestion с page map;
    
- native extraction + OCR fallback;
    
- clause-aware / heading-aware chunking;
    
- BM25 + один dense retriever;
    
- support-page selector;
    
- typed answering для `number/boolean/name/names/date/null`;
    
- один сильный generator backend;
    
- local eval/validator.
    

**Не должно блокировать baseline:**

- graph DB;
    
- multi-agent;
    
- OCR-ensemble из трёх моделей;
    
- INFINI-GRAM integration;
    
- multimodal embeddings;
    
- self-reflection / debate loops.
    

Reranker — пограничный случай. Если компактный reranker поднимается быстро и без боли, я бы включал его очень рано, потому что сами организаторы рекомендуют dense + reranking + hybrid search. Но если интеграция начинает тормозить весь baseline, тогда reranker — это **первый апгрейд поверх baseline**, а не обязательная стартовая часть.

И ещё важное уточнение: baseline должен быть не “самым простым”, а **самым предсказуемым**. Это разные вещи. В этом challenge предсказуемость телеметрии, page attribution и null-handling важнее красивых research-идей.

### d) Про local gold set и eval harness

Да, это обязательно. И тут у тебя только маленькая поправка по числам: в документах warm-up/public set — это **100 вопросов и примерно 30 документов**, а не 100 документов и 30 вопросов. Финал — 900 вопросов и примерно 300 документов.

Саму идею я полностью поддерживаю, но я бы разделил её на два слоя.

**Первый слой — строгий технический harness.**  
Он должен проверять:

- JSON schema submission;
    
- `question_id`;
    
- тип ответа по `answer_type`;
    
- `doc_id` как PDF filename;
    
- `page_numbers` как physical 1-based pages;
    
- timing constraints;
    
- usage non-negative;
    
- grounding scorer по F-beta;
    
- TTFT multiplier;
    
- telemetry penalties.
    

**Второй слой — локальный dev gold / silver set.**  
И вот тут я бы не пытался сразу разметить все 100 public questions “идеально”. Если официальные reference answers/page refs не будут выданы отдельно, а в API по `GET /questions` описаны только `id`, `question`, `answer_type`, то разумно предположить, что эталоны тебе, возможно, придётся собирать самому. В таком случае лучше сначала руками сделать **небольшой, но очень качественный набор** из 25–40 вопросов с точными support pages, чем размазать силы на все 100.

Для `free_text` я бы вообще не пытался “воссоздать” их внутреннего judge один в один. В документации сказано, что это internal LLM-based judge по пяти критериям. Локально тебе нужен не клон их judge, а **прокси для сравнений**: pairwise eval, rubric-based review, spot-check на hardest cases. Абсолютным числам такого judge я бы не верил, только относительным.

И ещё один важный момент для harness: я бы прямо зашил в него **проверку на противоречие в документации**. В `EVALUATION.md` для unanswerable cases сказано возвращать `retrieved_chunk_pages: []`, и это даёт grounding `1.0`, но в telemetry validation там же фигурирует требование `retrieved_chunk_pages present and non-empty`. Это нужно держать как explicit ambiguity и отдельно уточнить у организаторов.

Итог по твоим пунктам у меня такой:

- **a)** да, routing нужен, но offline и rule-based, не online-агентом;
    
- **b)** да, OAuth/ChatGPT/Codex/OpenCode — реальный и, вероятно, допустимый боевой путь, просто его надо быстро провалидировать и лучше опираться на официальные клиенты/доки, где это возможно;
    
- **c)** да, сначала freeze надёжный baseline, потом всё остальное;
    
- **d)** да, local harness и локальный gold/silver dev set — обязательны, и у тебя в числах warm-up была перестановка местами.
    
---
# 3 Заимствование идей из RAG Challenge 2-3

## Первый проход: что я сразу бы забрал

**1) Из `RAG-Challenge-2` — сериализация таблиц в контекстно-независимые блоки.**  
Это, на мой взгляд, одна из самых сильных идей из всех трёх репозиториев. У них таблицы не просто парсятся, а превращаются в самостоятельные information blocks: с row/column headers, единицами измерения, пояснениями, total-строками, валютой и прочим контекстом, чтобы такой блок можно было класть в retrieval как отдельный chunk. Плюс эти serialized tables отдельно вшиваются в chunked-report рядом с обычными текстовыми чанками. Для нашего legal RAG это очень ценно: именно так стоит обрабатывать приложения, тарифные таблицы, schedules, sanctions tables, fee grids и любые cross-page legal tables. ([GitHub](https://github.com/IlyaRice/RAG-Challenge-2 "https://github.com/IlyaRice/RAG-Challenge-2"))

**2) Из `RAG-Challenge-2` — parent-document / parent-page retrieval.**  
В репозитории явно есть режим, где retriever после поиска по chunk’ам возвращает не сам chunk, а родительскую страницу целиком (`return_parent_pages`). Для нашей задачи это почти идеально: искать можно на подчанках, но evidence и final context собирать на уровне страницы/родительского блока. Это очень хорошо совпадает с нашим scoring, потому что challenge оценивает grounding по physical PDF pages, а не по внутренним chunk IDs. ([GitHub](https://github.com/IlyaRice/RAG-Challenge-2 "https://github.com/IlyaRice/RAG-Challenge-2"))

**3) Из `RAG-Challenge-2` — валидация page refs против реально retrieved pages.**  
У них есть отдельный механизм, который вычищает “галлюцинированные” ссылки на страницы: если LLM назвал pages, которых не было среди retrieval results, такие страницы удаляются; если после чистки ссылок слишком мало, система добирает страницы из верхушки retrieval. Для нашего челленджа это вообще золото: у нас grounding считается по страницам, extra pages бьют по precision, missing pages бьют по recall. Я бы почти без изменений встроил такой `support-page validator / compressor` в наш пайплайн. ([GitHub](https://raw.githubusercontent.com/IlyaRice/RAG-Challenge-2/main/src/questions_processing.py "https://raw.githubusercontent.com/IlyaRice/RAG-Challenge-2/main/src/questions_processing.py"))

**4) Из `RAG-Challenge-2` — разбиение comparative questions на отдельные subquestions с параллельной обработкой.**  
Они для сравнительных вопросов сначала переформулируют исходный вопрос в по-компанийные подзадачи, потом гонят их параллельно, а уже затем собирают comparative answer. Для legal challenge это хорошо переносится на multi-document вопросы: сравнение редакций, comparison across regulations, conflicts between main text and annex, вопросы по нескольким судебным актам, вопросы по “какой документ/сторона/дата”. Это не надо делать universal default, но как router для comparative/multi-source queries — очень сильный паттерн. ([GitHub](https://github.com/IlyaRice/RAG-Challenge-2 "https://github.com/IlyaRice/RAG-Challenge-2"))

**5) Из `Enterprise-RAG-Challenge-3-AI-Agents` — pre-execution step validation.**  
Там самая блестящая идея не в том, что агент “думает”, а в том, что **каждое действие валидируется до исполнения**. Валидатор проверяет: тот ли tool выбран, корректны ли параметры, не нарушаются ли правила; если нет — шаг отклоняется, агент перестраивает его, а мусор не попадает в основной execution path. Для нашего legal RAG это отлично переносится не на все вопросы подряд, а на “agentic escalation path”: например, для hard free_text / multi-hop кейсов можно валидировать не tool-calls, а `retrieval plan`, `page set`, `null decision`, `answer type decision`. ([GitHub](https://github.com/IlyaRice/Enterprise-RAG-Challenge-3-AI-Agents "https://github.com/IlyaRice/Enterprise-RAG-Challenge-3-AI-Agents"))

**6) Из `Enterprise-RAG-Challenge-3-AI-Agents` — dynamic context selection до основного цикла.**  
Там до запуска агента собираются context blocks, а затем LLM выбирает только релевантные блоки для конкретного task. Это прямое попадание в наш challenge: candidate retrieval может быть широким, но final evidence set нужно сжимать. По сути это готовая идея для отдельного `context pruner` перед answer generation. ([GitHub](https://github.com/IlyaRice/Enterprise-RAG-Challenge-3-AI-Agents "https://github.com/IlyaRice/Enterprise-RAG-Challenge-3-AI-Agents"))

**7) Из `Enterprise-RAG-Challenge-3-AI-Agents` — “тонкая” память агента.**  
Они хранят в main conversation только успешные шаги, action summaries и актуальный remaining plan; validation failures и внутренний reasoning не засоряют историю. Для нас это означает: если делать agentic layer поверх baseline, то он должен быть короткопамятным и сжатым. Иначе TTFT и качество начинают деградировать просто из-за пухнущего контекста. ([GitHub](https://github.com/IlyaRice/Enterprise-RAG-Challenge-3-AI-Agents "https://github.com/IlyaRice/Enterprise-RAG-Challenge-3-AI-Agents"))

**8) Из `erc3-agents` — versioned evolution system для prompt/rule configs.**  
В `claude-agent-erc3-prod` у них не просто prompt, а версия конфигурации: `state.json` указывает active version, а в `vXXX/config.json` лежат `base_prompt`, `rules[]`, `examples[]`, `tool_patches{}`, `rulebook_sections{}`. Это очень сильная инженерная идея именно под дедлайн и under-limited submissions: не “улучшать промпт руками в хаосе”, а вести версионируемые боевые конфиги. Для нас это прямо просится как `configs/legal_vXX/`: chunking rules, page selector policy, null policy, free_text style, evidence pruning rules, typed extractor rules. ([GitHub](https://github.com/maddness/erc3-agents "https://github.com/maddness/erc3-agents"))

**9) Из `erc3-agents` — composite tools.**  
У них есть составные инструменты, которые схлопывают частые multi-call паттерны в одну операцию. В legal RAG это можно перенести не как SDK tools, а как “составные retrieval tools”: например, `locate-definition-and-usage`, `find-clause-and-amendment-history`, `table-row-plus-footnote`, `main-section-plus-annex-reference`. Это снижает глубину agent loop и уменьшает шанс на тупые промежуточные ошибки. ([GitHub](https://github.com/maddness/erc3-agents/blob/main/CLAUDE.md "https://github.com/maddness/erc3-agents/blob/main/CLAUDE.md"))


## Второй проход: что я сначала недооценил, а потом повысил в приоритете

**1) Самая недооценённая идея — не parent retrieval, а именно reference validation.**  
На первом проходе я отметил parent-page retrieval как сильную штуку. На втором понял, что **ещё важнее не возврат parent pages сам по себе, а контроль того, какие страницы потом попадают в answer telemetry**. В нашем челлендже это практически отдельный модуль: retrieval может быть recall-heavy, но наружу должен выходить минимальный, валидированный support set. Репозиторий-победитель ERC2 это уже по сути делает. ([GitHub](https://raw.githubusercontent.com/IlyaRice/RAG-Challenge-2/main/src/questions_processing.py "https://raw.githubusercontent.com/IlyaRice/RAG-Challenge-2/main/src/questions_processing.py"))

**2) Я повысил в приоритете table serialization.**  
Сначала это выглядело как “полезный ingestion trick”. После второго прохода я считаю, что это **один из лучших кандидатов на наш конкурентный upside**. Потому что legal corpora очень часто убиваются не обычным текстом, а таблицами, расписаниями, разбросанными footnotes и контекстно-зависимыми totals. Идея делать из таблицы независимые enriched blocks — это почти готовый ответ на наш пункт “обработка таблиц + связка сегментов”. ([GitHub](https://raw.githubusercontent.com/IlyaRice/RAG-Challenge-2/main/src/tables_serialization.py "https://raw.githubusercontent.com/IlyaRice/RAG-Challenge-2/main/src/tables_serialization.py"))

**3) Я сначала воспринимал versioned prompt evolution из `erc3-agents` как nice-to-have, а теперь считаю это must-have.**  
Не потому что prompts magically win competitions, а потому что у нас мало сабмитов и высокий риск потерять track of changes. Версионирование rules/examples/tool patches — это по сути система управления гипотезами. Для челленджа с 10 warm-up и 2 private submissions это очень практичная идея. ([GitHub](https://github.com/maddness/erc3-agents/blob/main/CLAUDE.md "https://github.com/maddness/erc3-agents/blob/main/CLAUDE.md"))

**4) Я недооценил infra-идеи из ERC3-репозитория победителя.**  
Особенно две:  
первая — единая точка входа для всех LLM calls со structured output, retries и tracing;  
вторая — раздельная политика для read/write SDK operations: читать можно с retry, писать — без retry, чтобы не плодить дублей.  
Для legal RAG вторая мысль напрямую переносится на наши служебные операции: retrieval/ocr/parsing/re-ranking могут ретраиться, а submission/telemetry packing/final page selection — только очень аккуратно. Плюс там есть timeout wrapper для SDK calls и trace propagation при параллельном прогоне задач, что хорошо ложится на наш local eval harness. ([GitHub](https://raw.githubusercontent.com/IlyaRice/Enterprise-RAG-Challenge-3-AI-Agents/main/infrastructure.py "https://raw.githubusercontent.com/IlyaRice/Enterprise-RAG-Challenge-3-AI-Agents/main/infrastructure.py"))

**5) Я снизил ценность full multi-agent orchestration как базовой идеи для нас.**  
Во втором проходе стало ещё очевиднее: и у `Enterprise-RAG-Challenge-3-AI-Agents`, и у `erc3-agents` самые эффектные куски связаны с API-navigation benchmarks, а не с page-grounded legal retrieval. Нам не нужен “оркестратор ради оркестратора”. Нам нужен baseline, где retrieval, page attribution и typed answering работают железно; агентность — только как opt-in слой для hard cases. ([GitHub](https://github.com/IlyaRice/Enterprise-RAG-Challenge-3-AI-Agents "https://github.com/IlyaRice/Enterprise-RAG-Challenge-3-AI-Agents"))


## Что я бы реально интегрировал в наш пайплайн

**Внедрять почти сразу:**

1. **Table serialization into self-contained blocks** — взять как отдельный stage ingestion.
    
2. **Support-page validator / compressor** — после answer extraction, до telemetry packing.
    
3. **Comparative query decomposition** — для multi-document / comparison / amendment-style вопросов.
    
4. **Versioned experiment configs** — не только для prompts, а для всего: OCR policy, chunking policy, page-selection policy, null policy.
    
5. **Consistency / repeat-task harness + traces** — чтобы перед финальными сабмитами видеть не только average quality, но и разброс по одинаковым вопросам. ([GitHub](https://raw.githubusercontent.com/IlyaRice/RAG-Challenge-2/main/src/tables_serialization.py "https://raw.githubusercontent.com/IlyaRice/RAG-Challenge-2/main/src/tables_serialization.py"))
    

**Внедрять как v1.5/v2:**

1. **Pre-execution validator** — но не для всего пайплайна, а только для agentic escalation path.
    
2. **Dynamic context selector** — как отдельный сжимающий модуль между candidate retrieval и final answerer.
    
3. **Composite legal tools** — не SDK-style, а retrieval primitives более высокого уровня. ([GitHub](https://github.com/IlyaRice/Enterprise-RAG-Challenge-3-AI-Agents "https://github.com/IlyaRice/Enterprise-RAG-Challenge-3-AI-Agents"))
    

	**Не тащить в baseline как есть:**

4. full multi-agent store/orchestrator architectures;
    
5. competition-specific API abstractions;
    
6. длинные internal CoT как часть боевого ответа.  
    В нашем challenge reasoning можно держать только как debug artifact, а наружу нужен короткий, grounded output и чистые page refs. ([GitHub](https://raw.githubusercontent.com/IlyaRice/RAG-Challenge-2/main/src/prompts.py "https://raw.githubusercontent.com/IlyaRice/RAG-Challenge-2/main/src/prompts.py"))
    


## Мой итоговый вердикт

Самые “блестящие” идеи для нас здесь — это не “агенты”, а четыре вещи:

**(1)** сериализация таблиц в независимые retrieval blocks;  
**(2)** жёсткая валидация и сжатие support pages;  
**(3)** разложение сравнительных вопросов на параллельные подзадачи;  
**(4)** versioned configs + traces + consistency testing как способ не развалить систему под дедлайн.