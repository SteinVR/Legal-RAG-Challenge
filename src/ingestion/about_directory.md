# About This Directory
Purpose: PDF parsing and canonical corpus creation.
Contains: The parse orchestration service, PDF parser, triage heuristics, OCR adapter, table serialization, and corpus builder.
Start Here: `service.py` for orchestration, then `pdf_parser.py`, `page_triage.py`, and `table_serializer.py` for the core mechanics.
Key Files/Dirs: `service.py`, `pdf_parser.py`, `page_triage.py`, `ocr_engine.py`, `table_serializer.py`, `corpus_builder.py`.
Notes: This is the right place to debug missing text, OCR routing, page quality flags, or corpus artifact shape.
