from __future__ import annotations

import json
from pathlib import Path

import fitz

from src.common.config import AppConfig
from src.common.runtime_logging import configure_runtime_logging, shutdown_runtime_logging
from src.common.schemas import (
    PageSignal,
    ParsedDocument,
    ParsedPage,
    ParserRoute,
    ParseStatus,
    RawParseSidecar,
    SourceMode,
    TriageLabel,
)
from src.ingestion.ocr_engine import OcrPageResult, OcrTableExtraction
from src.ingestion.pdf_parser import DocumentParser
from src.ingestion.service import CorpusParseService
from tests.support.documents import write_pdf


class StubOcrEngine:
    def __init__(self, page_results: list[OcrPageResult]) -> None:
        self._page_results = page_results
        self.calls = 0

    def extract_page(self, page: fitz.Page) -> OcrPageResult:
        del page
        result = self._page_results[self.calls]
        self.calls += 1
        return result


def _write_pdf(path: Path, *, pages: list[str]) -> None:
    write_pdf(path, page_texts=pages)


def _config(tmp_path: Path, *, logging_directory: Path | None = None) -> AppConfig:
    payload: dict[str, object] = {
        "storage": {"root_dir": str(tmp_path / "data")},
        "ingestion": {"enable_ocr": False},
    }
    if logging_directory is not None:
        payload["logging"] = {"directory": str(logging_directory), "console": False}
    return AppConfig.model_validate(payload)


def test_parse_corpus_writes_serialized_table_blocks_from_ocr_page(tmp_path: Path) -> None:
    config = _config(tmp_path)
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    write_pdf(documents_dir / "alpha.pdf", page_texts=[""])

    service = CorpusParseService(config)
    service.parser = DocumentParser(
        config,
        ocr_engine=StubOcrEngine(
            [
                OcrPageResult(
                    text="DIFC LAW NO. 1\nArticle 1",
                    text_blocks=["Schedule of fees", "Type Amount", "Fee 10"],
                    table_candidates=[
                        OcrTableExtraction(
                            cells=[["Type", "Amount"], ["Fee", "10"]],
                            raw_markdown="| Type | Amount |\n| --- | --- |\n| Fee | 10 |",
                            raw_html="<table></table>",
                            header_signature=["Type", "Amount"],
                            caption="Schedule of fees",
                            context_before=["Schedule of fees"],
                            context_after=["Footnote"],
                        )
                    ],
                )
            ]
        ),
    )

    result = service.parse_corpus(overwrite=True)

    corpus_path = tmp_path / "data" / "warmup" / "corpus" / "corpus.jsonl"
    corpus_rows = [json.loads(line) for line in corpus_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert result.parsed_document_count == 1
    assert corpus_rows[0]["document_family"] == "law_or_regulation"
    assert corpus_rows[0]["table_ids"] == ["alpha-p1-t1"]
    assert any(
        block["type"] == "table" and block["table_id"] == "alpha-p1-t1"
        for block in corpus_rows[0]["blocks"]
    )


def test_corpus_parse_service_reuses_one_shared_ocr_engine(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    write_pdf(documents_dir / "alpha.pdf", page_texts=[""])
    write_pdf(documents_dir / "beta.pdf", page_texts=[""])

    build_calls = 0

    class SharedOcrEngine:
        def __init__(self) -> None:
            self.calls = 0

        def extract_page(self, page: fitz.Page) -> OcrPageResult:
            del page
            self.calls += 1
            return OcrPageResult(
                text="DIFC LAW NO. 1\nArticle 1\nRecovered OCR text.",
                text_blocks=["DIFC LAW NO. 1", "Article 1", "Recovered OCR text."],
                table_candidates=[],
            )

    shared_engine = SharedOcrEngine()

    def fake_build_ocr_engine(_settings):
        nonlocal build_calls
        build_calls += 1
        return shared_engine

    monkeypatch.setattr("src.ingestion.service.build_ocr_engine", fake_build_ocr_engine)
    monkeypatch.setattr(
        "src.ingestion.pdf_parser.build_ocr_engine",
        lambda _settings: (_ for _ in ()).throw(AssertionError("unexpected per-document OCR construction")),
    )

    service = CorpusParseService(config)
    result = service.parse_corpus(overwrite=True)

    assert build_calls == 1
    assert service.ocr_engine is shared_engine
    assert shared_engine.calls == 2
    assert result.parsed_document_count == 2


def test_corpus_parse_service_rebuilds_when_debug_artifact_is_missing(tmp_path: Path) -> None:
    config = _config(tmp_path)
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    write_pdf(documents_dir / "alpha.pdf", page_texts=["DIFC LAW NO. 1\nArticle 1"])

    service = CorpusParseService(config)
    first_result = service.parse_corpus(overwrite=True)
    assert first_result.parsed_document_count == 1

    debug_path = tmp_path / "data" / "warmup" / "corpus" / "debug" / "alpha.md"
    debug_path.unlink()

    second_result = service.parse_corpus(overwrite=False)

    assert second_result.written_paths
    assert not second_result.skipped_paths
    assert debug_path.exists()


def test_corpus_parse_service_rebuilds_when_required_structural_sidecar_is_missing(
    tmp_path: Path, monkeypatch
) -> None:
    config = _config(tmp_path)
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    write_pdf(documents_dir / "alpha.pdf", page_texts=["DIFC LAW NO. 1\nArticle 1"])

    service = CorpusParseService(config)
    parsed = ParsedDocument(
        doc_id="alpha",
        filename="alpha.pdf",
        sha256="deadbeef",
        page_count=1,
        document_title="Employment Law",
        document_family="law_or_regulation",
        parse_status=ParseStatus.PARSED,
        parser_provenance="opendataloader:hybrid",
        raw_parse_sidecars={
            "pymupdf": RawParseSidecar(
                doc_id="alpha",
                parser_name="pymupdf",
                parser_route=ParserRoute.HYBRID,
                parser_provenance="pymupdf:native",
                page_count=1,
                page_geometry={1: [0.0, 0.0, 612.0, 792.0]},
                diagnostics={},
                route_decisions=["hybrid_selected"],
                nodes=[],
                tables=[],
            ),
            "opendataloader": RawParseSidecar(
                doc_id="alpha",
                parser_name="opendataloader",
                parser_route=ParserRoute.HYBRID,
                parser_provenance="opendataloader:hybrid",
                page_count=1,
                page_geometry={1: [0.0, 0.0, 612.0, 792.0]},
                diagnostics={},
                route_decisions=["hybrid_selected"],
                nodes=[],
                tables=[],
            ),
        },
        pages=[_parsed_page("alpha", 1, "DIFC LAW NO. 1\nArticle 1")],
    )
    monkeypatch.setattr(service.parser, "parse_document", lambda _pdf_path: parsed)

    first_result = service.parse_corpus(overwrite=True)
    assert first_result.parsed_document_count == 1

    structural_sidecar = (
        tmp_path / "data" / "warmup" / "corpus" / "raw_parse" / "opendataloader" / "alpha.json"
    )
    structural_sidecar.unlink()

    second_result = service.parse_corpus(overwrite=False)

    assert second_result.written_paths
    assert not second_result.skipped_paths
    assert structural_sidecar.exists()


def test_corpus_parse_service_skips_when_artifacts_are_complete(tmp_path: Path) -> None:
    config = _config(tmp_path)
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    _write_pdf(documents_dir / "alpha.pdf", pages=["DIFC LAW NO. 1\nArticle 1"])

    service = CorpusParseService(config)
    first_result = service.parse_corpus(overwrite=True)
    second_result = service.parse_corpus(overwrite=False)

    assert first_result.parsed_document_count == 1
    assert not second_result.written_paths
    assert second_result.skipped_paths


def test_corpus_parse_service_emits_skip_cache_runtime_event(tmp_path: Path) -> None:
    config = _config(tmp_path, logging_directory=tmp_path / "logs" / "project" / "runtime")
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    _write_pdf(documents_dir / "alpha.pdf", pages=["DIFC LAW NO. 1\nArticle 1"])

    service = CorpusParseService(config)
    first_result = service.parse_corpus(overwrite=True)
    assert first_result.parsed_document_count == 1

    context = configure_runtime_logging(config, command="parse-corpus", phase=config.phase.value)
    try:
        second_result = service.parse_corpus(overwrite=False)
    finally:
        shutdown_runtime_logging()

    payloads = [
        json.loads(line)
        for line in context.log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert not second_result.written_paths
    assert any(payload["event"] == "parse.skip_cache" for payload in payloads)


def test_corpus_parse_service_skips_when_selected_doc_subset_artifacts_are_complete(tmp_path: Path) -> None:
    config = _config(tmp_path)
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    _write_pdf(documents_dir / "alpha.pdf", pages=["DIFC LAW NO. 1\nArticle 1"])
    _write_pdf(documents_dir / "beta.pdf", pages=["DIFC LAW NO. 2\nArticle 2"])

    service = CorpusParseService(config)
    first_result = service.parse_corpus(overwrite=True, doc_ids=["beta"])
    second_result = service.parse_corpus(overwrite=False, doc_ids=["beta"])

    assert first_result.parsed_document_count == 1
    assert not second_result.written_paths
    assert second_result.skipped_paths


def test_corpus_parse_service_rebuilds_selected_subset_when_subset_debug_artifact_is_missing(tmp_path: Path) -> None:
    config = _config(tmp_path)
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    _write_pdf(documents_dir / "alpha.pdf", pages=["DIFC LAW NO. 1\nArticle 1"])
    _write_pdf(documents_dir / "beta.pdf", pages=["DIFC LAW NO. 2\nArticle 2"])

    service = CorpusParseService(config)
    service.parse_corpus(overwrite=True, doc_ids=["beta"])

    debug_path = tmp_path / "data" / "warmup" / "corpus" / "debug" / "beta.md"
    debug_path.unlink()

    rebuilt = service.parse_corpus(overwrite=False, doc_ids=["beta"])

    assert rebuilt.written_paths
    assert not rebuilt.skipped_paths
    assert debug_path.exists()


def test_corpus_parse_service_skips_selected_subset_when_failed_docs_are_already_recorded(tmp_path: Path) -> None:
    config = _config(tmp_path)
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    _write_pdf(documents_dir / "alpha.pdf", pages=["DIFC LAW NO. 1\nArticle 1"])
    broken_pdf = documents_dir / "broken.pdf"
    broken_pdf.write_bytes(b"%PDF-1.4 broken content")

    service = CorpusParseService(config)
    first_result = service.parse_corpus(overwrite=True, doc_ids=["alpha", "broken"])
    second_result = service.parse_corpus(overwrite=False, doc_ids=["alpha", "broken"])

    assert first_result.parsed_document_count == 1
    assert first_result.failed_document_count == 1
    assert not second_result.written_paths
    assert second_result.skipped_paths


def test_corpus_parse_service_skips_full_run_when_failed_docs_are_already_recorded(tmp_path: Path) -> None:
    config = _config(tmp_path)
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    _write_pdf(documents_dir / "alpha.pdf", pages=["DIFC LAW NO. 1\nArticle 1"])
    (documents_dir / "broken.pdf").write_bytes(b"%PDF-1.4 broken content")

    service = CorpusParseService(config)
    first_result = service.parse_corpus(overwrite=True)
    second_result = service.parse_corpus(overwrite=False)

    assert first_result.parsed_document_count == 1
    assert first_result.failed_document_count == 1
    assert not second_result.written_paths
    assert second_result.skipped_paths


def test_corpus_parse_service_rebuilds_full_run_when_pdf_set_changes(tmp_path: Path) -> None:
    config = _config(tmp_path)
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    _write_pdf(documents_dir / "alpha.pdf", pages=["DIFC LAW NO. 1\nArticle 1"])

    service = CorpusParseService(config)
    first_result = service.parse_corpus(overwrite=True)
    _write_pdf(documents_dir / "beta.pdf", pages=["DIFC LAW NO. 2\nArticle 2"])

    second_result = service.parse_corpus(overwrite=False)

    assert first_result.parsed_document_count == 1
    assert second_result.written_paths
    assert not second_result.skipped_paths


def test_corpus_parse_service_skips_failed_only_subset_without_debug_artifacts(tmp_path: Path) -> None:
    config = _config(tmp_path)
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    broken_pdf = documents_dir / "broken.pdf"
    broken_pdf.write_bytes(b"%PDF-1.4 broken content")

    service = CorpusParseService(config)
    first_result = service.parse_corpus(overwrite=True, doc_ids=["broken"])
    second_result = service.parse_corpus(overwrite=False, doc_ids=["broken"])

    assert first_result.parsed_document_count == 0
    assert first_result.failed_document_count == 1
    assert not second_result.written_paths
    assert second_result.skipped_paths


def test_corpus_parse_service_rebuilds_full_run_when_non_failed_debug_is_missing_but_failures_exist(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    _write_pdf(documents_dir / "alpha.pdf", pages=["DIFC LAW NO. 1\nArticle 1"])
    (documents_dir / "broken.pdf").write_bytes(b"%PDF-1.4 broken content")

    service = CorpusParseService(config)
    service.parse_corpus(overwrite=True)
    debug_path = tmp_path / "data" / "warmup" / "corpus" / "debug" / "alpha.md"
    debug_path.unlink()

    rebuilt = service.parse_corpus(overwrite=False)

    assert rebuilt.written_paths
    assert not rebuilt.skipped_paths
    assert debug_path.exists()


def _parsed_page(doc_id: str, page_number: int, text: str) -> ParsedPage:
    return ParsedPage(
        doc_id=doc_id,
        page_number=page_number,
        document_title="Employment Law",
        document_family="law_or_regulation",
        triage_label=TriageLabel.NATIVE_CLEAN,
        source_mode=SourceMode.NATIVE,
        parse_status=ParseStatus.PARSED,
        text=text,
        native_text=text,
        ocr_text=None,
        text_blocks=[text],
        quality_score=0.95,
        quality_flags=[],
        signals=PageSignal(
            text_char_count=len(text),
            word_count=len(text.split()),
            image_block_count=0,
            max_image_area_ratio=0.0,
            drawing_count=0,
            table_count=0,
            legal_marker_count=1,
            bad_char_ratio=0.0,
        ),
        tables=[],
    )


def test_parse_corpus_writes_raw_parse_sidecars_for_current_and_structural_parsers(
    tmp_path: Path, monkeypatch
) -> None:
    config = _config(tmp_path)
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    _write_pdf(documents_dir / "alpha.pdf", pages=["DIFC LAW NO. 1\nArticle 1"])

    service = CorpusParseService(config)

    parsed = ParsedDocument(
        doc_id="alpha",
        filename="alpha.pdf",
        sha256="deadbeef",
        page_count=1,
        document_title="Employment Law",
        document_family="law_or_regulation",
        parse_status=ParseStatus.PARSED,
        parser_provenance="opendataloader:hybrid",
        raw_parse_sidecars={
            "pymupdf": RawParseSidecar(
                doc_id="alpha",
                parser_name="pymupdf",
                parser_route=ParserRoute.BASELINE_FALLBACK,
                parser_provenance="pymupdf:native",
                page_count=1,
                page_geometry={1: [0.0, 0.0, 612.0, 792.0]},
                diagnostics={},
                route_decisions=["baseline_selected"],
                nodes=[],
                tables=[],
            ),
            "opendataloader": RawParseSidecar(
                doc_id="alpha",
                parser_name="opendataloader",
                parser_route=ParserRoute.HYBRID,
                parser_provenance="opendataloader:hybrid",
                page_count=1,
                page_geometry={1: [0.0, 0.0, 612.0, 792.0]},
                diagnostics={"hybrid_backend": "healthy"},
                route_decisions=["hybrid_selected"],
                nodes=[],
                tables=[],
            ),
        },
        pages=[_parsed_page("alpha", 1, "DIFC LAW NO. 1\nArticle 1")],
    )

    monkeypatch.setattr(service.parser, "parse_document", lambda _pdf_path: parsed)

    service.parse_corpus(overwrite=True)

    current_sidecar = tmp_path / "data" / "warmup" / "corpus" / "raw_parse" / "pymupdf" / "alpha.json"
    structural_sidecar = (
        tmp_path / "data" / "warmup" / "corpus" / "raw_parse" / "opendataloader" / "alpha.json"
    )

    assert current_sidecar.exists()
    assert structural_sidecar.exists()
    assert json.loads(structural_sidecar.read_text(encoding="utf-8"))["parser_route"] == "hybrid"


def test_corpus_parse_service_passes_structured_provider_when_semantic_table_blocks_enabled(
    tmp_path: Path, monkeypatch
) -> None:
    config = AppConfig.model_validate(
        {
            "storage": {"root_dir": str(tmp_path / "data")},
            "ingestion": {"enable_ocr": False, "enable_semantic_table_blocks": True},
        }
    )
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    _write_pdf(documents_dir / "alpha.pdf", pages=["DIFC LAW NO. 1\nArticle 1"])

    structured_provider = object()
    monkeypatch.setattr(
        "src.ingestion.service.CorpusParseService._build_structured_provider",
        lambda self: structured_provider,
    )

    service = CorpusParseService(config)
    parsed = ParsedDocument(
        doc_id="alpha",
        filename="alpha.pdf",
        sha256="deadbeef",
        page_count=1,
        document_title="Employment Law",
        document_family="law_or_regulation",
        parse_status=ParseStatus.PARSED,
        parser_provenance="pymupdf:native",
        raw_parse_sidecars={
            "pymupdf": RawParseSidecar(
                doc_id="alpha",
                parser_name="pymupdf",
                parser_route=ParserRoute.BASELINE_FALLBACK,
                parser_provenance="pymupdf:native",
                page_count=1,
                page_geometry={1: [0.0, 0.0, 612.0, 792.0]},
                diagnostics={},
                route_decisions=["baseline_selected"],
                nodes=[],
                tables=[],
            )
        },
        pages=[_parsed_page("alpha", 1, "DIFC LAW NO. 1\nArticle 1")],
    )
    monkeypatch.setattr(service.parser, "parse_document", lambda _pdf_path: parsed)

    captured: dict[str, object] = {}

    def fake_serialize_document_tables(document, *, enable_semantic_blocks, structured_provider):
        captured["doc_id"] = document.doc_id
        captured["enable_semantic_blocks"] = enable_semantic_blocks
        captured["structured_provider"] = structured_provider
        return {}

    monkeypatch.setattr("src.ingestion.service.serialize_document_tables", fake_serialize_document_tables)

    service.parse_corpus(overwrite=True)

    assert captured == {
        "doc_id": "alpha",
        "enable_semantic_blocks": True,
        "structured_provider": structured_provider,
    }
