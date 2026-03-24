# About This Directory
Purpose: Final answer construction layer.
Contains: `service.py` for schema-first answering, query metadata, and answer assembly, plus `page_attribution.py` for two-pass page grounding and validation.
Start Here: Open `service.py` for the end-to-end answering flow, then `page_attribution.py` for Pass A/Pass B attribution behavior and trace shaping.
Key Files/Dirs: `service.py`, `page_attribution.py`.
Notes: If you are tracing end-to-end flow, pair this directory with `src/retrieval/` for evidence collection, `src/providers/` for structured solving, and `src/submission/` for pipeline integration.
