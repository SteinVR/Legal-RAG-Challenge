"""Native PDF parsing with OCR fallback and table candidate extraction."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import shutil
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

import fitz

from src.common.config import AppConfig
from src.common.schemas import (
    PageSignal,
    ParsedDocument,
    ParsedPage,
    ParserRoute,
    ParseStatus,
    RawParseNode,
    RawParseSidecar,
    RawParseTable,
    RawTableRecord,
    SourceMode,
    TriageLabel,
)

from .ocr_engine import OcrEngine, OcrPageResult, OcrUnavailableError, build_ocr_engine
from .opendataloader_adapter import build_opendataloader_sidecar, route_provenance
from .page_triage import score_page_quality, triage_page
from .parser_routing import DocumentStructuralProfile, ParserAvailability, resolve_parser_route

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

_OPEN_DATALOADER_PACKAGE_PATH = (
    Path(__file__).resolve().parents[2]
    / "external"
    / "opendataloader-pdf"
    / "python"
    / "opendataloader-pdf"
    / "src"
    / "opendataloader_pdf"
)


@dataclass(slots=True)
class _ResolvedPageState:
    """Final parser-owned page state before schema serialization."""

    text: str
    ocr_text: str | None
    text_blocks: list[str]
    tables: list[RawTableRecord]
    source_mode: SourceMode
    parse_status: ParseStatus
    notes: list[str] = field(default_factory=list)


def parse_pdf_document(
    pdf_path: str | Path,
    config: AppConfig,
    *,
    ocr_engine: OcrEngine | None = None,
) -> ParsedDocument:
    """Parse one PDF into the canonical parsed-document contract."""

    path = Path(pdf_path)
    fitz.TOOLS.mupdf_display_warnings(False)
    fitz.TOOLS.mupdf_display_errors(False)
    effective_ocr = ocr_engine if ocr_engine is not None else build_ocr_engine(config.ingestion)

    with fitz.open(path) as document:
        metadata_title = _extract_metadata_title(document)
        document_title = metadata_title
        document_family = "other_legal_document"
        pages: list[ParsedPage] = []
        page_geometry: dict[int, list[float]] = {}

        for page in document:
            page_number = page.number + 1
            page_geometry[page_number] = [
                float(page.rect.x0),
                float(page.rect.y0),
                float(page.rect.x1),
                float(page.rect.y1),
            ]
            native_text = page.get_text("text").strip()
            native_text_blocks = _extract_text_blocks(page)
            native_tables = _extract_table_candidates(path.stem, page_number, page, native_text_blocks)
            native_signals = _build_signals(page, native_text, len(native_tables))
            triage_label = triage_page(native_signals, config.ingestion)

            ocr_requested = triage_label in {TriageLabel.SCAN, TriageLabel.SUSPICIOUS}
            ocr_result = OcrPageResult(text="")
            ocr_unavailable = False

            if ocr_requested and effective_ocr is not None:
                try:
                    ocr_result = effective_ocr.extract_page(page)
                except OcrUnavailableError:
                    if config.ingestion.ocr_unavailable_policy == "error" and triage_label is TriageLabel.SCAN:
                        raise
                    ocr_unavailable = True
            elif ocr_requested:
                ocr_unavailable = True

            resolved = _resolve_page_state(
                doc_id=path.stem,
                page_number=page_number,
                native_text=native_text,
                native_text_blocks=native_text_blocks,
                native_tables=native_tables,
                triage_label=triage_label,
                ocr_result=ocr_result,
                ocr_requested=ocr_requested,
                ocr_unavailable=ocr_unavailable,
            )

            if page_number == 1:
                document_title = metadata_title or _extract_title_from_text(resolved.text)
                document_family = _classify_document_family(resolved.text)

            quality_signals = _build_signals(page, resolved.text, len(resolved.tables))
            quality = score_page_quality(quality_signals, config.ingestion)

            pages.append(
                ParsedPage(
                    doc_id=path.stem,
                    page_number=page_number,
                    document_title=document_title,
                    document_family=document_family,
                    triage_label=triage_label,
                    source_mode=resolved.source_mode,
                    parse_status=resolved.parse_status,
                    text=resolved.text,
                    native_text=native_text or None,
                    ocr_text=resolved.ocr_text,
                    text_blocks=resolved.text_blocks,
                    quality_score=quality.score,
                    quality_flags=quality.flags,
                    signals=quality_signals,
                    resolution_notes=resolved.notes,
                    tables=resolved.tables,
                )
            )

        parser_route = _resolve_document_route(document, pages, config)

    document_status = (
        ParseStatus.PARSED
        if all(page.parse_status is ParseStatus.PARSED for page in pages)
        else ParseStatus.DEGRADED
    )
    parser_provenance, raw_parse_sidecars = _build_raw_parse_sidecars(
        doc_id=path.stem,
        pages=pages,
        page_geometry=page_geometry,
        parser_route=parser_route,
        config=config,
    )

    return ParsedDocument(
        doc_id=path.stem,
        filename=path.name,
        sha256=_sha256_for_file(path),
        page_count=len(pages),
        document_title=document_title,
        document_family=document_family,
        parse_status=document_status,
        parser_provenance=parser_provenance,
        raw_parse_sidecars=raw_parse_sidecars,
        pages=pages,
    )


def _extract_metadata_title(document: fitz.Document) -> str | None:
    metadata = document.metadata or {}
    title = (metadata.get("title") or "").strip()
    return title or None


def _extract_title_from_text(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
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


def _extract_table_candidates(
    doc_id: str,
    page_number: int,
    page: fitz.Page,
    text_blocks: list[str],
) -> list[RawTableRecord]:
    candidates: list[RawTableRecord] = []
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            tables = list(page.find_tables().tables)
    except Exception:
        tables = []

    for table_index, table in enumerate(tables, start=1):
        rows = _normalize_rows(_extract_rows(table))
        if not rows:
            continue
        caption = text_blocks[-1] if text_blocks else None
        candidates.append(
            RawTableRecord(
                table_id=f"{doc_id}-p{page_number}-t{table_index}",
                page_number=page_number,
                rows=rows,
                row_page_numbers=[page_number] * len(rows),
                has_header=False,
                raw_markdown=_rows_to_markdown(rows),
                raw_html=_rows_to_html(rows),
                header_signature=list(rows[0]),
                caption=caption,
                preceding_context=text_blocks[:3],
                following_context=text_blocks[-3:],
            )
        )
    return candidates


def _resolve_page_state(
    *,
    doc_id: str,
    page_number: int,
    native_text: str,
    native_text_blocks: list[str],
    native_tables: list[RawTableRecord],
    triage_label: TriageLabel,
    ocr_result: OcrPageResult,
    ocr_requested: bool,
    ocr_unavailable: bool,
) -> _ResolvedPageState:
    native_clean = native_text.strip()
    ocr_clean = ocr_result.text.strip()
    notes: list[str] = []

    if ocr_unavailable:
        notes.append("ocr_unavailable")
    elif ocr_requested and not ocr_clean:
        notes.append("ocr_empty")

    if triage_label is TriageLabel.NATIVE_CLEAN:
        return _ResolvedPageState(
            text=native_clean,
            ocr_text=ocr_clean or None,
            text_blocks=native_text_blocks or _split_text_lines(native_clean),
            tables=native_tables,
            source_mode=SourceMode.NATIVE,
            parse_status=ParseStatus.PARSED,
            notes=notes,
        )

    if triage_label is TriageLabel.SCAN:
        if ocr_clean:
            notes.append("ocr_selected")
            ocr_tables = _ocr_tables_to_records(doc_id, page_number, ocr_result)
            if not ocr_tables and native_tables:
                notes.append("native_tables_fallback")
            return _ResolvedPageState(
                text=ocr_clean,
                ocr_text=ocr_clean,
                text_blocks=ocr_result.text_blocks or _split_text_lines(ocr_clean),
                tables=ocr_tables or native_tables,
                source_mode=SourceMode.OCR,
                parse_status=ParseStatus.PARSED,
                notes=notes,
            )

        return _ResolvedPageState(
            text=native_clean,
            ocr_text=None,
            text_blocks=native_text_blocks or _split_text_lines(native_clean),
            tables=native_tables,
            source_mode=SourceMode.NATIVE,
            parse_status=ParseStatus.DEGRADED,
            notes=notes,
        )

    if ocr_clean and (not native_clean or len(ocr_clean) > len(native_clean)):
        notes.append("ocr_selected")
        ocr_tables = _ocr_tables_to_records(doc_id, page_number, ocr_result)
        if not ocr_tables and native_tables:
            notes.append("native_tables_fallback")
        return _ResolvedPageState(
            text=ocr_clean,
            ocr_text=ocr_clean,
            text_blocks=ocr_result.text_blocks or _split_text_lines(ocr_clean),
            tables=ocr_tables or native_tables,
            source_mode=SourceMode.OCR,
            parse_status=ParseStatus.PARSED,
            notes=notes,
        )

    parse_status = ParseStatus.DEGRADED if ocr_requested and not ocr_clean else ParseStatus.PARSED
    return _ResolvedPageState(
        text=native_clean,
        ocr_text=ocr_clean or None,
        text_blocks=native_text_blocks or _split_text_lines(native_clean),
        tables=native_tables,
        source_mode=SourceMode.NATIVE,
        parse_status=parse_status,
        notes=notes,
    )


def _ocr_tables_to_records(doc_id: str, page_number: int, ocr_result: OcrPageResult) -> list[RawTableRecord]:
    records: list[RawTableRecord] = []
    for table_index, table in enumerate(ocr_result.table_candidates, start=1):
        rows = _normalize_rows(table.cells)
        records.append(
            RawTableRecord(
                table_id=f"{doc_id}-p{page_number}-t{table_index}",
                page_number=page_number,
                rows=rows,
                row_page_numbers=list(table.row_page_numbers or [page_number] * len(rows)),
                has_header=table.has_header,
                raw_markdown=table.raw_markdown,
                raw_html=table.raw_html,
                header_signature=list(table.header_signature or (rows[0] if rows else [])),
                caption=table.caption,
                preceding_context=list(table.context_before),
                following_context=list(table.context_after),
            )
        )
    return records


def _split_text_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


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


def _build_signals(page: fitz.Page, text: str, table_count: int) -> PageSignal:
    raw_page = page.get_text("rawdict")
    blocks = raw_page.get("blocks", [])
    image_blocks = [block for block in blocks if block.get("type") == 1]
    page_area = max(page.rect.width * page.rect.height, 1.0)
    image_ratios: list[float] = []
    for block in image_blocks:
        x0, y0, x1, y1 = block.get("bbox", (0.0, 0.0, 0.0, 0.0))
        image_area = max((x1 - x0) * (y1 - y0), 0.0)
        image_ratios.append(image_area / page_area)

    return PageSignal(
        text_char_count=len(text),
        word_count=len(text.split()),
        image_block_count=len(image_blocks),
        max_image_area_ratio=max(image_ratios, default=0.0),
        drawing_count=len(page.get_drawings()),
        table_count=table_count,
        legal_marker_count=len(_legal_marker_hits(text)),
        bad_char_ratio=_bad_char_ratio(text),
    )


def _bad_char_ratio(text: str) -> float:
    if not text:
        return 1.0
    bad_chars = sum(1 for char in text if char == "\ufffd" or (ord(char) < 32 and char not in "\n\r\t"))
    return bad_chars / len(text)


def _legal_marker_hits(text: str) -> list[str]:
    lowered = text.lower()
    return [marker for marker in LEGAL_MARKERS if marker in lowered]


def _sha256_for_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_pymupdf_sidecar(
    *,
    doc_id: str,
    pages: list[ParsedPage],
    page_geometry: dict[int, list[float]],
    parser_route: ParserRoute,
) -> RawParseSidecar:
    nodes: list[RawParseNode] = []
    tables: list[RawParseTable] = []
    for page in pages:
        for block_index, text_block in enumerate(page.text_blocks, start=1):
            nodes.append(
                RawParseNode(
                    node_id=f"{doc_id}-p{page.page_number}-b{block_index}",
                    kind="paragraph",
                    page_number=page.page_number,
                    text=text_block,
                    bbox=None,
                )
            )
        for table in page.tables:
            tables.append(
                RawParseTable(
                    table_id=table.table_id,
                    page_number=table.page_number,
                    bbox=None,
                    raw_json={"rows": table.rows} if table.rows else None,
                    raw_html=table.raw_html,
                    linked_context_block_id=None,
                )
            )

    return RawParseSidecar(
        doc_id=doc_id,
        parser_name="pymupdf",
        parser_route=parser_route,
        parser_provenance="pymupdf:native",
        page_count=len(pages),
        page_geometry=page_geometry,
        diagnostics={},
        route_decisions=[f"{parser_route.value}_selected"],
        nodes=nodes,
        tables=tables,
    )


def _build_raw_parse_sidecars(
    *,
    doc_id: str,
    pages: list[ParsedPage],
    page_geometry: dict[int, list[float]],
    parser_route: ParserRoute,
    config: AppConfig,
) -> tuple[str, dict[str, RawParseSidecar]]:
    pymupdf_sidecar = _build_pymupdf_sidecar(
        doc_id=doc_id,
        pages=pages,
        page_geometry=page_geometry,
        parser_route=parser_route,
    )
    if parser_route is ParserRoute.BASELINE_FALLBACK:
        return "pymupdf:native", {"pymupdf": pymupdf_sidecar}

    structural_sidecar = build_opendataloader_sidecar(
        doc_id=doc_id,
        pages=pages,
        page_geometry=page_geometry,
        parser_route=parser_route,
        config=config,
    )
    return route_provenance(parser_route), {
        "pymupdf": pymupdf_sidecar,
        "opendataloader": structural_sidecar,
    }


def _resolve_document_route(document: fitz.Document, pages: list[ParsedPage], config: AppConfig) -> ParserRoute:
    profile = DocumentStructuralProfile(
        has_struct_tree=_has_struct_tree(document),
        born_digital=_is_born_digital(pages, config),
        layout_complex=_is_layout_complex(pages),
    )
    availability = _parser_availability(config)
    return resolve_parser_route(profile, availability)


def _parser_availability(config: AppConfig) -> ParserAvailability:
    opendataloader_available = _is_opendataloader_available()
    hybrid_backend_healthy = (
        opendataloader_available
        and config.ingestion.opendataloader_hybrid_backend != "off"
        and bool((config.ingestion.opendataloader_hybrid_url or "").strip())
    )
    return ParserAvailability(
        opendataloader_available=opendataloader_available,
        hybrid_backend_healthy=hybrid_backend_healthy,
    )


def _is_opendataloader_available() -> bool:
    has_python_package = importlib.util.find_spec("opendataloader_pdf") is not None
    has_vendored_adapter = _OPEN_DATALOADER_PACKAGE_PATH.exists()
    has_java_runtime = shutil.which("java") is not None
    return has_python_package or has_vendored_adapter or has_java_runtime


def _has_struct_tree(document: fitz.Document) -> bool:
    try:
        catalog_xref = document.pdf_catalog()
        key_type, value = document.xref_get_key(catalog_xref, "StructTreeRoot")
    except Exception:
        return False
    return key_type != "null" and bool(str(value).strip())


def _is_born_digital(pages: list[ParsedPage], config: AppConfig) -> bool:
    native_chars = sum(len((page.native_text or "").strip()) for page in pages)
    return native_chars >= config.ingestion.extractable_text_min_chars


def _is_layout_complex(pages: list[ParsedPage]) -> bool:
    return any(
        page.signals.table_count > 0 or page.signals.drawing_count > 0 or page.signals.image_block_count > 0
        for page in pages
    )


DocumentParseResult = ParsedDocument
PageParseResult = ParsedPage
TableCandidate = RawTableRecord
ParsedTableCandidate = RawTableRecord
extract_pdf_document = parse_pdf_document


class DocumentParser:
    """Compatibility wrapper around parse_pdf_document."""

    def __init__(self, config: AppConfig, ocr_engine: OcrEngine | None = None) -> None:
        self.config = config
        self.ocr_engine = ocr_engine

    def parse_document(self, pdf_path: str | Path) -> ParsedDocument:
        return parse_pdf_document(pdf_path, self.config, ocr_engine=self.ocr_engine)
