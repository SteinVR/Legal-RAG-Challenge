# SPEC: W2B -- Decompose `src/indexing`

**Wave:** 2 | **Depends on:** W1A, W2A | **Blocks:** W3A, W4A

## Goal

Split `src/indexing` into explicit chunking, embedding, sparse encoding, persistence, manifest, and orchestration modules while preserving index artifact compatibility. The detailed split and verification expectations are frozen in `../../.apm/worktrees/REF-PLANS/src/indexing/migration-plan.md`.

## Pipeline

1. Move indexing-local contracts and path logic into `contracts.py` and `paths.py`.
2. Extract chunk generation, dense embedding, sparse encoding, Qdrant writing, and manifest generation into dedicated modules.
3. Reduce `service.py` to orchestration, cache checks, stage logging, and typed result formatting.

## Contracts

| Interface | Location | Owner |
|-----------|----------|-------|
| `HybridIndexService.build_indices` | `src/indexing/service.py` | W2B |
| `IndexPaths`, `BuildIndexResult`, `IndexChunk` | `src/indexing/contracts.py` | W2B |
| Index artifact layout (`qdrant/`, `page_parent_map.json`, `index_manifest.json`, `sparse_encoder_state.json`) | `src/indexing/paths.py`, `src/indexing/manifest.py` | W2B |

## Frozen Decisions

| Decision | Value |
|----------|-------|
| Reference plan | `../../.apm/worktrees/REF-PLANS/src/indexing/migration-plan.md` |
| Runtime mode | Dense+sparse hybrid indexing stays required; no silent degraded fallback |
| Artifact compatibility | Existing index artifact names and downstream retrieval compatibility remain stable |

## Output

- `src/indexing/contracts.py`
- `src/indexing/paths.py`
- `src/indexing/chunking.py`
- `src/indexing/dense_embedder.py`
- `src/indexing/sparse_encoder.py`
- `src/indexing/qdrant_writer.py`
- `src/indexing/manifest.py`
- Narrowed `src/indexing/service.py`

## Definition of Done

- [ ] Indexing module boundaries match the migration plan and `service.py` is orchestration-only
- [ ] Chunk families, artifact layout, and retrieval-facing metadata remain stable
- [ ] Normal-run indexing logs cover chunking, embedding, persistence, completion, and failure
- [ ] `build-indices` smoke checks and downstream retrieval acceptance checks pass
- [ ] All contract interfaces implemented and type-checked
- [ ] Verification passing
- [ ] Results committed to git
