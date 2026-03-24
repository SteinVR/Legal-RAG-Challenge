"""Structural sidecar adapter for routed opendataloader parses."""

from __future__ import annotations

import re

from src.common.config import AppConfig
from src.common.schemas import ParsedPage, ParserRoute, RawParseNode, RawParseSidecar, RawParseTable

_LIST_ITEM_PATTERN = re.compile(r"^(?:[-*]|[0-9]+[.)]|[A-Za-z][.)])\s+")
_PART_PREFIXES = ("part ", "chapter ", "appendix ")
_SECTION_PREFIXES = ("article ", "section ", "schedule ")


def build_opendataloader_sidecar(
    *,
    doc_id: str,
    pages: list[ParsedPage],
    page_geometry: dict[int, list[float]],
    parser_route: ParserRoute,
    config: AppConfig,
) -> RawParseSidecar:
    """Project a routed structural parse into the raw sidecar contract."""

    nodes: list[RawParseNode] = []
    tables: list[RawParseTable] = []
    for page in pages:
        for block_index, text_block in enumerate(page.text_blocks, start=1):
            kind, heading_level = _classify_text_block(text_block)
            nodes.append(
                RawParseNode(
                    node_id=f"{doc_id}-p{page.page_number}-s{block_index}",
                    kind=kind,
                    page_number=page.page_number,
                    text=text_block,
                    bbox=None,
                    heading_level=heading_level,
                )
            )

        for table in page.tables:
            caption_node_id = None
            if table.caption:
                caption_node_id = f"{table.table_id}-caption"
                nodes.append(
                    RawParseNode(
                        node_id=caption_node_id,
                        kind="caption",
                        page_number=table.page_number,
                        text=table.caption,
                        bbox=None,
                        linked_content_id=table.table_id,
                    )
                )
            nodes.append(
                RawParseNode(
                    node_id=f"{table.table_id}-node",
                    kind="table",
                    page_number=table.page_number,
                    text=table.raw_markdown or table.caption or "",
                    bbox=None,
                    linked_content_id=caption_node_id,
                )
            )
            tables.append(
                RawParseTable(
                    table_id=table.table_id,
                    page_number=table.page_number,
                    bbox=None,
                    raw_json={"rows": table.rows} if table.rows else None,
                    raw_html=table.raw_html,
                    linked_context_block_id=caption_node_id,
                )
            )

    return RawParseSidecar(
        doc_id=doc_id,
        parser_name="opendataloader",
        parser_route=parser_route,
        parser_provenance=_route_provenance(parser_route),
        page_count=len(pages),
        page_geometry=page_geometry,
        diagnostics={
            "adapter_mode": "projected",
            "table_method": config.ingestion.opendataloader_table_method,
            "reading_order": config.ingestion.opendataloader_reading_order,
            "hybrid_backend": config.ingestion.opendataloader_hybrid_backend,
            "hybrid_mode": config.ingestion.opendataloader_hybrid_mode,
        },
        route_decisions=[f"{parser_route.value}_selected", "opendataloader_adapter_projection"],
        nodes=nodes,
        tables=tables,
    )


def route_provenance(parser_route: ParserRoute) -> str:
    """Expose the parser provenance string for one routed structural parse."""

    return _route_provenance(parser_route)


def _route_provenance(parser_route: ParserRoute) -> str:
    suffix = {
        ParserRoute.TAGGED: "tagged",
        ParserRoute.HYBRID: "hybrid",
        ParserRoute.LOCAL_ONLY: "local_only",
    }.get(parser_route)
    if suffix is None:
        return "pymupdf:native"
    return f"opendataloader:{suffix}"


def _classify_text_block(text: str) -> tuple[str, int | None]:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if not first_line:
        return "paragraph", None

    normalized = first_line.rstrip(":").strip()
    lowered = normalized.lower()
    if normalized.isupper() and len(normalized.split()) <= 12:
        return "heading", 1
    if any(lowered.startswith(prefix) for prefix in _PART_PREFIXES):
        return "heading", 1
    if any(lowered.startswith(prefix) for prefix in _SECTION_PREFIXES):
        return "heading", 2
    if _LIST_ITEM_PATTERN.match(normalized):
        return "list_item", None
    return "paragraph", None
