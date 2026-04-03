from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz
import pytest

from src.common.config import AppConfig
from src.common.schemas import SourceMode, TriageLabel
from src.ingestion.ocr_engine import OcrUnavailableError
from src.ingestion.pdf_parser import parse_pdf_document


class _UnavailableOcrEngine:
    def extract_page(self, page: Any) -> Any:
        raise OcrUnavailableError("OCR runtime unavailable")


def _write_pdf(path: Path, text: str) -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()


def test_suspicious_page_degrades_to_native_when_ocr_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("src.ingestion.pdf_parser.triage_page", lambda *_args, **_kwargs: TriageLabel.SUSPICIOUS)

    pdf_path = tmp_path / "suspicious.pdf"
    _write_pdf(pdf_path, "The notice must be filed within 30 days under DIFC Law No. 5.")
    config = AppConfig.model_validate({"ingestion": {"ocr_unavailable_policy": "error"}})

    parsed = parse_pdf_document(pdf_path, config, ocr_engine=_UnavailableOcrEngine())

    assert len(parsed.pages) == 1
    assert parsed.pages[0].source_mode == SourceMode.NATIVE
    assert parsed.pages[0].parse_status.value == "degraded"


def test_scan_page_still_fails_fast_when_ocr_is_required(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("src.ingestion.pdf_parser.triage_page", lambda *_args, **_kwargs: TriageLabel.SCAN)

    pdf_path = tmp_path / "scan.pdf"
    _write_pdf(pdf_path, "Scanned page placeholder.")
    config = AppConfig.model_validate({"ingestion": {"ocr_unavailable_policy": "error"}})

    with pytest.raises(OcrUnavailableError):
        parse_pdf_document(pdf_path, config, ocr_engine=_UnavailableOcrEngine())
