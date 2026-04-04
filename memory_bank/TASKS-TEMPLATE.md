# Task Board (RAPID): Agentic-RAG-Challenge Refactor

> Active refactor planning is frozen in `memory_bank/specs/SPEC_{TASK_ID}.md`. Working notes live in `memory_bank/tasks/{TASK_ID}.md`. Implementation is happening in `.apm/worktrees/REF-PLANS` against the per-package `migration-plan.md` files under `src/`.

## Wave Protocol

Tasks are organized in **waves**. Waves execute sequentially; tasks within the same wave may run in parallel only when their dependencies and file ownership boundaries stay clean.

- **Naming:** `W1A`, `W1B`, `W1C`, `W2A`, etc.
- **Backlog items:** `BL-001`, `BL-002`, etc.
- A wave is complete when all its tasks pass the quality gate and are integrated.
- The next wave starts only after the current wave is fully integrated.
- New work discovered mid-wave moves into the next wave or backlog, never into the active wave.
- **SPEC freeze:** once implementation starts for a task, its spec stays frozen unless an explicit runtime escalation is recorded.

## 1. Active Plan (Ordered)

### Wave 1: Shared Foundations
- [ ] [W1A](./specs/SPEC_W1A.md) Refactor `src/common` into a narrow foundation package. [Notes](./tasks/W1A.md)
- [ ] [W1B](./specs/SPEC_W1B.md) Move config authority from `src/resources` to repo-root `configs/`. [Notes](./tasks/W1B.md)
- [ ] [W1C](./specs/SPEC_W1C.md) Split `src/providers` into protocol, transport, prompt, schema, retry, and parsing layers. [Notes](./tasks/W1C.md)
- [ ] [W1D](./specs/SPEC_W1D.md) Layer `src/evaluation` into contracts, loaders, validation, scoring, and benchmark analytics. [Notes](./tasks/W1D.md)

**Wave DoD:**
- [ ] Shared config, schema, logging, provider, and evaluation boundaries are frozen for downstream stage work.
- [ ] Repo-root `configs/...` is the only supported default config source.
- [ ] Broad `__init__.py` facades are reduced to intentional exports across shared packages.

### Wave 2: Upstream Stage Decomposition
- [ ] [W2A](./specs/SPEC_W2A.md) Refactor `src/ingestion` into orchestration, parsing workers, and artifact writing boundaries. [Notes](./tasks/W2A.md)
- [ ] [W2B](./specs/SPEC_W2B.md) Decompose `src/indexing` into chunking, embedding, sparse encoding, persistence, and manifest modules. [Notes](./tasks/W2B.md)

**Wave DoD:**
- [ ] Canonical corpus and index artifact contracts remain stable.
- [ ] `service.py` in ingestion and indexing is orchestration-only.
- [ ] Stage boundary logs are present for parse and index flows in normal runs.

### Wave 3: Retrieval and Answering Runtime
- [ ] [W3A](./specs/SPEC_W3A.md) Layer `src/retrieval` into backend, fusion, reranking, grounding, and budget policy modules. [Notes](./tasks/W3A.md)
- [ ] [W3B](./specs/SPEC_W3B.md) Split `src/answering` into schemas, metadata, deterministic guardrails, solver, attribution, and orchestration modules. [Notes](./tasks/W3B.md)

**Wave DoD:**
- [ ] Retrieval and answering keep page-grounded outputs stable.
- [ ] Retrieval and answering emit the mandatory non-debug runtime boundary logs from their migration plans.
- [ ] `service.py` stays orchestration-only in both packages.

### Wave 4: Submission Composition
- [ ] [W4A](./specs/SPEC_W4A.md) Refactor `src/submission` into explicit orchestration, dependency wiring, question execution, trace writing, validation, and packaging modules. [Notes](./tasks/W4A.md)

**Wave DoD:**
- [ ] Submission composes refactored stages only through stable entrypoints and typed contracts.
- [ ] `pipeline.py` and `src/main.py` are dispatch/orchestration-only.
- [ ] End-to-end submission smoke verification and runtime log inspection are complete.

## 2. Backlog

- [ ] [BL-001] Post-refactor full regression run: rerun the 100-question submission flow after the refactor lands on `main` and compare outputs against the latest accepted baseline.
- [ ] [BL-002] Architecture sync after merge: refresh `memory_bank/ARCHITECTURE.md` and `memory_bank/STATE.md` once the refactor is integrated and verification artifacts are final.

## 3. Review Findings (Cross-Module)

> Cross-task findings from the quality gate belong here. Task-local findings stay in the individual task journal.

| ID | Source | Severity | Summary | Status |
|----|--------|----------|---------|--------|

### Error Patterns

> Recurring refactor risks identified from the migration plans. Agents should actively check for them during implementation and review.

| Pattern | Occurrences | Example Tasks | Guidance |
|---------|-------------|---------------|----------|
| Orchestration files keep hidden business logic after extraction | 6 planned stage refactors | W2A, W2B, W3A, W3B, W4A | Keep `service.py` and `pipeline.py` as composition-only modules with typed worker seams. |
| Broad package re-exports preserve accidental coupling | 5 planned package splits | W1A, W1C, W1D, W2A, W3B | Shrink `__init__.py` to intentional public symbols and update import sites directly. |
| Silent fallback behavior survives the refactor | 6 plans call this out | W1A, W1B, W1C, W2B, W3A, W3B | Preserve fail-fast behavior for missing config, provider/schema errors, and reduced-quality runtime paths. |
