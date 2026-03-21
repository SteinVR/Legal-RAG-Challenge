# TASK-W3A w3a-test-contract

## Metadata + Exact Request
- Logged at: 21-03-2026 10:59
- Agent identity: Ivan
- Task: TASK-W3A
- Branch / worktree: `.apm/worktrees/TASK-W3A`
- Scope: Write exhaustive TDD tests first for Wave 3A service-only indexing/chunking behavior, without implementing product logic.
- Exact user request or delegated objective:
  > Write exhaustive TDD tests first for W3A only. Own tests/ coverage and any test-only support; do not implement product logic, do not do git/worktree operations, do not update Memory Bank. Public surface for Wave 3 is service-only; do not require new CLI commands or main.py changes. Use the shared virtualenv at /home/xeliaray/Projects/Agentic-RAG-Challenge/.venv when running verification. After writing tests, run the most relevant targeted pytest command from this worktree, make sure failures are due to missing/incorrect implementation rather than broken tests, and return: changed files, pytest command, failure summary, and the concrete behavior contract the engineer must satisfy.

## Task Setup
- Context used:
  - `memory_bank/ARCHITECTURE.md`
  - `memory_bank/TASKS.md`
  - `memory_bank/tasks/TASK-W3A.md`
  - `tests/AGENTS.md`
  - Existing service-style tests under `tests/test_ingestion_service.py`
  - Current empty `src/indexing/` package
- Constraints:
  - Tests only; no product implementation
  - Service-only public surface
  - No git/worktree operations
  - No Memory Bank edits
  - Verification must use shared `.venv`
- Planned approach:
  - Freeze a concrete W3A service contract via tests
  - Reuse W2C corpus artifacts as realistic inputs
  - Validate that failures point to missing indexing implementation rather than fixture/test defects

## Implementation Log
1. Inspected task docs, architecture, roadmap notes, and existing service/test conventions.
2. Added `tests/test_indexing_service.py` covering:
   - package re-exports
   - missing-input guardrails
   - dry-run behavior
   - persisted hybrid Qdrant index contract
   - exact page-parent mapping
   - cache skip/rebuild behavior
   - source-corpus invalidation
   - page-map mismatch rejection
   - result formatting
3. Ran targeted pytest with the shared `.venv` and confirmed the failures are implementation gaps only.

## Verification
- Checks run:
  - `/home/xeliaray/Projects/Agentic-RAG-Challenge/.venv/bin/python -m pytest tests/test_indexing_service.py -q`
- Result:
  - Suite executed successfully and failed only on missing `src.indexing.service` and missing `src.indexing` re-exports.

## Issues / Resolutions
- Issue:
  - W3A indexing surface does not exist yet (`src/indexing/__init__.py` is empty and `src/indexing/service.py` is absent).
- How it was resolved or what remains open:
  - Tests were written to fail explicitly on that missing surface first, while also freezing the required runtime/indexing behavior the implementation must satisfy next.

## Artifacts
- Files touched:
  - `tests/test_indexing_service.py`
  - `logs/agents/TASK-W3A/TASK-W3A_Ivan_w3a-test-contract_10-59_21-03-2026.md`
- Reports, plots, logs, or other evidence:
  - Agent log at `logs/agents/TASK-W3A/TASK-W3A_Ivan_w3a-test-contract_10-59_21-03-2026.md`
- Verification artifacts:
  - Pytest failure output showing 9 failures rooted in missing indexing module/export surface

## Result / Conclusions (Exact Answer to User)
> TASK-W3A is in a clean TDD-red state. I added an exhaustive service-level W3A test contract in `tests/test_indexing_service.py` and verified it with `/home/xeliaray/Projects/Agentic-RAG-Challenge/.venv/bin/python -m pytest tests/test_indexing_service.py -q`. The run failed only because `src.indexing.service` and the `src.indexing` public re-exports do not exist yet, which confirms the failures are due to missing implementation rather than broken tests. The engineer now needs to implement a service-only indexing surface that provides `HybridIndexService`, `BuildIndexResult`, and `format_build_index_result`, persists a local Qdrant hybrid index plus exact `page_parent_map`, enforces corpus/page-map consistency, and supports dry-run, skip, and rebuild invalidation behavior as defined by the new tests.
