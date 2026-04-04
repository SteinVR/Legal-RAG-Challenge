# SPEC: W2A -- Refactor `src/ingestion`

**Wave:** 2 | **Depends on:** W1A, W1B, W1C | **Blocks:** W2B, W4A

## Goal

Keep `src/ingestion` as the canonical `PDF -> canonical corpus -> sidecars -> manifest` stage while tightening orchestration, parser-worker, and artifact-writing boundaries. The authoritative scope is frozen in `../../.apm/worktrees/REF-PLANS/src/ingestion/migration-plan.md`.

## Pipeline

1. Move ingestion-local result types into `contracts.py` and artifact persistence into `artifact_writer.py`.
2. Narrow `pdf_parser.py` to document-level orchestration that delegates routing, OCR, sidecars, and table extraction to specialized helpers.
3. Reduce package exports to the service entrypoint and stable contracts only, with explicit stage-boundary logging.

## Contracts

| Interface | Location | Owner |
|-----------|----------|-------|
| `CorpusParseService` stage entrypoint | `src/ingestion/service.py` | W2A |
| `CorpusPaths`, `ParseCorpusResult`, document parse result types | `src/ingestion/contracts.py` | W2A |
| Canonical corpus outputs (`CanonicalPageRecord`, `PageMapRecord`, `CorpusParseManifest`) | `src/common/schemas.py`, `src/ingestion/*` | W1A + W2A |

## Frozen Decisions

| Decision | Value |
|----------|-------|
| Reference plan | `../../.apm/worktrees/REF-PLANS/src/ingestion/migration-plan.md` |
| Stage ownership | `src/ingestion` remains the canonical upstream stage for corpus creation and sidecars |
| Logging policy | Normal runs must emit explicit parse/document/artifact boundary logs |

## Output

- `src/ingestion/contracts.py`
- `src/ingestion/artifact_writer.py`
- Narrowed `src/ingestion/service.py`
- Narrowed `src/ingestion/pdf_parser.py`
- Updated `src/ingestion/__init__.py`

## Definition of Done

- [ ] Ingestion orchestration, parser workers, and artifact writing match the migration plan boundaries
- [ ] Canonical corpus, page map, manifest, and sidecar contracts remain stable
- [ ] Normal-run parse logs exist for start, document boundaries, sidecar writes, corpus build, completion, and failures
- [ ] Ingestion smoke checks and focused tests pass with artifact inspection
- [ ] All contract interfaces implemented and type-checked
- [ ] Verification passing
- [ ] Results committed to git
