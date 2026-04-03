# Migration Plan: `src/retrieval`

## Goal and non-goals

### Goal
- Turn retrieval into a cleanly layered stage that separates search backend access, rank fusion, reranking, evidence compression, page grounding, and budget policy.
- Preserve page-grounded outputs while removing hidden heuristics embedded in large helper clusters.
- Upgrade observability so retrieval emits mandatory boundary logs in normal runs, not only in debug mode.

### Non-goals
- Do not change index artifact ownership or chunk taxonomy inside retrieval.
- Do not move answering-specific page attribution behavior into retrieval.
- Do not preserve debug-only observability for critical retrieval steps.

## Current boundary map
- `service.py` owns orchestration, question-class budget routing, parent-page expansion, and unanswerable handling.
- `hybrid_search.py` mixes Qdrant backend behavior, manifest loading, rank fusion, query metadata boosts, and normalization helpers.
- `reranker.py` mixes backend loading, scoring math, and fallback policy.
- `evidence_compressor.py` and `page_lifter.py` are already more focused and should stay specialized.

## Target module split
- `contracts.py`: `RetrievedChunk`, `RetrievalResult`, and retrieval-local protocols.
- `budget_policy.py`: question-class routing, candidate budgets, parent-page expansion policy, and explicit unanswerable thresholds.
- `backend.py`: Qdrant hybrid search backend and artifact loading.
- `fusion.py`: reciprocal-rank-fusion and other ranking-combination logic.
- `reranker.py`: reranker orchestration only; backend/model loading moves into `reranker_backend.py` if needed during implementation.
- `evidence_compressor.py`: keep specialized compressor behavior.
- `page_grounding.py`: page lifting/grouping logic, replacing the narrower naming of `page_lifter.py`.
- `service.py`: orchestration only.

## Migration steps
1. Move retrieval-local contracts and protocols into `contracts.py`.
2. Split `hybrid_search.py` into `backend.py` and `fusion.py`; keep query metadata boost logic with the backend layer, not with service orchestration.
3. Extract question-class budgets, parent-page expansion, and explicit unanswerable policy into `budget_policy.py`.
4. Narrow `reranker.py` so model/backend loading is separate from rerank orchestration and fallback selection.
5. Rename or wrap `page_lifter.py` as `page_grounding.py` so the module name matches the contract it owns.
6. Reduce `service.py` to stage composition using typed contracts only.
7. Add mandatory non-debug logs at every stage boundary.

## Contracts to preserve and change

### Preserve
- `RetrievalService.retrieve` remains the main entrypoint until submission and answering are migrated.
- `RetrievalResult`, evidence chunk payload semantics, and grouped page references remain stable for downstream consumers.
- Hybrid dense+sparse search and rerank-first retrieval remain the required runtime behavior.

### Change
- Budget policy becomes an explicit module instead of helper logic buried in `service.py`.
- Rank fusion is separated from backend access.
- Retrieval logging becomes mandatory and symmetric in normal runs.

## Logging and typing checklist
- Mandatory non-debug logs: `retrieval.start`, `retrieval.search.start`, `retrieval.search.complete`, `retrieval.rerank.start`, `retrieval.rerank.complete`, `retrieval.compress.start`, `retrieval.compress.complete`, `retrieval.grounding.complete`, `retrieval.complete`, `retrieval.failed`.
- Replace mixed payload dictionaries with typed wrappers wherever the retrieval boundary is stable.
- Keep query metadata usage explicit and typed; do not pass optional heuristic fields around as unstructured dicts.

## Verification
- Run retrieval smoke queries for representative question classes and inspect retrieved pages, reranked candidates, compressed evidence, and final grouped references.
- Inspect runtime logs from a normal run and confirm all boundary events are emitted without enabling debug mode.
- Run retrieval-focused tests plus one downstream answering integration smoke.

## Acceptance criteria
- Search backend, fusion, reranking, evidence compression, grounding, and budget policy are separated modules.
- `service.py` is orchestration-only.
- Retrieval emits normal-run boundary logs and keeps downstream page-grounded outputs stable.

## Risks and rollback
- The main risk is changing ranking behavior while moving helpers out of `service.py` and `hybrid_search.py`. Roll back by diffing candidate order and grouped grounding output against the pre-migration baseline.
- The second risk is over-typing unstable payloads too early. Introduce typed wrappers only at stable seams first, then tighten internal helpers after the stage is green.
