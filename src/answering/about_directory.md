# About This Directory
Purpose: Final answer construction layer.
Contains: `service.py`, which now owns schema-first answer solving for all answer types, query-metadata extraction, evidence normalization, typed guardrails, page narrowing, and confidence shaping.
Start Here: Open `service.py`; the answering pipeline remains intentionally consolidated rather than split into many helper modules.
Key Files/Dirs: `service.py`.
Notes: If you are tracing end-to-end flow, pair this directory with `src/retrieval/` for evidence collection, `src/providers/` for structured solving, and `src/submission/` for pipeline integration.
