# About This Directory
Purpose: PDF parsing, parser routing, opendataloader adaptation, sidecar persistence, and canonical corpus creation.
Contains: Parse orchestration, PDF parser/fallback, routed structural sidecar adaptation, routing helpers, sidecar I/O, structural normalization, OCR adapter, table serialization, and corpus builder.
Start Here: `service.py` for orchestration, then `pdf_parser.py`, `opendataloader_adapter.py`, `parser_routing.py`, and `sidecars.py`.
Key Files/Dirs: `service.py`, `pdf_parser.py`, `opendataloader_adapter.py`, `parser_routing.py`, `sidecars.py`, `structural_normalizer.py`, `page_triage.py`, `ocr_engine.py`, `table_serializer.py`, `corpus_builder.py`.
Notes: This is the right place to debug parser arbitration, missing structural artifacts, OCR routing, page quality flags, and canonical corpus shape.
