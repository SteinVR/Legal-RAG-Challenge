"""Native PDF parsing with optional OCR fallback and table candidate extraction."""

from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

import fitz

from src.common.config import AppConfig
from src.common.schemas import ParseStatus, SourceMode, TriageLabel

from .ocr_engine import OcrEngine, OcrUnavailableError, build_ocr_engine
from .page_triage import PageSignals, choose_source_mode, score_page_quality, triage_page

COURT_MARKERS = (
    "COURT OF",
    "SCT",
    "ARBITRATION",
    "DIGITAL ECONOMY COURT",
    "TECHNOLOGY AND CONSTRUCTION DIVISION",
    "ENFORCEMENT",
    "JUDGMENT",
    "JUDGMENTS",
    "ORDERS",
)

LEGAL_MARKERS = (
    "article",
    "section",
    "clause",
    "law",
    "court",
    "judgment",
    "order",
    "decision",
    "regulation",
)


@dataclass(slots=True)
class TableCandidate:
    """Raw table extracted from one PDF page."""

    table_id: str
    page_number: int
    raw_markdown: str | None
    raw_html: str | None
    cells: list[list[str]] = field(default_factory=list)
    header_signature: list[str] = field(default_factory=list)
    context_before: list[str] = field(default_factory=list)
    context_after: list[str] = field(default_factory=list)
    caption: str | None = None
    footnotes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PageParseResult:
    """Parsed page result consumed by corpus assembly."""

    doc_id: str
    page_number: int
    text: str
    native_text: str
    document_title: str | None
    document_family: str
    triage_label: TriageLabel
    source_mode: SourceMode
    parse_status: ParseStatus
    quality_score: float
    quality_flags: list[str] = field(default_factory=list)
    text_blocks: list[str] = field(default_factory=list)
    table_candidates: list[TableCandidate] = field(default_factory=list)


@dataclass(slots=True)
class DocumentParseResult:
    """Parsed document plus stable metadata."""

    doc_id: str
    filename: str
    sha256: str
    page_count: int
    document_title: str | None
    document_family: str
    parse_status: ParseStatus
    pages: list[PageParseResult] = field(default_factory=list)
    failure_reason: str | None = None


def parse_pdf_document(
    pdf_path: str | Path,
    config: AppConfig,
    *,
    ocr_engine: OcrEngine | None = None,
) -> DocumentParseResult:
    """Parse one PDF into page-level results suitable for corpus assembly."""

    path = Path(pdf_path)
    fitz.TOOLS.mupdf_display_warnings(False)
    fitz.TOOLS.mupdf_display_errors(False)
    effective_ocr = ocr_engine if ocr_engine is not None else build_ocr_engine(config.ingestion)

    with fitz.open(path) as document:
        first_page_text = document[0].get_text("text") if document.page_count else ""
        document_title = _extract_document_title(document, first_page_text)
        document_family = _classify_document_family(first_page_text)
        pages: list[PageParseResult] = []
        document_status = ParseStatus.PARSED

        for page in document:
            page_number = page.number + 1
            native_text = page.get_text("text").strip()
            text_blocks = _extract_text_blocks(page)
            table_candidates = _extract_table_candidates(path.stem, page, text_blocks)
            signals = _build_signals(page, native_text, len(table_candidates))
            triage_label = triage_page(signals, config.ingestion)

            ocr_text = ""
            ocr_degraded = False
            if effective_ocr is not None and triage_label in {TriageLabel.SCAN, TriageLabel.SUSPICIOUS}:
                try:
                    ocr_text = effective_ocr.extract_page_text(page)
                except OcrUnavailableError:
                    if config.ingestion.ocr_unavailable_policy == "error" and triage_label is TriageLabel.SCAN:
                        raise
                    ocr_degraded = True

            final_text, used_ocr, used_native = _select_page_text(
                native_text=native_text,
                ocr_text=ocr_text,
                triage_label=triage_label,
            )
            source_mode = choose_source_mode(
                triage_label,
                used_ocr=used_ocr,
                used_native_text=used_native,
            )
            missing_required_ocr = triage_label is TriageLabel.SCAN and not used_ocr
            parse_status = ParseStatus.DEGRADED if ocr_degraded or missing_required_ocr else ParseStatus.PARSED
            if parse_status is ParseStatus.DEGRADED:
                document_status = ParseStatus.DEGRADED

            quality_signals = _build_signals(page, final_text, len(table_candidates))
            quality = score_page_quality(quality_signals, config.ingestion)

            pages.append(
                PageParseResult(
                    doc_id=path.stem,
                    page_number=page_number,
                    text=final_text,
                    native_text=native_text,
                    document_title=document_title,
                    document_family=document_family,
                    triage_label=triage_label,
                    source_mode=source_mode,
                    parse_status=parse_status,
                    quality_score=quality.score,
                    quality_flags=quality.flags,
                    text_blocks=text_blocks,
                    table_candidates=table_candidates,
                )
            )

    return DocumentParseResult(
        doc_id=path.stem,
        filename=path.name,
        sha256=_sha256_for_file(path),
        page_count=len(pages),
        document_title=document_title,
        document_family=document_family,
        parse_status=document_status,
        pages=pages,
    )


def _extract_document_title(document: fitz.Document, first_page_text: str) -> str | None:
    metadata = document.metadata or {}
    title = (metadata.get("title") or "").strip()
    if title:
        return title
    lines = [line.strip() for line in first_page_text.splitlines() if line.strip()]
    return lines[0] if lines else None


def _classify_document_family(first_page_text: str) -> str:
    heading = " ".join(line.strip() for line in first_page_text.splitlines()[:4]).upper()
    if "LAW NO." in heading or "DIFC LAW" in heading or heading.endswith(" LAW"):
        return "law_or_regulation"
    if any(marker in heading for marker in COURT_MARKERS):
        return "court_or_arbitration_decision"
    return "other_legal_document"


def _extract_text_blocks(page: fitz.Page) -> list[str]:
    results: list[str] = []
    for block in page.get_text("blocks"):
        if len(block) < 5:
            continue
        text = str(block[4]).strip()
        if text:
            results.append(text)
    return results


def _extract_table_candidates(doc_id: str, page: fitz.Page, text_blocks: list[str]) -> list[TableCandidate]:
    candidates: list[TableCandidate] = []
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            tables = list(page.find_tables().tables)
    except Exception:
        tables = []

    for table_index, table in enumerate(tables, start=1):
        rows = _normalize_rows(_extract_rows(table))
        if not rows:
            continue
        header_signature = [cell for cell in rows[0] if cell]
        caption = text_blocks[-1] if text_blocks else None
        candidates.append(
            TableCandidate(
                table_id=f"{doc_id}-p{page.number + 1}-t{table_index}",
                page_number=page.number + 1,
                raw_markdown=_rows_to_markdown(rows),
                raw_html=_rows_to_html(rows),
                cells=rows,
                header_signature=header_signature,
                context_before=text_blocks[:3],
                context_after=text_blocks[-3:],
                caption=caption,
            )
        )
    return candidates


def _extract_rows(table: object) -> list[list[object]]:
    if hasattr(table, "extract"):
        return table.extract()
    return []


def _normalize_rows(rows: list[list[object]]) -> list[list[str]]:
    normalized: list[list[str]] = []
    for row in rows:
        normalized.append([str(cell).strip() if cell is not None else "" for cell in row])
    return normalized


def _rows_to_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized_rows = [row + [""] * (width - len(row)) for row in rows]
    header = normalized_rows[0]
    separator = ["---"] * width
    body = normalized_rows[1:] or [[""] * width]
    return "\n".join("| " + " | ".join(cell for cell in row) + " |" for row in [header, separator, *body])


def _rows_to_html(rows: list[list[str]]) -> str:
    html_rows: list[str] = []
    for row_index, row in enumerate(rows):
        tag = "th" if row_index == 0 else "td"
        html_rows.append("<tr>" + "".join(f"<{tag}>{cell}</{tag}>" for cell in row) + "</tr>")
    return "<table>" + "".join(html_rows) + "</table>"


def _build_signals(page: fitz.Page, text: str, table_count: int) -> PageSignals:
    raw_page = page.get_text("rawdict")
    blocks = raw_page.get("blocks", [])
    image_blocks = [block for block in blocks if block.get("type") == 1]
    page_area = max(page.rect.width * page.rect.height, 1.0)
    image_ratios: list[float] = []
    for block in image_blocks:
        x0, y0, x1, y1 = block.get("bbox", (0.0, 0.0, 0.0, 0.0))
        image_area = max((x1 - x0) * (y1 - y0), 0.0)
        image_ratios.append(image_area / page_area)

    return PageSignals(
        page_number=page.number + 1,
        text_char_count=len(text),
        word_count=len(text.split()),
        image_block_count=len(image_blocks),
        max_image_area_ratio=max(image_ratios, default=0.0),
        drawing_count=len(page.get_drawings()),
        table_count=table_count,
        bad_char_ratio=_bad_char_ratio(text),
        legal_marker_hits=_legal_marker_hits(text),
    )


def _bad_char_ratio(text: str) -> float:
    if not text:
        return 1.0
    bad_chars = sum(1 for char in text if char == "\ufffd" or (ord(char) < 32 and char not in "\n\r\t"))
    return bad_chars / len(text)


def _legal_marker_hits(text: str) -> list[str]:
    lowered = text.lower()
    return [marker for marker in LEGAL_MARKERS if marker in lowered]


def _select_page_text(
    *,
    native_text: str,
    ocr_text: str,
    triage_label: TriageLabel,
) -> tuple[str, bool, bool]:
    native_clean = native_text.strip()
    ocr_clean = ocr_text.strip()
    if triage_label is TriageLabel.SCAN:
        if ocr_clean:
            return ocr_clean, True, False
        return native_clean, False, bool(native_clean)
    if triage_label is TriageLabel.SUSPICIOUS and ocr_clean and len(ocr_clean) > len(native_clean):
        return ocr_clean, True, bool(native_clean)
    return native_clean, False, bool(native_clean)


def _sha256_for_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


ParsedDocument = DocumentParseResult
ParsedPage = PageParseResult
ParsedTableCandidate = TableCandidate
extract_pdf_document = parse_pdf_document


class DocumentParser:
    """Compatibility wrapper around parse_pdf_document."""

    def __init__(self, config: AppConfig, ocr_engine: OcrEngine | None = None) -> None:
        self.config = config
        self.ocr_engine = ocr_engine

    def parse_document(self, pdf_path: str | Path) -> DocumentParseResult:
        return parse_pdf_document(pdf_path, self.config, ocr_engine=self.ocr_engine)
