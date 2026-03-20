from __future__ import annotations

import json
from pathlib import Path

import fitz

from src.common.config import AppConfig
from src.ingestion.ocr_engine import OcrPageResult, OcrTableExtraction
from src.ingestion.pdf_parser import DocumentParser
from src.ingestion.service import CorpusParseService


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
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    document.save(path)
    document.close()


def test_parse_corpus_writes_serialized_table_blocks_from_ocr_page(tmp_path: Path) -> None:
    config = AppConfig.model_validate({"storage": {"root_dir": str(tmp_path / "data")}})
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    _write_pdf(documents_dir / "alpha.pdf", pages=[""])

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
    config = AppConfig.model_validate({"storage": {"root_dir": str(tmp_path / "data")}})
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    _write_pdf(documents_dir / "alpha.pdf", pages=[""])
    _write_pdf(documents_dir / "beta.pdf", pages=[""])

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
    config = AppConfig.model_validate({"storage": {"root_dir": str(tmp_path / "data")}})
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    _write_pdf(documents_dir / "alpha.pdf", pages=["DIFC LAW NO. 1\nArticle 1"])

    service = CorpusParseService(config)
    first_result = service.parse_corpus(overwrite=True)
    assert first_result.parsed_document_count == 1

    debug_path = tmp_path / "data" / "warmup" / "corpus" / "debug" / "alpha.md"
    debug_path.unlink()

    second_result = service.parse_corpus(overwrite=False)

    assert second_result.written_paths
    assert not second_result.skipped_paths
    assert debug_path.exists()


def test_corpus_parse_service_skips_when_artifacts_are_complete(tmp_path: Path) -> None:
    config = AppConfig.model_validate({"storage": {"root_dir": str(tmp_path / "data")}})
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    _write_pdf(documents_dir / "alpha.pdf", pages=["DIFC LAW NO. 1\nArticle 1"])

    service = CorpusParseService(config)
    first_result = service.parse_corpus(overwrite=True)
    second_result = service.parse_corpus(overwrite=False)

    assert first_result.parsed_document_count == 1
    assert not second_result.written_paths
    assert second_result.skipped_paths


def test_corpus_parse_service_skips_when_selected_doc_subset_artifacts_are_complete(tmp_path: Path) -> None:
    config = AppConfig.model_validate({"storage": {"root_dir": str(tmp_path / "data")}})
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
    config = AppConfig.model_validate({"storage": {"root_dir": str(tmp_path / "data")}})
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
