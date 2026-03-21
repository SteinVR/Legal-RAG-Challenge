# [TASK-W3C] [answering-service]

## Metadata + Exact Request
- Logged at: 21-03-2026 11:03
- Agent identity: Leo
- Task: TASK-W3C
- Branch / worktree: `TASK-W3C` worktree at `/home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/TASK-W3C`
- Scope: Implement the W3C answering service and provider contract in `src/answering` and `src/providers` against `tests/test_answering_service.py`, then run broader relevant verification.
- Exact user request or delegated objective:
  > Implement against the existing SDET red contract in `tests/test_answering_service.py` until that suite passes, then run relevant broader verification. Own product code only for W3C in `src/answering` and `src/providers`; do not do git/worktree operations, do not update Memory Bank, do not require new CLI commands or `main.py` changes.

## Task Setup
- Context used:
  - `memory_bank/ARCHITECTURE.md`
  - `memory_bank/TASKS.md`
  - `memory_bank/tasks/TASK-W3C.md`
  - `tests/test_answering_service.py`
  - `src/common/schemas.py`
  - `src/evaluation/contracts.py`
- Constraints:
  - Stay inside TASK-W3C file scope.
  - Do not modify Memory Bank files.
  - Use the shared virtualenv at `/home/xeliaray/Projects/Agentic-RAG-Challenge/.venv`.
  - Treat the SDET test as the source-of-truth spec.
- Planned approach:
  - Read the spec and surrounding contracts.
  - Implement a minimal extraction-first answering service and provider protocol.
  - Verify the target suite, then run a broader regression slice around question/answer contracts and orchestration.

## Implementation Log
1. Read the W3C task brief, architecture, evaluation contracts, and the new SDET answering test suite to establish the answer/result contract.
2. Added `src/providers/base.py` with a minimal `FreeTextProvider` protocol and exported it from `src/providers/__init__.py`.
3. Added `src/answering/service.py` implementing:
   - `AnsweringService`
   - `AnswerResult`
   - deterministic extraction-first routing for `number`, `boolean`, `name`, `names`, and `date`
   - null responses for empty or conflicting deterministic evidence
   - grounded free-text generation with a 280-character gate and date contradiction check
   - grouped `PageReference` evidence output
4. Exported the answering service surface from `src/answering/__init__.py`.
5. Tightened the number heuristic after the first green-near miss so unrelated structural numbers like `Article 2` are ignored when they have no question relevance.
6. Applied the quality-gate fix pass:
   - expanded free-text grounding checks to reject unsupported numbers, names, and outcome terms introduced by the provider
   - validated provider confidence as finite and bounded within `0.0..1.0`
   - improved numeric scoring to prefer local amount cues over nearby deadline numbers in mixed sentences
   - added regression coverage in `tests/test_answering_service.py` for all three findings
7. Applied the final quality-gate fix pass:
   - normalized written-number forms and digit forms during free-text grounding, so evidence like `five days` supports summaries using `5 days`
   - made `names` corroboration order-insensitive across pages while preserving the first stable presentation order in the returned answer
   - extended deterministic date extraction to accept ISO-formatted evidence through the existing ISO normalization path
   - added regressions for each of those cases in `tests/test_answering_service.py`
8. Applied the last product fix pass:
   - strengthened number-intent scoring so duration/time questions prefer numbers directly attached to temporal units over nearby amount values in mixed sentences
   - tightened free-text grounding to reject unsupported explanatory clauses and rationale fragments when their salient tokens are absent from the evidence
   - added regressions for both findings in `tests/test_answering_service.py`
9. Applied the final review fix pass:
   - upgraded deterministic number extraction to parse and score written-number spans directly, so questions over evidence like `within five days` now resolve to `5`
   - added polarity/state-aware contradiction checks for negation flips and salient antonym flips such as `did not dismiss` vs `dismissed` and `contract was valid` vs `contract was void`
   - calendar-validated ISO-looking dates before accepting them, so malformed values like `2026-13-05` are ignored rather than returned
   - added regressions for all three cases in `tests/test_answering_service.py`
10. Applied the last extraction fix pass:
   - replaced raw boolean cue substring checks with phrase-boundary matching so words like `notice` and `cancellation` no longer trigger false boolean decisions
   - expanded entity extraction to include uppercase/acronym legal entities such as `ACME LTD` and `BETA LLC`
   - added regressions for boundary-safe boolean cues and uppercase entity extraction in `tests/test_answering_service.py`
11. Applied the final single-token entity fix pass:
   - added legal-role-anchored single-token entity extraction so deterministic `name` answers now capture evidence like `The respondent is ADNOC.` and `The respondent is Beta.`
   - aligned free-text grounding name validation to the same entity extraction path so unsupported single-token hallucinated names are rejected before return
   - added regressions for acronym extraction, title-case single-token extraction, and unsupported single-token name rejection in `tests/test_answering_service.py`

## Verification
- `env PYTHONPATH=$PWD /home/xeliaray/Projects/Agentic-RAG-Challenge/.venv/bin/python -m pytest -q tests/test_answering_service.py`
- Result: `36 passed in 0.20s`
- `env PYTHONPATH=$PWD /home/xeliaray/Projects/Agentic-RAG-Challenge/.venv/bin/python -m pytest -q`
- Result: `120 passed in 0.45s`
- `env PYTHONPATH=$PWD /home/xeliaray/Projects/Agentic-RAG-Challenge/.venv/bin/python -m ruff check src/answering src/providers tests/test_answering_service.py`
- Result: `All checks passed!`

## Issues / Resolutions
- Direct `pytest -q ...` import resolution was inconsistent in this environment. Final verification used `PYTHONPATH=$PWD python -m pytest ...` to force worktree-local imports as required.
- The free-text grounding validator remains heuristic rather than semantic. It now blocks unsupported factual additions in the reviewed categories, but future broader summarization coverage may still need a richer contradiction check.
- Written-number normalization is intentionally bounded to common English cardinal forms. If later waves need broader numeric language coverage, that parser should be expanded deliberately rather than inferred ad hoc.
- Clause grounding is lexical rather than entailment-based. It now blocks unsupported rationale fragments like `because the contract was void`, but later work may still want a more semantic support check.
- Polarity/state contradiction checks are rule-based around the reviewed legal predicates and contract validity states. If later waves need broader contradiction coverage, that fact inventory should be extended explicitly.
- Uppercase entity extraction is pattern-based and aimed at common legal-party formats. If later waves need richer organization-name coverage, that entity matcher should be extended with more explicit patterns rather than made looser.
- Single-token entity extraction is intentionally guarded by nearby legal-role cues to avoid turning generic capitalized words into names. If later waves need broader single-token organization coverage, extend those anchors explicitly.

## Artifacts
- Files touched:
  - `src/answering/__init__.py`
  - `src/answering/service.py`
  - `src/providers/__init__.py`
  - `src/providers/base.py`
  - `tests/test_answering_service.py`
  - `logs/agents/TASK-W3C/TASK-W3C_Leo_answering-service_11-03_21-03-2026.md`
- Reports, plots, logs, or other evidence:
  - This activity log
- Verification artifacts:
  - Passing pytest outputs for the target answering suite and the broader regression slice listed above

## Result / Conclusions (Exact Answer to User)
> TASK-W3C is complete for the requested scope, including the final single-token entity fixes. The answering service now extracts legal-role-anchored single-token entities such as `ADNOC` and `Beta`, rejects unsupported single-token name hallucinations in free-text grounding, and retains the earlier boolean, numeric, grounding, corroboration, polarity, and date-validation fixes. The requested pytest and ruff verification commands all pass with worktree-local import resolution.
