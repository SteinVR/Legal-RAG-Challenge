from __future__ import annotations

from src.common.schemas import ParserRoute, RawParseNode, RawParseSidecar
from src.ingestion.structural_normalizer import normalize_structural_sidecar


def test_normalize_structural_sidecar_carries_heading_paths_and_block_roles() -> None:
    sidecar = RawParseSidecar(
        doc_id="alpha",
        parser_name="opendataloader",
        parser_route=ParserRoute.TAGGED,
        parser_provenance="opendataloader:tagged",
        page_count=1,
        page_geometry={1: [0.0, 0.0, 612.0, 792.0]},
        diagnostics={},
        route_decisions=["tagged_selected"],
        nodes=[
            RawParseNode(
                node_id="h1",
                kind="heading",
                page_number=1,
                text="Part 1",
                bbox=[10.0, 10.0, 100.0, 30.0],
                heading_level=1,
            ),
            RawParseNode(
                node_id="c1",
                kind="paragraph",
                page_number=1,
                text="Clause /comma.tnum 1 glyph<0> obligations",
                bbox=[10.0, 50.0, 300.0, 100.0],
            ),
            RawParseNode(
                node_id="l1",
                kind="list_item",
                page_number=1,
                text="1.1 Nested duty",
                bbox=[20.0, 110.0, 250.0, 140.0],
            ),
        ],
    )

    blocks = normalize_structural_sidecar(sidecar)
    clause = next(block for block in blocks if block.source_block_id == "c1")
    list_item = next(block for block in blocks if block.source_block_id == "l1")

    assert clause.heading_path == ["Part 1"]
    assert clause.text == "Clause , 1 obligations"
    assert "clause" in clause.block_roles
    assert list_item.heading_path == ["Part 1"]
    assert "list-item" in list_item.block_roles


def test_normalize_structural_sidecar_links_captions_to_table_context_blocks() -> None:
    sidecar = RawParseSidecar(
        doc_id="alpha",
        parser_name="opendataloader",
        parser_route=ParserRoute.HYBRID,
        parser_provenance="opendataloader:hybrid",
        page_count=1,
        page_geometry={1: [0.0, 0.0, 612.0, 792.0]},
        diagnostics={},
        route_decisions=["hybrid_selected"],
        nodes=[
            RawParseNode(
                node_id="cap-1",
                kind="caption",
                page_number=1,
                text="Schedule of fees",
                bbox=[10.0, 10.0, 200.0, 30.0],
                linked_content_id="table-1",
            ),
            RawParseNode(
                node_id="table-1",
                kind="table",
                page_number=1,
                text="",
                bbox=[10.0, 40.0, 400.0, 200.0],
            ),
        ],
    )

    blocks = normalize_structural_sidecar(sidecar)
    caption = next(block for block in blocks if block.source_block_id == "cap-1")

    assert caption.linked_content_id == "table-1"
    assert "table-context" in caption.block_roles
