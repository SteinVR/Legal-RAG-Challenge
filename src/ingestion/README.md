# `src/ingestion/`

PDF parsing, OCR, sidecars, routing, normalization, and corpus assembly live here. Package initializers and cache directories are intentionally omitted from the map.

## File graph

```text
ingestion/
├── corpus_builder.py
├── ocr_engine.py
├── opendataloader_adapter.py
├── page_triage.py
├── parser_routing.py
├── pdf_parser.py
├── service.py
├── sidecars.py
├── structural_normalizer.py
└── table_serializer.py
```

## File map

- `corpus_builder.py`: Canonical corpus assembly. It turns parsed documents into page records, page maps, manifests, debug markdown, and the `CorpusBuilder` orchestration wrapper.
- `ocr_engine.py`: Optional OCR adapter for scanned or suspicious pages. It provides the OCR engine abstraction, PaddleOCR-backed implementation, page text extraction, table extraction, and availability checks.
- `opendataloader_adapter.py`: Opendataloader execution and sidecar adaptation. It routes provenance, runs the converter, and extracts nodes, tables, and normalized sidecar payloads.
- `page_triage.py`: Page triage and quality scoring. It computes quality breakdowns, bad-character ratios, legal marker counts, and page labels used during parsing decisions.
- `parser_routing.py`: Parser routing and batching policies. It resolves parser routes and plans route batches from structural document profiles.
- `pdf_parser.py`: Native PDF parsing with OCR fallback and table candidate extraction. It classifies documents, resolves page state, builds raw parse sidecars, and exposes the `DocumentParser` entrypoint.
- `service.py`: Phase-aware corpus parsing orchestration. It manages paths, logging, config resolution, and the end-to-end parse service wrapper.
- `sidecars.py`: Read/write helpers for raw parse sidecar artifacts.
- `structural_normalizer.py`: Normalization layer that converts raw structural sidecars into canonical blocks suitable for downstream corpus assembly.
- `table_serializer.py`: Rule-based table detection, merging, and serialization. It produces markdown/HTML table representations and the `TableSerializer` wrapper.
