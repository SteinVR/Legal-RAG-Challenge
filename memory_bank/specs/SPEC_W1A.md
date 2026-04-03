# SPEC: W1A — [Title]

**Wave:** 1 | **Depends on:** — | **Blocks:** —

## Goal

[1-2 sentences: what to build and why. Concrete — no "may", "optional", or deferred decisions.]

## Pipeline

[How the feature/module functions: sequence, data flow, processing order. Not an implementation plan — describes the runtime behavior.]

1. [Step with exact module, e.g. `src/core/auth.py` — validate session token]
2. ...

## Contracts

| Interface | Location | Owner |
|-----------|----------|-------|
| [e.g. SessionStore] | [e.g. src/contracts/auth.py] | [Owner TASK_ID] |

> Cross-task Protocol/dataclass definitions. If no cross-task contracts exist, leave empty.

## Frozen Decisions

| Decision | Value |
|----------|-------|
| [e.g. Auth mechanism] | [e.g. JWT with RS256] |

## Output

- [Expected artifact paths, e.g. `src/core/auth.py`, `tests/test_auth.py`]

## Definition of Done

- [ ] [Concrete, verifiable criterion]
- [ ] All contract interfaces implemented and type-checked
- [ ] Verification passing
- [ ] Results committed to git

---

> This template contains core sections. Task-specific sections (e.g., VRAM Budget, Metrics, External Integration) may be added as needed.
