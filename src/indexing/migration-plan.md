# Migration Plan: `src/indexing`

## Goal and non-goals

### Goal
- Decompose `src/indexing` from a single large service module into a stage with explicit ownership boundaries for chunking, embedding, sparse encoding, persistence, and manifest generation.
- Preserve index artifact compatibility while making chunking and model-loading policies independently swappable.
- Keep indexing strict and quality-first; no fallback paths that silently reduce retrieval quality.

### Non-goals
- Do not change corpus input contracts owned by ingestion.
- Do not collapse indexing into retrieval or submission orchestration.
- Do not preserve the current monolithic `service.py` layout once the migration is complete.

## Current boundary map
- `service.py` currently owns local result contracts, index path layout, dense embedder implementation, sparse encoder implementation, chunking logic, Qdrant persistence, and manifest writing.
- `HybridIndexService.build_indices` is the public entrypoint, but almost every meaningful implementation detail lives in the same file.
- `build_index_chunks`, `Qwen3DenseEmbedder`, and `BM25SparseEncoder` are all embedded beside orchestration code.

## Target module split
- `contracts.py`: `IndexPaths`, `BuildIndexResult`, `IndexChunk`, and other indexing-local types.
- `paths.py`: path/materialization logic for index artifacts only.
- `chunking.py`: chunk-family generation, heading context, token counting, and chunk metadata enrichment.
- `dense_embedder.py`: dense embedding protocol plus Qwen implementation and loader.
- `sparse_encoder.py`: BM25 sparse encoder and persisted sparse state handling.
- `qdrant_writer.py`: local Qdrant collection creation/update and payload persistence.
- `manifest.py`: index manifest generation and validation.
- `service.py`: orchestration only, wiring the above modules together.

## Migration steps
1. Move indexing-local contracts and path logic out of `service.py` into `contracts.py` and `paths.py`.
2. Extract chunk generation into `chunking.py`, keeping chunk-family taxonomy and metadata semantics unchanged.
3. Extract dense model loading and embedding into `dense_embedder.py`; keep fail-fast behavior when the local model is missing.
4. Extract sparse encoder state build/load/persist into `sparse_encoder.py`.
5. Extract Qdrant write/update logic into `qdrant_writer.py` and manifest generation into `manifest.py`.
6. Reduce `service.py` to orchestration, cache checks, stage logging, and result formatting only.
7. Replace cross-module `dict[str, Any]` payload traffic with typed `IndexChunk` and manifest/path models wherever the boundary is stable enough to do so.

## Contracts to preserve and change

### Preserve
- `HybridIndexService.build_indices` remains the stage entrypoint until `main.py` and `submission` are migrated.
- Index artifact layout remains stable: `qdrant/`, `page_parent_map.json`, `index_manifest.json`, and `sparse_encoder_state.json`.
- Chunk taxonomy and downstream metadata required by retrieval stay unchanged unless an explicit retrieval-linked migration step updates both packages together.

### Change
- Chunking, embedding, sparse encoding, and persistence are no longer implemented inline inside `service.py`.
- Dense embedder and sparse encoder become independent injectable dependencies.
- Internal data flow becomes typed at stage boundaries instead of relying on helper-heavy mixed dicts.

## Logging and typing checklist
- Mandatory non-debug logs: `index.start`, `index.chunking.start`, `index.chunking.complete`, `index.embedding.start`, `index.embedding.complete`, `index.persist.start`, `index.persist.complete`, `index.complete`, `index.failed`.
- Keep typed contracts for chunk families, embedder outputs, sparse state, and manifest data.
- No fallback from dense+sparse hybrid indexing to a reduced-quality mode unless explicitly configured by a higher-level contract update.

## Verification
- Run `build-indices` on an existing corpus and compare index artifact presence, manifest shape, and chunk counts to the pre-migration baseline.
- Inspect runtime logs to confirm each boundary emits start/complete events.
- Run indexing-related tests plus at least one retrieval smoke query to ensure downstream consumers still accept the artifacts.

## Acceptance criteria
- `service.py` is reduced to orchestration and formatting.
- Chunking, dense embedding, sparse encoding, and Qdrant persistence are separate modules with typed seams.
- Index artifact layout and retrieval compatibility remain stable.

## Risks and rollback
- The main risk is silent drift in chunk-family behavior during extraction. Roll back by diffing emitted chunk inventories and restoring the previous chunking module only long enough to isolate mismatches.
- The second risk is persistence drift in Qdrant or sparse state. Keep manifest compatibility checks in place before removing the old path.
