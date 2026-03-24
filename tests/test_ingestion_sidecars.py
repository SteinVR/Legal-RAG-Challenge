from __future__ import annotations

import json

from src.common.schemas import ParserRoute, RawParseNode, RawParseSidecar, RawParseTable
from src.ingestion.sidecars import load_raw_parse_sidecar, write_raw_parse_sidecar


def test_write_raw_parse_sidecar_round_trips_json_contract(tmp_path) -> None:
    sidecar = RawParseSidecar(
        doc_id="alpha",
        parser_name="opendataloader",
        parser_route=ParserRoute.HYBRID,
        parser_provenance="opendataloader:hybrid",
        page_count=1,
        page_geometry={1: [0.0, 0.0, 612.0, 792.0]},
        diagnostics={"hybrid_backend": "healthy"},
        route_decisions=["hybrid_selected"],
        nodes=[
            RawParseNode(
                node_id="n-1",
                kind="heading",
                page_number=1,
                text="Part 1",
                bbox=[10.0, 10.0, 100.0, 30.0],
                heading_level=1,
            )
        ],
        tables=[
            RawParseTable(
                table_id="t-1",
                page_number=1,
                bbox=[20.0, 40.0, 300.0, 200.0],
                raw_json={"rows": [["Name", "Value"], ["Fee", "10"]]},
                raw_html="<table></table>",
                linked_context_block_id="n-2",
            )
        ],
    )

    path = write_raw_parse_sidecar(tmp_path, sidecar)

    assert path.name == "alpha.json"
    assert json.loads(path.read_text(encoding="utf-8"))["parser_route"] == "hybrid"
    assert load_raw_parse_sidecar(path) == sidecar


def test_write_raw_parse_sidecar_preserves_nulls_for_parser_specific_fields(tmp_path) -> None:
    sidecar = RawParseSidecar(
        doc_id="beta",
        parser_name="pymupdf",
        parser_route=ParserRoute.BASELINE_FALLBACK,
        parser_provenance="pymupdf:native",
        page_count=1,
        page_geometry={1: [0.0, 0.0, 612.0, 792.0]},
        diagnostics={"fallback_reason": "opendataloader_unavailable"},
        route_decisions=["baseline_selected"],
        nodes=[
            RawParseNode(
                node_id="n-1",
                kind="paragraph",
                page_number=1,
                text="Plain text fallback",
                bbox=None,
                heading_level=None,
                linked_content_id=None,
            )
        ],
        tables=[
            RawParseTable(
                table_id="t-1",
                page_number=1,
                bbox=None,
                raw_json=None,
                raw_html=None,
                linked_context_block_id=None,
            )
        ],
    )

    path = write_raw_parse_sidecar(tmp_path, sidecar)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["nodes"][0]["bbox"] is None
    assert payload["tables"][0]["raw_json"] is None
    assert payload["tables"][0]["linked_context_block_id"] is None
