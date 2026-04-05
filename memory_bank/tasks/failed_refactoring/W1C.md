# Task: W1C Working Journal

**Spec:** [SPEC_W1C.md](../specs/SPEC_W1C.md)

## Working Notes

- Scope is frozen by `../../.apm/worktrees/REF-PLANS/src/providers/migration-plan.md`.
- Provider internals are split into `transport.py`, `prompts.py`, `schema_adapter.py`, `response_parser.py`, `retry.py`, `factory.py`, `codex_free_text.py`, and `codex_structured.py`.
- Downstream wiring now consumes provider protocols or explicit factories in ingestion, answering, submission, and CLI composition.
- Added smoke coverage for structured answering and ingestion semantic-table extraction, both with runtime-log assertions on provider boundaries.
- The authoritative Memory Bank chain is `memory_bank/ARCHITECTURE.md -> memory_bank/component_design.md -> memory_bank/specs/ -> memory_bank/tasks/`; there is no separate `memory_bank/design/` layer in this repo.
- `memory_bank/STATE.md` now repeats that governance chain so the compact project state stays consistent with the architecture docs.

## Review Findings

- [P1] The staged W1C surface depended on untracked build/runtime files such as `pyproject.toml`, `uv.lock`, and the new `src/common/{config_loader,config_models,paths}.py` modules. Resolved by staging those dependency files so the indexed W1C state is closure-ready.
- [P2] Submission wiring still hardcoded structured capability instead of deriving it from the actual provider. Resolved by passing the real provider instance into answering and adding a submission-path regression for a free-text-only factory/provider.
- [P2] The Memory Bank docs still needed a formal chain for the missing `memory_bank/design/` layer. Resolved by documenting `memory_bank/ARCHITECTURE.md -> memory_bank/component_design.md -> memory_bank/specs/` and `memory_bank/tasks/` as the authoritative chain.
- [P2] The answering regression still referenced the removed `_LazyProvider` wrapper after the submission path moved to direct provider injection. Resolved by switching the regression to a direct free-text-only provider stub so it validates the real capability contract.
- [P2] The compact Memory Bank state was still not repeating the same governance chain, so the docs were not fully self-consistent yet. Resolved by adding the same chain to `memory_bank/STATE.md`.

## Outcome

**Result:** Completed
**Key findings:** Provider refactor is isolated behind stable protocols and factories, submission routing now respects provider capability, and the Memory Bank audit chain is explicit and repeated in `STATE.md`.
**Next action:** None for W1C; the indexed state is closure-ready for this task path after staging the dependency and provider split files.
