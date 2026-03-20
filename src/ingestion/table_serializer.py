"""Rule-based table detection, merging, and serialization."""

from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz

from src.common.config import AppConfig
from src.common.schemas import SerializedTableBlock, TableBlock


@dataclass(slots=True)
class TableCandidate:
    """Intermediate detected table before merge/serialization."""

    table_id: str
    page_span: list[int]
    rows: list[list[str]]
    raw_markdown: str
    raw_html: str
    header_signature: list[str]
    caption: str | None = None
    context_before: list[str] = field(default_factory=list)
    context_after: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PageTableAssignments:
    """Serialized tables grouped by page number."""

    by_page: dict[int, list[TableBlock]]


def extract_document_tables(pdf_path: str | Path) -> list[TableBlock]:
    """Detect, merge, and serialize tables for one document."""

    candidates = detect_tables(pdf_path)
    merged = merge_adjacent_tables(candidates)
    return [serialize_table(candidate) for candidate in merged]


def serialize_document_tables(document: Any) -> dict[int, list[TableBlock]]:
    """Serialize already extracted table candidates on a parsed document."""

    candidates: list[TableCandidate] = []
    for page in getattr(document, "pages", []):
        for candidate in getattr(page, "table_candidates", []):
            candidates.append(
                TableCandidate(
                    table_id=candidate.table_id,
                    page_span=[candidate.page_number],
                    rows=_normalize_rows(_extract_candidate_rows(candidate)),
                    raw_markdown=getattr(candidate, "raw_markdown", "") or "",
                    raw_html=getattr(candidate, "raw_html", "") or "",
                    header_signature=list(getattr(candidate, "header_signature", [])),
                    caption=getattr(candidate, "caption", None),
                    context_before=list(getattr(candidate, "context_before", [])),
                    context_after=list(getattr(candidate, "context_after", [])),
                )
            )
    merged = merge_adjacent_tables(candidates)
    page_map: dict[int, list[TableBlock]] = {}
    for candidate in merged:
        block = serialize_table(candidate)
        for page_number in candidate.page_span:
            page_map.setdefault(page_number, []).append(block)
    return page_map


def _extract_candidate_rows(candidate: Any) -> list[list[Any]]:
    for field_name in ("rows", "cells"):
        rows = getattr(candidate, field_name, None)
        if rows:
            return rows

    return []


def detect_tables(pdf_path: str | Path) -> list[TableCandidate]:
    """Detect tables from a PDF using PyMuPDF table extraction."""

    candidates: list[TableCandidate] = []
    doc_id = Path(pdf_path).stem
    with fitz.open(pdf_path) as document:
        for page in document:
            page_number = page.number + 1
            text_blocks = _extract_page_text_blocks(page)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                try:
                    tables = list(page.find_tables().tables)
                except Exception:
                    tables = []

            for table_index, table in enumerate(tables, start=1):
                rows = _normalize_rows(_extract_rows(table))
                if not rows:
                    continue

                caption, context_before, context_after = _table_context(text_blocks, getattr(table, "bbox", None))
                header_signature = _header_signature(rows)
                table_id = f"{doc_id}-table-{page_number}-{table_index}"
                candidates.append(
                    TableCandidate(
                        table_id=table_id,
                        page_span=[page_number],
                        rows=rows,
                        raw_markdown=_rows_to_markdown(rows),
                        raw_html=_rows_to_html(rows),
                        header_signature=header_signature,
                        caption=caption,
                        context_before=context_before,
                        context_after=context_after,
                    )
                )
    return candidates


def merge_adjacent_tables(candidates: list[TableCandidate]) -> list[TableCandidate]:
    """Merge consecutive-page tables when headers and continuation cues match."""

    if not candidates:
        return []

    merged: list[TableCandidate] = []
    current = candidates[0]
    for candidate in candidates[1:]:
        if _should_merge(current, candidate):
            merged_rows = _merge_rows(current.rows, candidate.rows)
            current = TableCandidate(
                table_id=current.table_id,
                page_span=[*current.page_span, *candidate.page_span],
                rows=merged_rows,
                raw_markdown=_rows_to_markdown(merged_rows),
                raw_html=_rows_to_html(merged_rows),
                header_signature=current.header_signature,
                caption=current.caption or candidate.caption,
                context_before=current.context_before,
                context_after=candidate.context_after,
            )
            continue

        merged.append(current)
        current = candidate

    merged.append(current)
    return merged


def serialize_table(candidate: TableCandidate) -> TableBlock:
    """Convert a detected table into the canonical table block."""

    rows = candidate.rows
    headers = _header_signature(rows)
    data_rows = rows[1:] if len(rows) > 1 and headers else rows
    serialized_blocks: list[SerializedTableBlock] = []
    legal_context = candidate.context_before[-2:] if candidate.context_before else []
    footnotes = candidate.context_after[:2] if candidate.context_after else []

    for row_index, row in enumerate(data_rows, start=1):
        if not any(cell for cell in row):
            continue

        row_anchor = row[0] if row else None
        pairs: list[str] = []
        for column_index, cell in enumerate(row):
            if not cell:
                continue
            header = headers[column_index] if column_index < len(headers) else f"column_{column_index + 1}"
            pairs.append(f"{header}: {cell}")

        if not pairs:
            continue

        lead = candidate.caption or "Table"
        block_text = f"{lead}. " if lead else ""
        if row_anchor:
            block_text += f"{row_anchor}. "
        block_text += "; ".join(pairs)
        if legal_context:
            block_text += f" Context: {' '.join(legal_context)}"
        if footnotes:
            block_text += f" Notes: {' '.join(footnotes)}"

        serialized_blocks.append(
            SerializedTableBlock(
                block_id=f"{candidate.table_id}-row-{row_index}",
                text=block_text.strip(),
                row_anchor=row_anchor,
                column_context=headers[1:] if len(headers) > 1 else headers,
                table_caption=candidate.caption,
                footnotes=footnotes,
                legal_context=legal_context,
            )
        )

    if not serialized_blocks:
        serialized_blocks.append(
            SerializedTableBlock(
                block_id=f"{candidate.table_id}-summary",
                text=(candidate.caption or "Table") + ". " + candidate.raw_markdown.strip(),
                table_caption=candidate.caption,
                footnotes=footnotes,
                legal_context=legal_context,
            )
        )

    return TableBlock(
        table_id=candidate.table_id,
        page_span=candidate.page_span,
        raw_markdown=candidate.raw_markdown,
        raw_html=candidate.raw_html,
        header_signature=headers,
        serialized_blocks=serialized_blocks,
    )


def _extract_rows(table: Any) -> list[list[Any]]:
    if hasattr(table, "extract"):
        return table.extract()

    if hasattr(table, "to_pandas"):
        frame = table.to_pandas()
        return [list(frame.columns)] + frame.fillna("").values.tolist()

    return []


def _normalize_rows(rows: list[list[Any]]) -> list[list[str]]:
    normalized: list[list[str]] = []
    for row in rows:
        normalized.append([str(cell).strip() if cell is not None else "" for cell in row])
    return normalized


def _header_signature(rows: list[list[str]]) -> list[str]:
    if not rows:
        return []
    return [cell for cell in rows[0] if cell]


def _merge_rows(first_rows: list[list[str]], second_rows: list[list[str]]) -> list[list[str]]:
    if not first_rows:
        return second_rows
    if not second_rows:
        return first_rows

    first_headers = _header_signature(first_rows)
    second_headers = _header_signature(second_rows)
    if first_headers and first_headers == second_headers:
        return first_rows + second_rows[1:]
    return first_rows + second_rows


def _should_merge(previous: TableCandidate, current: TableCandidate) -> bool:
    if not previous.page_span or not current.page_span:
        return False
    if current.page_span[0] != previous.page_span[-1] + 1:
        return False
    if not previous.header_signature or previous.header_signature != current.header_signature:
        return False

    previous_caption = (previous.caption or "").strip().lower()
    current_caption = (current.caption or "").strip().lower()
    if previous_caption and current_caption and previous_caption == current_caption:
        return True

    continuation_cues = ("continued", "continuation", "cont.")
    current_before = " ".join(current.context_before).lower()
    previous_after = " ".join(previous.context_after).lower()
    return any(cue in current_before or cue in previous_after for cue in continuation_cues)


def _extract_page_text_blocks(page: fitz.Page) -> list[tuple[tuple[float, float, float, float], str]]:
    blocks = page.get_text("blocks")
    results: list[tuple[tuple[float, float, float, float], str]] = []
    for block in blocks:
        x0, y0, x1, y1, text = block[:5]
        cleaned = str(text).strip()
        if cleaned:
            results.append(((x0, y0, x1, y1), cleaned))
    return results


def _table_context(
    text_blocks: list[tuple[tuple[float, float, float, float], str]],
    table_bbox: tuple[float, float, float, float] | None,
) -> tuple[str | None, list[str], list[str]]:
    if table_bbox is None:
        lines = [text for _, text in text_blocks]
        caption = lines[-1] if lines else None
        return caption, lines[-3:], []

    _, y0, _, y1 = table_bbox
    before = [text for (_, _, _, by1), text in text_blocks if by1 <= y0]
    after = [text for (_, by0, _, _), text in text_blocks if by0 >= y1]
    caption = before[-1] if before else None
    return caption, before[-3:], after[:3]


def _rows_to_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    widths = max(len(row) for row in rows)
    padded_rows = [row + [""] * (widths - len(row)) for row in rows]
    header = "| " + " | ".join(padded_rows[0]) + " |"
    separator = "| " + " | ".join(["---"] * widths) + " |"
    body = ["| " + " | ".join(row) + " |" for row in padded_rows[1:]]
    return "\n".join([header, separator, *body]) if body else "\n".join([header, separator])


def _rows_to_html(rows: list[list[str]]) -> str:
    table_rows = []
    for row_index, row in enumerate(rows):
        tag = "th" if row_index == 0 else "td"
        cells = "".join(f"<{tag}>{cell}</{tag}>" for cell in row)
        table_rows.append(f"<tr>{cells}</tr>")
    return "<table>" + "".join(table_rows) + "</table>"


class TableSerializer:
    """Compatibility wrapper around the functional serializer helpers."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def serialize_document(self, document: Any) -> PageTableAssignments:
        page_map = serialize_document_tables(document)
        return PageTableAssignments(by_page=page_map)
