"""Optional OCR adapter for scanned or suspicious PDF pages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import fitz
import numpy

from src.common.config import IngestionSettings
from src.common.schemas import ParseStatus, SourceMode


class OcrUnavailableError(RuntimeError):
    """Raised when OCR is requested but PaddleOCR is unavailable."""


OCRUnavailableError = OcrUnavailableError


class OcrEngine(Protocol):
    """Protocol for OCR adapters used by the parser."""

    def extract_page_text(self, page: fitz.Page) -> str:
        """Return OCR text for one page."""


@dataclass(slots=True)
class OcrResolution:
    """Resolved page text and provenance after OCR selection."""

    text: str
    source_mode: SourceMode
    parse_status: ParseStatus
    notes: list[str] = field(default_factory=list)


class PaddleOcrEngine:
    """Thin adapter around PaddleOCR with explicit unavailable policies."""

    def __init__(self, settings: IngestionSettings) -> None:
        self.settings = settings
        self._ocr_client: Any | None = None

    def extract_page_text(self, page: fitz.Page) -> str:
        ocr_client = self._get_client()
        pixmap = page.get_pixmap(dpi=200, alpha=False)
        channels = pixmap.n
        image = numpy.frombuffer(pixmap.samples, dtype=numpy.uint8).reshape(pixmap.height, pixmap.width, channels)
        if channels == 4:
            image = image[:, :, :3]

        results = ocr_client.ocr(image, cls=False)
        return _extract_ocr_text(results).strip()

    def _get_client(self) -> Any:
        if self._ocr_client is not None:
            return self._ocr_client

        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise OcrUnavailableError("PaddleOCR is not installed. Install the paddle extra to enable OCR.") from exc

        self._ocr_client = PaddleOCR(use_angle_cls=False, lang="en")
        return self._ocr_client


def _extract_ocr_text(results: Any) -> str:
    lines: list[str] = []
    if not results:
        return ""

    for page_result in results:
        if not page_result:
            continue
        for item in page_result:
            if not item or len(item) < 2:
                continue
            text_tuple = item[1]
            if isinstance(text_tuple, (list, tuple)) and text_tuple:
                text = str(text_tuple[0]).strip()
            else:
                text = str(text_tuple).strip()
            if text:
                lines.append(text)
    return "\n".join(lines)


def build_ocr_engine(settings: IngestionSettings) -> OcrEngine | None:
    """Return a runtime OCR adapter when enabled and available."""

    if not settings.enable_ocr:
        return None
    try:
        return PaddleOcrAdapter(settings)
    except OcrUnavailableError:
        if settings.ocr_unavailable_policy == "error":
            raise
        return None


def resolve_page_text(
    *,
    native_text: str,
    ocr_text: str | None,
    prefer_ocr: bool,
    allow_hybrid: bool,
    ocr_available: bool,
    config: IngestionSettings,
) -> OcrResolution:
    """Choose the final page text after considering OCR availability."""

    native = native_text.strip()
    ocr = (ocr_text or "").strip()
    notes: list[str] = []

    if not ocr_available:
        if native:
            notes.append("ocr_unavailable")
            return OcrResolution(
                text=native,
                source_mode=SourceMode.NATIVE,
                parse_status=ParseStatus.DEGRADED,
                notes=notes,
            )
        if config.ocr_unavailable_policy == "error":
            raise OcrUnavailableError("OCR is unavailable and no native text was extracted.")
        notes.append("ocr_unavailable")
        return OcrResolution(text="", source_mode=SourceMode.NATIVE, parse_status=ParseStatus.DEGRADED, notes=notes)

    if not ocr:
        notes.append("ocr_empty")
        return OcrResolution(
            text=native,
            source_mode=SourceMode.NATIVE,
            parse_status=ParseStatus.DEGRADED if prefer_ocr else ParseStatus.PARSED,
            notes=notes,
        )

    if prefer_ocr or not native:
        return OcrResolution(text=ocr, source_mode=SourceMode.OCR, parse_status=ParseStatus.PARSED, notes=notes)

    if allow_hybrid and len(ocr) > len(native) * 1.1:
        notes.append("ocr_selected")
        return OcrResolution(text=ocr, source_mode=SourceMode.HYBRID, parse_status=ParseStatus.PARSED, notes=notes)

    return OcrResolution(text=native, source_mode=SourceMode.NATIVE, parse_status=ParseStatus.PARSED, notes=notes)


PaddleOcrAdapter = PaddleOcrEngine
OCREngine = OcrEngine
