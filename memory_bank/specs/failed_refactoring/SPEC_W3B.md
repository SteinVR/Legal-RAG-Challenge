# SPEC: W3B -- Split `src/answering`

**Wave:** 3 | **Depends on:** W1A, W1C, W3A | **Blocks:** W4A

## Goal

Break `src/answering` into orchestration, schemas, metadata extraction, deterministic guardrails, solver execution, page attribution, and decomposition modules without changing schema-first typed answering semantics. The detailed migration contract is frozen in `../../.apm/worktrees/REF-PLANS/src/answering/migration-plan.md`.

## Pipeline

1. Move answer schemas, query metadata, and deterministic guardrails out of `service.py`.
2. Extract provider-facing solve logic into `solver.py` and keep page attribution and decomposition as explicit logged subsystems.
3. Reduce `service.py` to path selection and composition over typed contracts only.

## Contracts

| Interface | Location | Owner |
|-----------|----------|-------|
| `AnsweringService.answer_question` | `src/answering/service.py` | W3B |
| `AnswerResult` and answering-local protocols | `src/answering/contracts.py` | W3B |
| Answer schemas, metadata, solver, attribution, and decomposition seams | `src/answering/answer_schemas.py`, `src/answering/query_metadata.py`, `src/answering/solver.py`, `src/answering/page_attribution.py`, `src/answering/decomposition.py` | W3B |

## Frozen Decisions

| Decision | Value |
|----------|-------|
| Reference plan | `../../.apm/worktrees/REF-PLANS/src/answering/migration-plan.md` |
| Answering contract | Schema-first typed answering, two-pass page attribution, and decomposition behavior remain stable |
| Error policy | Provider/schema failures stay explicit; no silent downgrade to weaker answer paths unless the preserved contract allows it |

## Output

- `src/answering/contracts.py`
- `src/answering/answer_schemas.py`
- `src/answering/query_metadata.py`
- `src/answering/deterministic.py`
- `src/answering/solver.py`
- Narrowed `src/answering/service.py`
- Updated `src/answering/page_attribution.py`
- Updated `src/answering/decomposition.py`

## Definition of Done

- [ ] Answering module boundaries match the migration plan and `service.py` is orchestration-only
- [ ] Typed answering semantics, page traces, and decomposition behavior remain stable
- [ ] Normal-run answering logs cover solve, attribution, decomposition, completion, and failure boundaries
- [ ] Typed-answer and decomposition smoke checks plus one downstream submission smoke pass
- [ ] All contract interfaces implemented and type-checked
- [ ] Verification passing
- [ ] Results committed to git
