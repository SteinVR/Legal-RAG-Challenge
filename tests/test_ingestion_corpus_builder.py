from __future__ import annotations

from src.common.schemas import (
    NormalizedStructuralBlock,
    PageSignal,
    ParsedDocument,
    ParsedPage,
    ParseStatus,
    SerializedTableBlock,
    SourceMode,
    TableBlock,
    TriageLabel,
)
from src.ingestion.corpus_builder import build_corpus_artifacts


def _signal() -> PageSignal:
    return PageSignal(
        text_char_count=120,
        word_count=20,
        image_block_count=0,
        max_image_area_ratio=0.0,
        drawing_count=0,
        table_count=0,
        legal_marker_count=1,
        bad_char_ratio=0.0,
    )


def _page(page_number: int, text: str) -> ParsedPage:
    return ParsedPage(
        doc_id="alpha",
        page_number=page_number,
        document_title="Employment Law",
        document_family="law_or_regulation",
        triage_label=TriageLabel.NATIVE_CLEAN,
        source_mode=SourceMode.NATIVE,
        parse_status=ParseStatus.PARSED,
        text=text,
        native_text=text,
        text_blocks=[text],
        quality_score=0.95,
        quality_flags=[],
        signals=_signal(),
        tables=[],
    )


def test_build_corpus_artifacts_emits_canonical_records_manifest_and_debug_markdown() -> None:
    document = ParsedDocument(
        doc_id="alpha",
        filename="alpha.pdf",
        sha256="deadbeef",
        page_count=1,
        document_title="Employment Law",
        document_family="law_or_regulation",
        parse_status=ParseStatus.PARSED,
        pages=[_page(1, "EMPLOYMENT LAW\nArticle 1")],
    )

    serialized_tables_by_doc = {
        "alpha": {
            1: [
                TableBlock(
                    table_id="alpha-p1-t1",
                    page_span=[1],
                    raw_markdown="| Type | Amount |\n| --- | --- |\n| Fee | 10 |",
                    raw_html="<table></table>",
                    header_signature=["Type", "Amount"],
                    serialized_blocks=[
                        SerializedTableBlock(
                            block_id="alpha-p1-t1-row-1",
                            text="Schedule of fees. Fee. Type: Fee; Amount: 10",
                            source_page_number=1,
                            row_anchor="Fee",
                            column_context=["Amount"],
                            table_caption="Schedule of fees",
                        )
                    ],
                )
            ]
        }
    }

    artifacts = build_corpus_artifacts(
        phase="warmup",
        documents=[document],
        serialized_tables_by_doc=serialized_tables_by_doc,
    )

    assert artifacts.manifest.document_count == 1
    assert artifacts.manifest.page_count == 1
    assert artifacts.page_map_records[0].page_numbers == [1]
    assert artifacts.corpus_records[0].table_ids == ["alpha-p1-t1"]
    assert any(block.table_id == "alpha-p1-t1" for block in artifacts.corpus_records[0].blocks)
    assert "## Page 1" in artifacts.debug_markdown["alpha"]
    assert [block.type for block in artifacts.corpus_records[0].blocks] == ["text", "table"]


def test_build_corpus_artifacts_preserves_source_page_for_merged_table_rows() -> None:
    document = ParsedDocument(
        doc_id="alpha",
        filename="alpha.pdf",
        sha256="deadbeef",
        page_count=2,
        document_title="Employment Law",
        document_family="law_or_regulation",
        parse_status=ParseStatus.PARSED,
        pages=[_page(1, "Page one"), _page(2, "Page two")],
    )

    merged_table = TableBlock(
        table_id="alpha-p1-t1",
        page_span=[1, 2],
        raw_markdown="| Type | Amount |\n| --- | --- |\n| Fee | 10 |\n| Tax | 5 |",
        raw_html="<table></table>",
        header_signature=["Type", "Amount"],
        serialized_blocks=[
            SerializedTableBlock(
                block_id="alpha-p1-t1-row-1",
                text="Schedule of fees. Fee. Type: Fee; Amount: 10",
                source_page_number=1,
                row_anchor="Fee",
                column_context=["Amount"],
                table_caption="Schedule of fees",
            ),
            SerializedTableBlock(
                block_id="alpha-p1-t1-row-2",
                text="Schedule of fees. Tax. Type: Tax; Amount: 5",
                source_page_number=2,
                row_anchor="Tax",
                column_context=["Amount"],
                table_caption="Schedule of fees",
            ),
        ],
    )
    serialized_tables_by_doc = {"alpha": {1: [merged_table], 2: [merged_table]}}

    artifacts = build_corpus_artifacts(
        phase="warmup",
        documents=[document],
        serialized_tables_by_doc=serialized_tables_by_doc,
    )

    page_one_blocks = [block for block in artifacts.corpus_records[0].blocks if block.type == "table"]
    page_two_blocks = [block for block in artifacts.corpus_records[1].blocks if block.type == "table"]

    assert [block.block_id for block in page_one_blocks] == ["alpha-p1-t1-row-1"]
    assert [block.block_id for block in page_two_blocks] == ["alpha-p1-t1-row-2"]
    assert artifacts.corpus_records[0].table_ids == ["alpha-p1-t1"]
    assert artifacts.corpus_records[1].table_ids == ["alpha-p1-t1"]
    assert all(block.page_number == 1 for block in page_one_blocks)
    assert all(block.page_number == 2 for block in page_two_blocks)


def test_build_corpus_artifacts_excludes_table_ids_when_no_rows_emit_on_page() -> None:
    document = ParsedDocument(
        doc_id="alpha",
        filename="alpha.pdf",
        sha256="deadbeef",
        page_count=2,
        document_title="Employment Law",
        document_family="law_or_regulation",
        parse_status=ParseStatus.PARSED,
        pages=[_page(1, "Page one"), _page(2, "Page two")],
    )

    table_block = TableBlock(
        table_id="alpha-p1-t1",
        page_span=[1, 2],
        raw_markdown="| Type | Amount |\n| --- | --- |\n| Fee | 10 |",
        raw_html="<table></table>",
        header_signature=["Type", "Amount"],
        serialized_blocks=[
            SerializedTableBlock(
                block_id="alpha-p1-t1-row-1",
                text="Schedule of fees. Fee. Type: Fee; Amount: 10",
                source_page_number=1,
                row_anchor="Fee",
                column_context=["Amount"],
                table_caption="Schedule of fees",
            )
        ],
    )

    artifacts = build_corpus_artifacts(
        phase="warmup",
        documents=[document],
        serialized_tables_by_doc={"alpha": {1: [table_block], 2: [table_block]}},
    )

    assert artifacts.corpus_records[0].table_ids == ["alpha-p1-t1"]
    assert artifacts.corpus_records[1].table_ids == []


def test_build_corpus_artifacts_table_ids_match_emitted_table_blocks_per_page() -> None:
    document = ParsedDocument(
        doc_id="alpha",
        filename="alpha.pdf",
        sha256="deadbeef",
        page_count=2,
        document_title="Employment Law",
        document_family="law_or_regulation",
        parse_status=ParseStatus.PARSED,
        pages=[_page(1, "Page one"), _page(2, "Page two")],
    )

    first_table = TableBlock(
        table_id="alpha-p1-t1",
        page_span=[1],
        raw_markdown="| Type | Amount |\n| --- | --- |\n| Fee | 10 |",
        raw_html="<table></table>",
        header_signature=["Type", "Amount"],
        serialized_blocks=[
            SerializedTableBlock(
                block_id="alpha-p1-t1-row-1",
                text="Schedule. Fee. Type: Fee; Amount: 10",
                source_page_number=1,
            )
        ],
    )
    second_table = TableBlock(
        table_id="alpha-p2-t1",
        page_span=[2],
        raw_markdown="| Type | Amount |\n| --- | --- |\n| Tax | 5 |",
        raw_html="<table></table>",
        header_signature=["Type", "Amount"],
        serialized_blocks=[
            SerializedTableBlock(
                block_id="alpha-p2-t1-row-1",
                text="Schedule. Tax. Type: Tax; Amount: 5",
                source_page_number=2,
            )
        ],
    )

    artifacts = build_corpus_artifacts(
        phase="warmup",
        documents=[document],
        serialized_tables_by_doc={"alpha": {1: [first_table], 2: [second_table]}},
    )

    assert artifacts.corpus_records[0].table_ids == ["alpha-p1-t1"]
    assert artifacts.corpus_records[1].table_ids == ["alpha-p2-t1"]


def test_build_corpus_artifacts_adds_parser_provenance_heading_path_and_source_block_ids() -> None:
    document = ParsedDocument(
        doc_id="alpha",
        filename="alpha.pdf",
        sha256="deadbeef",
        page_count=1,
        document_title="Employment Law",
        document_family="law_or_regulation",
        parse_status=ParseStatus.PARSED,
        parser_provenance="opendataloader:tagged",
        pages=[_page(1, "Clause 1")],
    )

    artifacts = build_corpus_artifacts(
        phase="warmup",
        documents=[document],
        structural_blocks_by_doc={
            "alpha": {
                1: [
                    NormalizedStructuralBlock(
                        source_block_id="h1",
                        page_number=1,
                        text="Part 1",
                        heading_path=["Part 1"],
                        block_roles=["heading"],
                    ),
                    NormalizedStructuralBlock(
                        source_block_id="c1",
                        page_number=1,
                        text="Clause 1",
                        heading_path=["Part 1"],
                        block_roles=["clause"],
                    ),
                ]
            }
        },
    )

    record = artifacts.corpus_records[0]

    assert record.parser_provenance == "opendataloader:tagged"
    assert record.heading_path == ["Part 1"]
    assert record.block_roles == ["heading", "clause"]
    assert record.source_block_ids == ["h1", "c1"]
    assert record.blocks[0].metadata["source_block_id"] == "c1"
    assert record.blocks[0].metadata["block_roles"] == ["clause"]
