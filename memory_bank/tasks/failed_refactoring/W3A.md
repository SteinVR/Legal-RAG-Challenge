# Task: W3A Working Journal

**Spec:** [SPEC_W3A.md](../specs/SPEC_W3A.md)

## Working Notes

- Scope is frozen by `../../.apm/worktrees/REF-PLANS/src/retrieval/migration-plan.md`.
- Retrieval must keep hybrid search, reranking, compression, and page grounding behavior stable while making budgets and fusion explicit modules.
- Hidden ranking drift is the main risk, especially when splitting backend access from rank fusion and rerank orchestration.
- Verification should inspect candidate ordering, grouped references, and the mandatory non-debug retrieval logs from a normal run.

## Review Findings

- P1: W3A split was not implemented initially. Resolved by extracting `contracts.py`, `backend.py`, `fusion.py`, `budget_policy.py`, and `page_grounding.py`, then narrowing `service.py`, `hybrid_search.py`, `reranker.py`, and `page_lifter.py` to orchestration or compatibility wrappers.
- P1: normal-run retrieval boundary logs were missing. Resolved by emitting unconditional `retrieval.start`, `retrieval.search.start/complete`, `retrieval.rerank.start/complete`, `retrieval.compress.start/complete`, `retrieval.grounding.complete`, `retrieval.complete`, and `retrieval.failed` events at the stage boundaries.
- P1: closure evidence was missing. Resolved by adding the retrieval regression smoke in `tests/test_retrieval_service_regressions.py` and by running the downstream answering smoke plus an explicit retrieval log audit during verification.
- P2: `component_design.md` still showed the old retrieval topology. Resolved by updating the retrieval section to the split-module layout.
- P2: `tests/test_retrieval_components.py` still patched the old reranker module path. Resolved by switching the deterministic backend monkeypatch to `src.retrieval.reranker_backend.snapshot_download` so the test stays cache-independent after backend extraction.
- P2: `memory_bank/ARCHITECTURE.md` still described retrieval as a five-module monolith. Resolved by updating the top-level architecture summary to the split retrieval topology and pointing detailed ownership to `component_design.md`.

## Outcome

**Result:** Ready for closure
**Key findings:** Retrieval now follows the split topology from the migration plan, with stage logging and page-grounded evidence preserved, and the normal-run log order is explicitly covered by smoke checks.
**Next action:** None unless a new reviewer finds a regression.

## Verification

- `./.venv/bin/python -m py_compile src/retrieval/contracts.py src/retrieval/page_grounding.py src/retrieval/budget_policy.py src/retrieval/backend.py src/retrieval/fusion.py src/retrieval/reranker_backend.py src/retrieval/reranker.py src/retrieval/evidence_compressor.py src/retrieval/service.py src/retrieval/__init__.py tests/test_retrieval_service_regressions.py` passed.
- `./.venv/bin/python -m ruff check src/retrieval tests/test_retrieval_service_regressions.py` passed after auto-fixing import ordering and the unused test import.
- `./.venv/bin/pytest -q tests/test_retrieval_components.py tests/test_retrieval_service_regressions.py` passed with `8 passed in 2.85s`.
- `./.venv/bin/python -m ruff check tests/test_retrieval_components.py` passed after switching the monkeypatch path.
- `./.venv/bin/pytest -q tests/test_retrieval_components.py` passed with `5 passed in 2.76s`.
- `./.venv/bin/pytest -q tests/test_retrieval_components.py::test_transformers_qwen_backend_uses_causal_lm_yes_no_scoring` passed with `1 passed in 2.85s`.
- `./.venv/bin/pytest -q tests/test_answering_service_regressions.py::test_answering_service_uses_structured_provider_path_and_logs_boundaries` passed with `1 passed in 0.63s`.
- Retrieval log audit was performed through `tests/test_retrieval_service_regressions.py`, which asserts the exact normal-run event order and the absence of `retrieval.failed`.
