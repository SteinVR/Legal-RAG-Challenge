"""Optional OCR adapter for scanned or suspicious PDF pages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import fitz
import numpy

from src.common.config import IngestionSettings

BBox = tuple[float, float, float, float]


class OcrUnavailableError(RuntimeError):
    """Raised when OCR is requested but PaddleOCR is unavailable."""


OCRUnavailableError = OcrUnavailableError


@dataclass(slots=True)
class OcrTextLine:
    """Single OCR text line with a bounding box."""

    text: str
    bbox: BBox


@dataclass(slots=True)
class OcrTableExtraction:
    """Structured OCR table candidate derived from page detections."""

    cells: list[list[str]]
    raw_markdown: str
    raw_html: str
    header_signature: list[str]
    has_header: bool = False
    caption: str | None = None
    context_before: list[str] = field(default_factory=list)
    context_after: list[str] = field(default_factory=list)
    row_page_numbers: list[int] = field(default_factory=list)


@dataclass(slots=True)
class OcrPageResult:
    """Structured OCR output for one page."""

    text: str
    text_blocks: list[str] = field(default_factory=list)
    table_candidates: list[OcrTableExtraction] = field(default_factory=list)


class OcrEngine(Protocol):
    """Protocol for OCR adapters used by the parser."""

    def extract_page(self, page: fitz.Page) -> OcrPageResult:
        """Return structured OCR data for one page."""

    def extract_page_text(self, page: fitz.Page) -> str:
        """Return OCR text only for one page."""


class PaddleOcrEngine:
    """Thin adapter around PaddleOCR with explicit unavailable policies."""

    def __init__(self, settings: IngestionSettings) -> None:
        self.settings = settings
        self._ocr_client: Any | None = None

    def extract_page(self, page: fitz.Page) -> OcrPageResult:
        ocr_client = self._get_client()
        pixmap = page.get_pixmap(dpi=200, alpha=False)
        channels = pixmap.n
        image = numpy.frombuffer(pixmap.samples, dtype=numpy.uint8).reshape(pixmap.height, pixmap.width, channels)
        if channels == 4:
            image = image[:, :, :3]

        results = ocr_client.predict(image)
        lines = _extract_ocr_lines_v3(results) if results else []
        text_blocks = [line.text for line in lines]
        table_candidates = _extract_tables_from_lines(lines, page.number + 1)
        return OcrPageResult(
            text="\n".join(text_blocks).strip(),
            text_blocks=text_blocks,
            table_candidates=table_candidates,
        )

    def extract_page_text(self, page: fitz.Page) -> str:
        return self.extract_page(page).text

    def _get_client(self) -> Any:
        if self._ocr_client is not None:
            return self._ocr_client

        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise OcrUnavailableError("PaddleOCR is not installed. Install the paddle extra to enable OCR.") from exc

        try:
            self._ocr_client = PaddleOCR(use_textline_orientation=False, lang="en")
        except (ImportError, ModuleNotFoundError) as exc:
            raise OcrUnavailableError(
                "PaddleOCR runtime dependency (paddle) is not installed. "
                "Install paddlepaddle or paddlepaddle-gpu."
            ) from exc
        return self._ocr_client


def build_ocr_engine(settings: IngestionSettings) -> OcrEngine | None:
    """Return a runtime OCR adapter when enabled and available."""

    if not settings.enable_ocr:
        return None
    try:
        return PaddleOcrEngine(settings)
    except OcrUnavailableError:
        if settings.ocr_unavailable_policy == "error":
            raise
        return None


def _extract_ocr_lines_v3(results: Any) -> list[OcrTextLine]:
    """Parse PaddleOCR v3 .predict() results (list of OCRResult objects)."""

    lines: list[OcrTextLine] = []
    if not results:
        return lines

    for ocr_result in results:
        dt_polys = getattr(ocr_result, "dt_polys", None) or ocr_result.get("dt_polys", [])
        rec_texts = getattr(ocr_result, "rec_texts", None) or ocr_result.get("rec_texts", [])

        for poly, text in zip(dt_polys, rec_texts):
            text = str(text).strip()
            if not text:
                continue
            bbox = _normalize_bbox(poly)
            lines.append(OcrTextLine(text=text, bbox=bbox))

    return sorted(lines, key=lambda line: (_bbox_center_y(line.bbox), line.bbox[0]))


def _extract_ocr_lines(results: Any) -> list[OcrTextLine]:
    lines: list[OcrTextLine] = []
    if not results:
        return lines

    for page_result in results:
        if not page_result:
            continue
        for item in page_result:
            if not item or len(item) < 2:
                continue
            bbox = _normalize_bbox(item[0])
            text_tuple = item[1]
            if isinstance(text_tuple, (list, tuple)) and text_tuple:
                text = str(text_tuple[0]).strip()
            else:
                text = str(text_tuple).strip()
            if text:
                lines.append(OcrTextLine(text=text, bbox=bbox))

    return sorted(lines, key=lambda line: (_bbox_center_y(line.bbox), line.bbox[0]))


def _normalize_bbox(raw_bbox: Any) -> BBox:
    if isinstance(raw_bbox, (list, tuple)) and raw_bbox:
        if len(raw_bbox) == 4 and all(isinstance(value, (int, float)) for value in raw_bbox):
            x0, y0, x1, y1 = raw_bbox
            return float(x0), float(y0), float(x1), float(y1)
        points = [point for point in raw_bbox if isinstance(point, (list, tuple)) and len(point) >= 2]
        if points:
            xs = [float(point[0]) for point in points]
            ys = [float(point[1]) for point in points]
            return min(xs), min(ys), max(xs), max(ys)
    return (0.0, 0.0, 0.0, 0.0)


def _extract_tables_from_lines(lines: list[OcrTextLine], page_number: int) -> list[OcrTableExtraction]:
    clustered_rows = _cluster_lines_into_rows(lines)
    candidate_rows = [row for row in clustered_rows if len(row) >= 2]
    if len(candidate_rows) < 2:
        return []

    column_counts = [len(row) for row in candidate_rows]
    dominant_columns = max(set(column_counts), key=column_counts.count)
    if dominant_columns < 2 or column_counts.count(dominant_columns) < 2:
        return []

    rows = [_normalize_ocr_row(row, dominant_columns) for row in candidate_rows]
    if len(rows) < 2:
        return []

    table_bbox = _rows_bbox(candidate_rows)
    caption, context_before, context_after = _table_context_from_lines(lines, table_bbox)
    return [
        OcrTableExtraction(
            cells=rows,
            raw_markdown=_rows_to_markdown(rows),
            raw_html=_rows_to_html(rows),
            header_signature=list(rows[0]),
            has_header=_should_treat_first_row_as_header(rows),
            caption=caption,
            context_before=context_before,
            context_after=context_after,
            row_page_numbers=[page_number] * len(rows),
        )
    ]


def _cluster_lines_into_rows(lines: list[OcrTextLine], y_tolerance: float = 12.0) -> list[list[OcrTextLine]]:
    rows: list[list[OcrTextLine]] = []
    for line in lines:
        line_center_y = _bbox_center_y(line.bbox)
        if not rows:
            rows.append([line])
            continue

        current_row = rows[-1]
        current_center_y = sum(_bbox_center_y(item.bbox) for item in current_row) / len(current_row)
        if abs(line_center_y - current_center_y) <= y_tolerance:
            current_row.append(line)
        else:
            rows.append([line])

    for row in rows:
        row.sort(key=lambda item: item.bbox[0])
    return rows


def _normalize_ocr_row(row: list[OcrTextLine], width: int) -> list[str]:
    cells = [cell.text for cell in row]
    if len(cells) < width:
        return cells + [""] * (width - len(cells))
    if len(cells) == width:
        return cells
    overflow = " ".join(cells[width - 1 :]).strip()
    return [*cells[: width - 1], overflow]


def _should_treat_first_row_as_header(rows: list[list[str]]) -> bool:
    if len(rows) < 2:
        return False

    width = max(len(row) for row in rows)
    first = rows[0] + [""] * max(width - len(rows[0]), 0)
    second = rows[1] + [""] * max(width - len(rows[1]), 0)
    if not any(cell.strip() for cell in first):
        return False

    first_value_like = sum(1 for cell in first if _looks_value_like(cell))
    second_value_like = sum(1 for cell in second if _looks_value_like(cell))
    if first_value_like >= second_value_like:
        return False

    return any(first_cell.strip() != second_cell.strip() for first_cell, second_cell in zip(first, second))


def _looks_value_like(cell: str) -> bool:
    normalized = cell.strip().replace(",", "").replace("%", "").replace("$", "").replace("€", "")
    if not normalized:
        return False
    if normalized.replace(".", "", 1).isdigit():
        return True
    return any(char.isdigit() for char in normalized) and any(separator in normalized for separator in ("/", "-", "."))


def _table_context_from_lines(lines: list[OcrTextLine], table_bbox: BBox) -> tuple[str | None, list[str], list[str]]:
    _, y0, _, y1 = table_bbox
    before = [line.text for line in lines if line.bbox[3] <= y0]
    after = [line.text for line in lines if line.bbox[1] >= y1]
    caption = before[-1] if before else None
    return caption, before[-3:], after[:3]


def _rows_bbox(rows: list[list[OcrTextLine]]) -> BBox:
    xs0 = [cell.bbox[0] for row in rows for cell in row]
    ys0 = [cell.bbox[1] for row in rows for cell in row]
    xs1 = [cell.bbox[2] for row in rows for cell in row]
    ys1 = [cell.bbox[3] for row in rows for cell in row]
    return min(xs0), min(ys0), max(xs1), max(ys1)


def _bbox_center_y(bbox: BBox) -> float:
    return (bbox[1] + bbox[3]) / 2.0


def _rows_to_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    padded_rows = [row + [""] * (width - len(row)) for row in rows]
    header = "| " + " | ".join(padded_rows[0]) + " |"
    separator = "| " + " | ".join(["---"] * width) + " |"
    body = ["| " + " | ".join(row) + " |" for row in padded_rows[1:]]
    return "\n".join([header, separator, *body]) if body else "\n".join([header, separator])


def _rows_to_html(rows: list[list[str]]) -> str:
    html_rows: list[str] = []
    for row_index, row in enumerate(rows):
        tag = "th" if row_index == 0 else "td"
        html_rows.append("<tr>" + "".join(f"<{tag}>{cell}</{tag}>" for cell in row) + "</tr>")
    return "<table>" + "".join(html_rows) + "</table>"


PaddleOcrAdapter = PaddleOcrEngine
OCREngine = OcrEngine
