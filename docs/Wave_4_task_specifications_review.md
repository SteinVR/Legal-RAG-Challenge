## Замечания к Wave 4 task specifications


**1. Embedding quality review для новых chunk families не закреплён явно.**
Архитектурный документ (секция 6, стр. 283) говорит: "enriched chunk families such as semantic tables and clause chunks should trigger an explicit embedding-quality review before the architecture is considered stable." W4D не упоминает проверку embedding quality для новых типов чанков.

W4D должен включить в acceptance criteria: "Evaluate embedding quality on chunk families accepted from W4C. If the current embedding model degrades on semantic table or clause chunks, document the degradation and flag for resolution."


---

**2. 20 формулировок с неопределённостью ("may", "optional", "when available", "preferred", "where needed", "or") требуют замены на конкретные решения.**

Полный перечень по файлам:

#### TASK-W4A

**2.1** Строка 7: *"It may consume retrieval outputs from the current baseline stack and from later Wave 4 retrieval work"*

- Проблема: "may consume" — потребляет или нет?
- Решение: **Потребляет.** Формулировка: "It consumes retrieval outputs from the current baseline stack initially, and from TASK-W4D retrieval once that contract stabilizes."
- Обоснование: W4A определяет page-attribution contract. Этот contract оперирует над retrieval output — он обязан его потреблять, иначе не может работать.

**2.2** Строка 78: *"May start immediately against the current baseline retrieval/answering flow."*

- Проблема: "May start" — планирование или возможность?
- Решение: **"Starts immediately..."**
- Обоснование: Dependency section прямо говорит "none for start". Это не "может", это "стартует". Убрать неопределённость.

**2.3** Строка 108: *"Implement or specify suppression heuristics for title pages and repeated boilerplate."*

- Проблема: "or specify" — код или документ?
- Решение: **"Implement suppression heuristics..."**
- Обоснование: TASK-W4A — code task с unit test coverage и ablations. Спецификация без реализации не удовлетворяет acceptance criteria.

#### TASK-W4B

**2.4** Строка 49: *"ordered or unordered multi-name outputs where relevant"*

- Проблема: "where relevant" — когда relevant, когда нет?
- Решение: **"multi-name outputs as unordered lists"**
- Обоснование: `names` answer type ожидает list. Exact match в scoring не зависит от порядка. Unordered — единственный корректный выбор. Убрать "where relevant".

**2.5** Строка 57: *"Query-side legal entities are available to retrieval as optional soft guidance."*

- Проблема: "optional" — фича поставляется или можно пропустить?
- Решение: **"...as soft (non-blocking) guidance."** Убрать "optional".
- Обоснование: Legal-entity prefilters — обязательный deliverable W4B (in-scope, стр. 94-95). "Soft" означает, что retrieval не обязан блокировать результаты при отсутствии entity match — это свойство signal design, не опциональность фичи.

**2.6** Строка 78: *"May start in parallel with TASK-W4A and TASK-W4C."*

- Решение: **"Starts in parallel..."**
- Обоснование: Dependencies = none for start.

**2.7** Строка 102 (Implementation Plan): *"Integrate legal-prefilter signals as optional soft guidance."*

- Решение: **"...as soft (non-blocking) guidance."**
- Обоснование: То же, что 6.5.

#### TASK-W4C

**2.8** Строка 28: *"raw table objects and linked context when available"*

- Проблема: "when available" — когда именно available?
- Решение: **"raw table objects and linked context from parser output (null if parser does not provide)"**
- Обоснование: opendataloader-pdf hybrid mode выдаёт linked context (captions, preceding/following text). Sidecar обязан хранить это поле. Если конкретный парсер не выдал — поле null. Это data-conditional presence, не feature optionality.

**2.9** Строка 32: *"heading/section path when known"*

- Решение: **"heading/section path from parser output (null if not detected)"**
- Обоснование: Та же логика, что 6.8. Поле в schema обязательно, значение условно.

**2.10** Строка 33: *"optional table-context roles"*

- Проблема: "optional" — role annotations включаются или нет?
- Решение: **Убрать "optional". Формулировка: "block role annotations (heading, clause, annex, footnote, table-context)"**
- Обоснование: W4C normalization производит typed blocks. Role annotations — это то, ради чего нормализация существует. Если они "optional", нормализация бессмысленна.

**2.11** Строка 41: *"Use opendataloader-pdf hybrid mode as the preferred born-digital/layout-complex path when infra is healthy."*

- Проблема: "when infra is healthy" — нет определения healthy.
- Решение: **"Hybrid mode is the required path for born-digital/layout-complex pages. If the Docling backend is unreachable at parse time, fall back to local-only mode and log a degradation warning."**
- Обоснование: "Healthy infra" — это бинарная проверка: Docling endpoint отвечает или нет. Health check должен быть в коде, а не в prose.

**2.12** Строка 43: *"Use tagged structure-tree extraction as a distinct fast path when available."*

- Проблема: "when available" — когда?
- Решение: **"...for PDFs that contain a valid structure tree (auto-detected by parser)."**
- Обоснование: opendataloader-pdf с `use_struct_tree=True` проверяет наличие structure tree. Это runtime detection, не external condition.

**2.13** Строка 45: *"Use table_method='cluster' as the preferred table experiment baseline."*

- Проблема: "preferred" — required или нет?
- Решение: **"Use table_method='cluster' as the required table method."**
- Обоснование: По vendor benchmarks, border-based (default) значительно слабее cluster на таблицах. На наших warmup PDFs 0 parse failures — нет причин использовать default. Если cluster вызовет regression на конкретных PDFs, это bug в рамках W4C, а не повод откатываться на default.

**2.14** Строка 81: *"May start in parallel with TASK-W4A and TASK-W4B."*

- Решение: **"Starts in parallel..."**
- Обоснование: Dependencies = none for start.

#### TASK-W4D

**2.15** Строка 5 (About): *"...and optional structural artifacts."*

- Проблема: "optional" — артефакты из W4C потребляются или нет?
- Решение: **"...and structural artifacts accepted from W4C."**
- Обоснование: W4D потребляет ровно то, что W4C приняло через benchmark gate. Это не optional — это dependency на W4C acceptance. Если W4C ничего не принял, W4D работает с существующими chunk families.

**2.16** Строка 27: *"retrieval budgets by question class where needed"*

- Проблема: "where needed" — для каких question classes?
- Решение: **"retrieval budgets for each question class (case, statute, cross_case, free_text)"**
- Обоснование: Baseline прямо показывает: case/statute over-retrieve (2.2-2.4x vs gold), cross_case under-retrieves (1.94 vs 2.35 gold). Asymmetric tuning — обязательная часть W4D. Бюджеты определяются для каждого class, а не "where needed".

**2.17** Строка 69: *"Depends on any chunk/schema enrichments accepted from TASK-W4C."*

- Решение: **"Depends on the chunk families and schema enrichments that W4C freezes as accepted."**
- Обоснование: "any" подразумевает неопределённость. W4C обязан зафиксировать что он отдаёт (freeze) до приёмки W4D. Dependency конкретная: frozen output of W4C.

**2.18** Строка 102 (Implementation Plan): *"Integrate legal-prefilter signals as optional soft guidance."*

- Решение: **"...as soft (non-blocking) guidance."**
- Обоснование: То же, что 6.5 и 6.7.

#### TASK-W4E

**2.19** Строка 57: *"amendment-vs-current style questions when present"*

- Проблема: "when present" — есть они в warmup set или нет?
- Решение: **"amendment-vs-current style questions (verify presence in warmup gold set; add synthetic test cases if absent)"**
- Обоснование: Regression slice либо покрывает тип вопросов, либо нет. "When present" — это не acceptance criterion. Если таких вопросов нет в warmup — создать synthetic cases для unit/integration coverage, чтобы decomposition для этого типа была протестирована.

**2.20** Строка 111 (Outcome): *"Use as an optional escalation path..."*

- Проблема: "optional" — escalation path поставляется или нет?
- Решение: **"Use as a selective escalation path..."**
- Обоснование: Decomposition — обязательный deliverable W4E. "Selective" означает: не для всех вопросов, только для тех, где trigger policy срабатывает. "Optional" ошибочно подразумевает, что фичу можно не поставить.

#### TASKS.md Wave 4 header

**2.21** Строка 30: *"TASK-W4A, TASK-W4B, and TASK-W4C may begin in parallel"*

- Решение: **"...start in parallel"**
- Обоснование: Dependency graph прямо показывает: три задачи без входных зависимостей.

---

### Суммарная статистика

| Категория | Кол-во | Решение |
|---|---|---|
| "may" → "starts/consumes" | 6 | Конкретный глагол |
| "optional" на обязательных фичах | 4 | Убрать "optional", фича обязательна |
| "when available/known/present" | 4 | Конкретное условие или null-поведение |
| "preferred" → "required" | 1 | cluster table method required |
| "where relevant/needed" | 2 | Убрать, перечислить конкретные случаи |
| "or" без выбора | 1 | Implement (не specify) |
| "any" без определённости | 1 | Frozen output of W4C |
| Неопределённость scope | 2 | annex/schedule chunks — out of scope Wave 4; XY-Cut++ calibration — out of scope Wave 4 |

**Всего: 21 двусмысленность, все с конкретными решениями.**