# Migration Plan: `src/ingestion`

## Goal and non-goals

### Goal
- Keep `src/ingestion` as the canonical upstream stage for `PDF -> canonical corpus -> sidecars -> manifest`.
- Preserve the current stage-oriented structure, but tighten module boundaries so orchestration, parsing, sidecar handling, table serialization, normalization, and artifact writing are independently replaceable.
- Make runtime logging explicit at every document-level and stage-level boundary.

### Non-goals
- Do not weaken canonical corpus quality gates for convenience.
- Do not push ingestion-specific path or artifact-writing logic into `common`.
- Do not preserve the current oversized package export surface.

## Current boundary map
- `service.py` orchestrates parse flow, cache decisions, sidecar handling, and artifact writing.
- `pdf_parser.py` currently mixes page triage, OCR fallback, route selection, and parse result assembly.
- `corpus_builder.py` builds canonical corpus artifacts and also renders debug markdown.
- `table_serializer.py` already contains provider-driven structured generation behavior.
- `parser_routing.py`, `page_triage.py`, `ocr_engine.py`, `sidecars.py`, `structural_normalizer.py`, and `opendataloader_adapter.py` are useful submodules but not yet cleanly bounded at the orchestration layer.
- `__init__.py` exports almost the whole package surface.

## Target module split
- `contracts.py`: ingestion-local typed result models such as `CorpusPaths`, `ParseCorpusResult`, and any document-level intermediate result types that are not global SSOTs.
- `service.py`: orchestration only; no low-level parse heuristics, no sidecar write logic, no markdown rendering.
- `pdf_parser.py`: one-document parse orchestration only, delegating route choice, OCR, native parse, structural parse, and table extraction to narrower helpers.
- `artifact_writer.py`: writes corpus JSONL, page map, manifests, and debug markdown.
- `parser_routing.py`, `page_triage.py`, `ocr_engine.py`, `sidecars.py`, `structural_normalizer.py`, `table_serializer.py`, `opendataloader_adapter.py`: keep as specialized workers with typed inputs/outputs.
- `__init__.py`: export only the service entrypoint and stable contracts.

## Migration steps
1. Introduce `contracts.py` and move ingestion-local dataclasses/results out of `service.py`.
2. Split artifact persistence from `service.py` into `artifact_writer.py`; keep all filesystem write policy there.
3. Narrow `pdf_parser.py` so it delegates page triage, route selection, OCR upgrade, structural parse, and sidecar assembly instead of owning all of them inline.
4. Move debug markdown rendering out of `corpus_builder.py` into `artifact_writer.py` or a dedicated debug-output helper.
5. Keep `table_serializer.py` focused on table serialization and schema-bound extraction; document provider usage explicitly as a dependency instead of leaving it as an implicit helper path.
6. Reduce `__init__.py` to the minimal public surface and update call sites to import concrete modules where needed.
7. Add explicit start/complete/failure logs for document parse, sidecar generation, corpus assembly, and artifact writing.

## Contracts to preserve and change

### Preserve
- `CanonicalPageRecord`, `PageMapRecord`, and `CorpusParseManifest` stay the canonical stage outputs.
- Parser provenance, triage labels, quality flags, and page numbering semantics remain unchanged unless a separate spec updates them.
- `CorpusParseService` remains the top-level orchestration seam for `parse-corpus`.

### Change
- Package-wide exports are reduced.
- Artifact writing becomes a dedicated module instead of being embedded in the service.
- Intermediate document parse types become explicit and typed rather than being passed as raw mixed payloads.

## Logging and typing checklist
- Mandatory non-debug logs: `parse.start`, `parse.document.start`, `parse.document.complete`, `parse.document.failed`, `parse.sidecar.write`, `parse.corpus.build`, `parse.complete`.
- Every helper boundary must accept and return typed objects; avoid untyped mixed payload dicts between parser, table serializer, and corpus builder.
- Keep fail-fast behavior for missing OCR/runtime/parser dependencies where the current config already requires it.

## Verification
- Run `parse-corpus` on a representative subset and inspect produced corpus/manifests and runtime logs.
- Confirm debug artifacts are still written only by the dedicated artifact writer path.
- Run ingestion-focused tests and inspect at least one failure-path log for clear parser/runtime errors.

## Acceptance criteria
- `service.py` is orchestration-only.
- `pdf_parser.py` no longer owns route, OCR, sidecars, and corpus concerns inline.
- Public exports are narrow, typed, and intentionally owned.

## Risks and rollback
- The main risk is accidentally changing canonical corpus shape while extracting helpers. Roll back by restoring the previous document-assembly path only long enough to diff outputs and isolate the contract drift.
- The second risk is hidden coupling between table serialization and provider behavior. Keep that dependency explicit during extraction instead of burying it in generic helpers.
