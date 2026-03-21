# TASK-W3C w3c-answering-contract

## Metadata + Exact Request
- Logged at: 21-03-2026 10:56
- Agent identity: Ivan
- Task: TASK-W3C
- Branch / worktree: `.apm/worktrees/TASK-W3C`
- Scope: Write exhaustive W3C tests first for the service-only answering surface, then run a targeted red pytest check.
- Exact user request or delegated objective:
  > Write exhaustive TDD tests first for W3C only. Own tests/ coverage and any test-only support; do not implement product logic, do not do git/worktree operations, do not update Memory Bank. Public surface for Wave 3 is service-only; do not require new CLI commands or main.py changes. W3C may proceed against frozen W2A/W1A and local retrieval/provider doubles where needed. Use the shared virtualenv at /home/xeliaray/Projects/Agentic-RAG-Challenge/.venv when running verification. After writing tests, run the most relevant targeted pytest command from this worktree, make sure failures are due to missing/incorrect implementation rather than broken tests, and return: changed files, pytest command, failure summary, and the concrete behavior contract the engineer must satisfy.

## Task Setup
- Context used:
  - `memory_bank/tasks/TASK-W3C.md`
  - `memory_bank/tasks/TASK-W3B.md`
  - `memory_bank/tasks/TASK-W1A.md`
  - `memory_bank/ARCHITECTURE.md`
  - `docs/about_challenge/about_challenge.md`
  - `docs/about_challenge/about_challenge_API.md`
  - `docs/about_challenge/about_challenge_EVALUATION.md`
  - `docs/Initial Roadmap.md`
  - existing `tests/` patterns and `src/common/schemas.py`
- Constraints:
  - tests only; no product implementation
  - no `main.py` / CLI expansion
  - no Memory Bank updates
  - verify with the shared `.venv`
- Planned approach:
  - derive the service contract from Wave 3 docs and frozen dependencies
  - encode the contract in a dedicated answering-service test module with local doubles
  - run a narrow pytest target and confirm failures come from missing implementation only

## Implementation Log
1. Inspected repo structure, local AGENTS instructions, and the `apm-test` / `apm-report` skill references.
2. Read the Wave 3 answering task, adjacent retrieval/provider context, architecture notes, and challenge answer/telemetry rules to freeze a service-only contract.
3. Added `tests/test_answering_service.py` with 12 red tests covering deterministic routing, normalization, null behavior, free-text generation boundaries, and self-check rejection paths using local retrieval/provider doubles.
4. Compiled the test module with `/home/xeliaray/Projects/Agentic-RAG-Challenge/.venv/bin/python -m py_compile tests/test_answering_service.py` to rule out syntax or collection defects.
5. Ran `/home/xeliaray/Projects/Agentic-RAG-Challenge/.venv/bin/pytest -q tests/test_answering_service.py` and confirmed the suite fails only because `src.answering.service` does not exist yet.

## Verification
- Checks run:
  - `/home/xeliaray/Projects/Agentic-RAG-Challenge/.venv/bin/python -m py_compile tests/test_answering_service.py`
  - `/home/xeliaray/Projects/Agentic-RAG-Challenge/.venv/bin/pytest -q tests/test_answering_service.py`
- Result:
  - compile check passed
  - pytest collected and executed 12 tests; all 12 failed with `ModuleNotFoundError: No module named 'src.answering.service'`

## Issues / Resolutions
- Issue: Wave 3 answering modules are absent in `src/answering/`.
- Resolution: wrote contract tests that import the intended module inside test helpers so pytest collection still succeeds and the red state points cleanly at the missing implementation boundary.
- Residual risk: the tests establish a provider collaborator shape of `generate(question=..., evidence_pages=..., max_chars=280)` and a retriever collaborator shape of `retrieve(question)`. If the implementer wants a different collaborator API, they must either adapt internally or renegotiate the contract.

## Artifacts
- Files touched:
  - `tests/test_answering_service.py`
  - `logs/agents/TASK-W3C/TASK-W3C_Ivan_w3c-answering-contract_10-56_21-03-2026.md`
- Verification artifacts:
  - red pytest output showing only missing `src.answering.service`

## Result / Conclusions (Exact Answer to User)
> TASK_ID: TASK-W3C is in red-test state. I added `tests/test_answering_service.py`, verified it compiles, and ran `/home/xeliaray/Projects/Agentic-RAG-Challenge/.venv/bin/pytest -q tests/test_answering_service.py`. The run fails cleanly because `src.answering.service` is missing. The implementer now needs to provide an `AnsweringService` with a service-only API that calls `retriever.retrieve(question)`, uses extraction-first deterministic solving without the provider, uses the provider only for grounded `free_text` generation with a 280-char budget, returns `question_id` / `answer` / `confidence` / `evidence_pages`, emits `None` for insufficient or conflicting deterministic evidence, emits the canonical no-information sentence for unanswerable `free_text`, normalizes number/boolean/name/names/date outputs, rejects unsupported answer types, rejects overlength free-text, and rejects free-text drafts that contradict evidence by introducing unsupported dates.
