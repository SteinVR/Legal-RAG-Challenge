# SPEC: TASK-AR-GROUNDING-01 -- Autoresearch Grounding Cycle

**Wave:** AR-1 | **Depends on:** -- | **Blocks:** --

## Goal

Запустить непрерывный autoresearch-цикл для максимизации `grounding_mean` на `warmup100` без использования OpenAI/API и без деградации GPU-runtime контракта.

## Pipeline

1. `scripts/autoresearch_grounding_runner.py` загружает `questions.json` и benchmark references.
2. Перед оценкой runner выполняет GPU preflight для Qwen query embedder и Qwen reranker (CUDA-only).
3. Для каждого вопроса выполняется retrieval (`RetrievalService`) c query metadata.
4. Финальные страницы для grounding вычисляются через Pass A page attribution (`candidate_pages_from_chunks` -> `prune_candidate_pages`).
5. Grounding на вопрос считается локальной функцией `score_grounding` по парам `(doc_id, page_number)`.
6. Runner агрегирует метрики (`grounding_mean`, `grounding_zero_count`, `runtime_sec`) и печатает greppable строку для autoresearch loop.
7. Autoresearch loop фиксирует результат в `results.tsv`, делает keep/discard по objective, и повторяет цикл до ручной остановки.

## Contracts

| Interface | Location | Owner |
|-----------|----------|-------|
| Retrieval-only grounding runner CLI (`--config`, `--env-file`, `--questions-path`, `--benchmark-path`, `--phase`) | `scripts/autoresearch_grounding_runner.py` | TASK-AR-GROUNDING-01 |
| Greppable metric output (`AUTORESEARCH_METRIC grounding_mean=... grounding_zero_count=... runtime_sec=...`) | `scripts/autoresearch_grounding_runner.py` stdout | TASK-AR-GROUNDING-01 |
| Autoresearch results tracking (`results.tsv` untracked) | repo root | TASK-AR-GROUNDING-01 |

## Frozen Decisions

| Decision | Value |
|----------|-------|
| Workflow | Strict `$apm-autoresearch` keep/discard loop |
| Objective | `grounding_mean` maximize |
| Runner mode | Retrieval-only benchmark (no Answering/API) |
| In-scope edits | `src/retrieval/**`, `src/answering/page_attribution.py`, retrieval/page-attribution config, runner script |
| Read-only | `src/evaluation/**`, `src/submission/**`, `src/providers/**`, `memory_bank/**` during loop |
| GPU contract | Mandatory CUDA runtime for retrieval models |
| Time budget rule | Budget = baseline runtime runner; crash if run > 2x baseline |
| Regression gate | Metric-only gate (per user decision) |

## Output

- `memory_bank/specs/SPEC_TASK-AR-GROUNDING-01.md`
- `memory_bank/tasks/TASK-AR-GROUNDING-01.md`
- `scripts/autoresearch_grounding_runner.py`
- `results.tsv` (untracked, not committed)

## Definition of Done

- [ ] Retrieval-only runner стабильно считает grounding на `warmup100` без OpenAI/API вызовов
- [ ] Runner hard-fail'ит при нарушении GPU contract
- [ ] `AUTORESEARCH_METRIC` строка пригодна для автоматического парсинга в autoresearch loop
- [ ] Baseline run записан в `results.tsv` как стартовая точка
- [ ] Follow-up эксперименты используют keep/discard через `keep_ref`

