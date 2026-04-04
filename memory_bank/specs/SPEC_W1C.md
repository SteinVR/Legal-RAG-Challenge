# SPEC: W1C -- Refactor `src/providers`

**Wave:** 1 | **Depends on:** W1A | **Blocks:** W2A, W3B, W4A

## Goal

Refactor `src/providers` into a clean abstraction layer with separate protocol, transport, prompt-building, schema adaptation, retry, and response parsing modules while preserving fail-fast provider semantics. Detailed implementation guidance lives in `../../.apm/worktrees/REF-PLANS/src/providers/migration-plan.md`.

## Pipeline

1. Keep `base.py` as the protocol seam and extract transport, prompts, schema adaptation, retry, and parsing into focused modules.
2. Split concrete Codex implementations by responsibility instead of keeping one mixed implementation file.
3. Rewire downstream stages so they depend on provider protocols or factories rather than concrete provider internals.

## Contracts

| Interface | Location | Owner |
|-----------|----------|-------|
| `FreeTextProvider`, `StructuredOutputProvider` | `src/providers/base.py` | W1C |
| Transport, retry, schema, and parsing helpers | `src/providers/transport.py`, `src/providers/retry.py`, `src/providers/schema_adapter.py`, `src/providers/response_parser.py` | W1C |
| Stable concrete provider entrypoints | `src/providers/codex_free_text.py`, `src/providers/codex_structured.py` | W1C |

## Frozen Decisions

| Decision | Value |
|----------|-------|
| Reference plan | `../../.apm/worktrees/REF-PLANS/src/providers/migration-plan.md` |
| Provider contract | Downstream stages depend on protocols or factories, not deep concrete-class knowledge |
| Error policy | Provider/schema/transport contract breaks stay explicit and fail fast |

## Output

- `src/providers/transport.py`
- `src/providers/prompts.py`
- `src/providers/schema_adapter.py`
- `src/providers/response_parser.py`
- `src/providers/retry.py`
- `src/providers/codex_free_text.py`
- `src/providers/codex_structured.py`
- Narrowed `src/providers/__init__.py`

## Definition of Done

- [ ] Provider abstractions and extracted modules match the `src/providers` migration plan
- [ ] Downstream answering, ingestion, submission, and CLI code use provider protocols or explicit factories
- [ ] Structured and free-text provider smoke paths preserve schema strictness, retry semantics, and confidence parsing
- [ ] Mandatory provider runtime logs are emitted on normal runs
- [ ] All contract interfaces implemented and type-checked
- [ ] Verification passing
- [ ] Results committed to git
