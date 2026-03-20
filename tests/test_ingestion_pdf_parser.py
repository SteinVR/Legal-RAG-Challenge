from __future__ import annotations

from pathlib import Path

import fitz

from src.common.config import AppConfig
from src.common.schemas import ParseStatus, SourceMode, TriageLabel
from src.ingestion.pdf_parser import parse_pdf_document


def _write_pdf(path: Path, *, pages: list[str], title: str | None = None) -> None:
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    if title:
        document.set_metadata({"title": title})
    document.save(path)
    document.close()


def test_parse_pdf_document_extracts_title_family_and_pages(tmp_path: Path) -> None:
    pdf_path = tmp_path / "alpha.pdf"
    _write_pdf(
        pdf_path,
        pages=[
            (
                "DIFC LAW NO. 1\nArticle 1\nSection 1\nThis law governs employment and procedures. "
                "It defines scope, jurisdiction, obligations, notice periods, remedies, enforcement pathways, "
                "and transitional provisions in detailed legal language for the employment framework."
            ),
            (
                "Article 2\nSection 2\nThis provision defines the duties of the parties in detail. "
                "It specifies compliance requirements, formal notices, documentary evidence, payment timing, "
                "and administrative obligations across multiple scenarios to preserve a clean native page."
            ),
        ],
        title="DIFC Law",
    )
    config = AppConfig.model_validate({"ingestion": {"enable_ocr": False, "suspicious_text_max_chars": 10}})

    parsed = parse_pdf_document(pdf_path, config)

    assert parsed.doc_id == "alpha"
    assert parsed.document_title == "DIFC Law"
    assert parsed.document_family == "law_or_regulation"
    assert parsed.page_count == 2
    assert parsed.parse_status is ParseStatus.PARSED
    assert all(page.source_mode is SourceMode.NATIVE for page in parsed.pages)
    assert parsed.pages[0].triage_label is TriageLabel.NATIVE_CLEAN


def test_parse_pdf_document_marks_empty_page_as_degraded_when_ocr_is_unavailable(tmp_path: Path) -> None:
    pdf_path = tmp_path / "scan_like.pdf"
    _write_pdf(pdf_path, pages=[""])
    config = AppConfig()

    parsed = parse_pdf_document(pdf_path, config, ocr_engine=None)

    assert parsed.page_count == 1
    assert parsed.parse_status is ParseStatus.DEGRADED
    assert parsed.pages[0].triage_label is TriageLabel.SCAN
    assert parsed.pages[0].parse_status is ParseStatus.DEGRADED


def test_parse_pdf_document_marks_scan_page_as_degraded_when_ocr_is_disabled(tmp_path: Path) -> None:
    pdf_path = tmp_path / "scan_like.pdf"
    _write_pdf(pdf_path, pages=[""])
    config = AppConfig.model_validate({"ingestion": {"enable_ocr": False}})

    parsed = parse_pdf_document(pdf_path, config)

    assert parsed.page_count == 1
    assert parsed.parse_status is ParseStatus.DEGRADED
    assert parsed.pages[0].triage_label is TriageLabel.SCAN
    assert parsed.pages[0].parse_status is ParseStatus.DEGRADED


def test_parse_pdf_document_marks_short_scan_text_as_degraded_without_ocr(tmp_path: Path) -> None:
    pdf_path = tmp_path / "short_scan.pdf"
    _write_pdf(pdf_path, pages=["Court order"])
    config = AppConfig.model_validate({"ingestion": {"enable_ocr": False}})

    parsed = parse_pdf_document(pdf_path, config)

    assert parsed.page_count == 1
    assert parsed.parse_status is ParseStatus.DEGRADED
    assert parsed.pages[0].triage_label is TriageLabel.SCAN
    assert parsed.pages[0].text == "Court order"
    assert parsed.pages[0].parse_status is ParseStatus.DEGRADED
