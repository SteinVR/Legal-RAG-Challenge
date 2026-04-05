# SPEC: W3A -- Layer `src/retrieval`

**Wave:** 3 | **Depends on:** W1A, W2B | **Blocks:** W3B, W4A

## Goal

Refactor retrieval into explicit backend, fusion, reranking, budget policy, evidence compression, grounding, and orchestration layers while preserving page-grounded outputs. The authoritative migration details are in `../../.apm/worktrees/REF-PLANS/src/retrieval/migration-plan.md`.

## Pipeline

1. Move retrieval-local result types and protocols into `contracts.py`.
2. Split backend access from rank fusion, make budget policy explicit, and narrow reranker and grounding modules to owned responsibilities.
3. Reduce `service.py` to typed orchestration with mandatory non-debug boundary logging.

## Contracts

| Interface | Location | Owner |
|-----------|----------|-------|
| `RetrievalService.retrieve` | `src/retrieval/service.py` | W3A |
| `RetrievedChunk`, `RetrievalResult`, retrieval-local protocols | `src/retrieval/contracts.py` | W3A |
| Search, fusion, rerank, grounding, and budget policy seams | `src/retrieval/backend.py`, `src/retrieval/fusion.py`, `src/retrieval/reranker.py`, `src/retrieval/page_grounding.py`, `src/retrieval/budget_policy.py` | W3A |

## Frozen Decisions

| Decision | Value |
|----------|-------|
| Reference plan | `../../.apm/worktrees/REF-PLANS/src/retrieval/migration-plan.md` |
| Runtime behavior | Hybrid dense+sparse search plus rerank-first retrieval remains required |
| Output stability | Grouped page references and evidence payload semantics stay stable for downstream consumers |

## Output

- `src/retrieval/contracts.py`
- `src/retrieval/backend.py`
- `src/retrieval/fusion.py`
- `src/retrieval/budget_policy.py`
- `src/retrieval/page_grounding.py`
- Narrowed `src/retrieval/reranker.py`
- Narrowed `src/retrieval/service.py`

## Definition of Done

- [ ] Retrieval backend, fusion, rerank, grounding, and budget policy seams match the migration plan
- [ ] Retrieval results remain page-grounded and downstream-compatible
- [ ] Normal-run retrieval logs cover start, search, rerank, compression, grounding, completion, and failures
- [ ] Retrieval smoke checks and one downstream answering integration smoke pass
- [ ] All contract interfaces implemented and type-checked
- [ ] Verification passing
- [ ] Results committed to git
