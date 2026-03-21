# TASK-W3A review-fixes

## Metadata + Exact Request
- Logged at: 21-03-2026 11:29
- Agent identity: Leo
- Task: TASK-W3A
- Branch / worktree: `.apm/worktrees/TASK-W3A`
- Scope: Apply quality-gate changes-required findings inside the W3A worktree and re-verify with worktree-local imports.
- Exact user request or delegated objective:
  > Replace the dummy indexing baseline with a real Qwen3/BM25-shaped contract, fix chunk-context preservation and add regressions, remove the process-wide portalocker monkeypatch, avoid main.py work, and verify with `PYTHONPATH=$PWD`.

## Task Setup
- Context used:
  - existing `src/indexing/service.py`
  - `tests/test_indexing_service.py`
  - `memory_bank/tasks/TASK-W3B.md`
- Constraints:
  - own only W3A code/tests in the worktree
  - no Memory Bank updates
  - no main.py edits
  - verification must use worktree-local import resolution
- Planned approach:
  - refactor the indexing baseline to expose a Qwen3-oriented dense path and BM25 sparse contract
  - fix heading carryover and unnumbered-clause synthesis
  - remove lock monkeypatching and make tests use safe client lifetimes

## Implementation Log
1. Replaced the placeholder embedding baseline with `Qwen3DenseEmbedder`, a lazy local-only `sentence-transformers` path for `Qwen/Qwen3-Embedding-0.6B`.
2. Replaced the ad hoc sparse encoder with `BM25SparseEncoder`, including manifest metadata (`scheme`, `k1`, `b`, `average_document_length`, vocabulary size) and payload metadata (`token_count`, `bm25_terms`) for W3B.
3. Refactored chunk building to preserve last-seen headings across continuation pages by carrying a rolling `HeadingContext` per document.
4. Reworked unnumbered clause synthesis to operate on real non-heading paragraphs, preserving the first real paragraph instead of dropping it.
5. Removed the runtime `portalocker` monkeypatch entirely. Updated the W3A tests to open/close embedded Qdrant clients safely and added regressions for:
   - continuation-page heading carryover
   - first-paragraph preservation for synthesized clauses

## Verification
- `PYTHONPATH=$PWD /home/xeliaray/Projects/Agentic-RAG-Challenge/.venv/bin/pytest tests/test_indexing_service.py`
- Result: `11 passed`
- `PYTHONPATH=$PWD /home/xeliaray/Projects/Agentic-RAG-Challenge/.venv/bin/pytest tests/test_indexing_service.py tests/test_config.py tests/test_ingestion_corpus_builder.py`
- Result: `20 passed`

## Issues / Resolutions
- Issue: the previous implementation depended on dummy embedding/sparse baselines that were not suitable as a retrieval contract.
- Resolution: replaced them with explicit Qwen3/BM25-oriented product contracts while keeping test monkeypatchability intact.
- Issue: the previous lock workaround globally patched `portalocker`.
- Resolution: removed it from runtime code and made tests respect Qdrant local-mode locking by avoiding overlapping client lifetimes.
- Residual risk: non-test runs now require the Qwen3 embedding model to be available locally; the service raises a clear runtime error instead of silently falling back to a dummy embedder.

## Artifacts
- Files touched:
  - `src/indexing/service.py`
  - `tests/test_indexing_service.py`
  - `logs/agents/TASK-W3A/TASK-W3A_Leo_review-fixes_11-29_21-03-2026.md`
- Reports, plots, logs, or other evidence:
  - worktree-local pytest results recorded above
- Verification artifacts:
  - passing `PYTHONPATH=$PWD` pytest runs

## Result / Conclusions (Exact Answer to User)
> TASK-W3A review findings were fixed in the worktree. The indexing service now exposes the intended Qwen3/BM25-shaped contract, preserves heading context and first-paragraph content correctly, no longer monkeypatches locking semantics, and the requested verification passes with `PYTHONPATH=$PWD`.
