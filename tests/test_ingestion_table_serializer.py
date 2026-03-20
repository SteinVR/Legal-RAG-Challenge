from __future__ import annotations

from src.common.schemas import (
    PageSignal,
    ParsedDocument,
    ParsedPage,
    ParseStatus,
    RawTableRecord,
    SourceMode,
    TriageLabel,
)
from src.ingestion.table_serializer import serialize_document_tables


def _signal() -> PageSignal:
    return PageSignal(
        text_char_count=120,
        word_count=20,
        image_block_count=0,
        max_image_area_ratio=0.0,
        drawing_count=0,
        table_count=1,
        legal_marker_count=1,
        bad_char_ratio=0.0,
    )


def _page(page_number: int, *, tables: list[RawTableRecord]) -> ParsedPage:
    return ParsedPage(
        doc_id="alpha",
        page_number=page_number,
        document_title="Employment Law",
        document_family="law_or_regulation",
        triage_label=TriageLabel.NATIVE_CLEAN,
        source_mode=SourceMode.NATIVE,
        parse_status=ParseStatus.PARSED,
        text=f"Page {page_number} text",
        native_text=f"Page {page_number} text",
        text_blocks=[f"Page {page_number} text"],
        quality_score=0.9,
        quality_flags=[],
        signals=_signal(),
        tables=tables,
    )


def test_serialize_document_tables_merges_adjacent_tables_and_keeps_row_provenance() -> None:
    document = ParsedDocument(
        doc_id="alpha",
        filename="alpha.pdf",
        sha256="deadbeef",
        page_count=2,
        document_title="Employment Law",
        document_family="law_or_regulation",
        parse_status=ParseStatus.PARSED,
        pages=[
            _page(
                1,
                tables=[
                    RawTableRecord(
                        table_id="alpha-p1-t1",
                        page_number=1,
                        rows=[["Name", "Value"], ["Fee", "10"]],
                        row_page_numbers=[1, 1],
                        has_header=True,
                        raw_markdown="| Name | Value |\n| --- | --- |\n| Fee | 10 |",
                        raw_html="<table></table>",
                        header_signature=["Name", "Value"],
                        caption="Table 1",
                        preceding_context=["Schedule of fees"],
                        following_context=["continued"],
                    )
                ],
            ),
            _page(
                2,
                tables=[
                    RawTableRecord(
                        table_id="alpha-p2-t1",
                        page_number=2,
                        rows=[["Name", "Value"], ["Tax", "5"]],
                        row_page_numbers=[2, 2],
                        has_header=True,
                        raw_markdown="| Name | Value |\n| --- | --- |\n| Tax | 5 |",
                        raw_html="<table></table>",
                        header_signature=["Name", "Value"],
                        caption="Table 1",
                        preceding_context=["continued"],
                        following_context=["Notes"],
                    )
                ],
            ),
        ],
    )

    page_map = serialize_document_tables(document)

    assert set(page_map) == {1, 2}
    assert page_map[1][0].table_id == "alpha-p1-t1"
    assert page_map[1][0].page_span == [1, 2]
    assert [block.source_page_number for block in page_map[1][0].serialized_blocks] == [1, 2]
    assert "Name: Fee; Value: 10" in page_map[1][0].serialized_blocks[0].text
    assert "Name: Tax; Value: 5" in page_map[2][0].serialized_blocks[1].text


def test_serialize_document_tables_keeps_first_row_for_headerless_tables() -> None:
    document = ParsedDocument(
        doc_id="alpha",
        filename="alpha.pdf",
        sha256="deadbeef",
        page_count=1,
        document_title="Employment Law",
        document_family="law_or_regulation",
        parse_status=ParseStatus.PARSED,
        pages=[
            _page(
                1,
                tables=[
                    RawTableRecord(
                        table_id="alpha-p1-t1",
                        page_number=1,
                        rows=[["Fee", "10"], ["Tax", "5"]],
                        row_page_numbers=[1, 1],
                        has_header=False,
                        raw_markdown="| Fee | 10 |\n| --- | --- |\n| Tax | 5 |",
                        raw_html="<table></table>",
                        header_signature=["", ""],
                        caption="Schedule of fees",
                    )
                ],
            )
        ],
    )

    page_map = serialize_document_tables(document)
    serialized = page_map[1][0].serialized_blocks

    assert [block.block_id for block in serialized] == ["alpha-p1-t1-row-1", "alpha-p1-t1-row-2"]
    assert "column_1: Fee; column_2: 10" in serialized[0].text
    assert "column_1: Tax; column_2: 5" in serialized[1].text


def test_serialize_document_tables_preserves_all_non_empty_rows_for_headerless_tables() -> None:
    document = ParsedDocument(
        doc_id="alpha",
        filename="alpha.pdf",
        sha256="deadbeef",
        page_count=1,
        document_title="Employment Law",
        document_family="law_or_regulation",
        parse_status=ParseStatus.PARSED,
        pages=[
            _page(
                1,
                tables=[
                    RawTableRecord(
                        table_id="alpha-p1-t1",
                        page_number=1,
                        rows=[["Fee", "10"], ["", ""], ["Tax", "5"], ["Surcharge", "2"]],
                        row_page_numbers=[1, 1, 1, 1],
                        has_header=False,
                        raw_markdown="| Fee | 10 |\n| --- | --- |\n| Tax | 5 |\n| Surcharge | 2 |",
                        raw_html="<table></table>",
                        header_signature=["", ""],
                        caption="Schedule of fees",
                    )
                ],
            )
        ],
    )

    serialized = serialize_document_tables(document)[1][0].serialized_blocks

    assert [block.block_id for block in serialized] == [
        "alpha-p1-t1-row-1",
        "alpha-p1-t1-row-3",
        "alpha-p1-t1-row-4",
    ]
    assert [block.source_page_number for block in serialized] == [1, 1, 1]


def test_serialize_document_tables_explicit_header_does_not_emit_header_as_data() -> None:
    document = ParsedDocument(
        doc_id="alpha",
        filename="alpha.pdf",
        sha256="deadbeef",
        page_count=1,
        document_title="Employment Law",
        document_family="law_or_regulation",
        parse_status=ParseStatus.PARSED,
        pages=[
            _page(
                1,
                tables=[
                    RawTableRecord(
                        table_id="alpha-p1-t1",
                        page_number=1,
                        rows=[["Type", "Amount"], ["Fee", "10"], ["Tax", "5"]],
                        row_page_numbers=[1, 1, 1],
                        has_header=True,
                        raw_markdown="| Type | Amount |\n| --- | --- |\n| Fee | 10 |\n| Tax | 5 |",
                        raw_html="<table></table>",
                        header_signature=["Type", "Amount"],
                        caption="Schedule of fees",
                    )
                ],
            )
        ],
    )

    serialized = serialize_document_tables(document)[1][0].serialized_blocks

    assert [block.block_id for block in serialized] == ["alpha-p1-t1-row-1", "alpha-p1-t1-row-2"]
    assert all("Type: Type" not in block.text for block in serialized)


def test_serialize_document_tables_preserves_blank_header_positions() -> None:
    document = ParsedDocument(
        doc_id="alpha",
        filename="alpha.pdf",
        sha256="deadbeef",
        page_count=1,
        document_title="Employment Law",
        document_family="law_or_regulation",
        parse_status=ParseStatus.PARSED,
        pages=[
            _page(
                1,
                tables=[
                    RawTableRecord(
                        table_id="alpha-p1-t1",
                        page_number=1,
                        rows=[["", "Amount"], ["Fee", "10"]],
                        row_page_numbers=[1, 1],
                        has_header=True,
                        raw_markdown="|  | Amount |\n| --- | --- |\n| Fee | 10 |",
                        raw_html="<table></table>",
                        header_signature=["", "Amount"],
                        caption="Schedule of fees",
                    )
                ],
            )
        ],
    )

    page_map = serialize_document_tables(document)
    table_block = page_map[1][0]

    assert table_block.header_signature == ["", "Amount"]
    assert "column_1: Fee; Amount: 10" in table_block.serialized_blocks[0].text


def test_serialize_document_tables_does_not_merge_headerless_tables_without_continuation_cue() -> None:
    document = ParsedDocument(
        doc_id="alpha",
        filename="alpha.pdf",
        sha256="deadbeef",
        page_count=2,
        document_title="Employment Law",
        document_family="law_or_regulation",
        parse_status=ParseStatus.PARSED,
        pages=[
            _page(
                1,
                tables=[
                    RawTableRecord(
                        table_id="alpha-p1-t1",
                        page_number=1,
                        rows=[["Fee", "10"]],
                        row_page_numbers=[1],
                        has_header=False,
                        raw_markdown="| Fee | 10 |",
                        raw_html="<table></table>",
                        header_signature=["", ""],
                        caption="Table A",
                    )
                ],
            ),
            _page(
                2,
                tables=[
                    RawTableRecord(
                        table_id="alpha-p2-t1",
                        page_number=2,
                        rows=[["Tax", "5"]],
                        row_page_numbers=[2],
                        has_header=False,
                        raw_markdown="| Tax | 5 |",
                        raw_html="<table></table>",
                        header_signature=["", ""],
                        caption="Table A",
                    )
                ],
            ),
        ],
    )

    page_map = serialize_document_tables(document)

    assert page_map[1][0].table_id == "alpha-p1-t1"
    assert page_map[2][0].table_id == "alpha-p2-t1"


def test_serialize_document_tables_merges_headerless_tables_with_continuation_cue() -> None:
    document = ParsedDocument(
        doc_id="alpha",
        filename="alpha.pdf",
        sha256="deadbeef",
        page_count=2,
        document_title="Employment Law",
        document_family="law_or_regulation",
        parse_status=ParseStatus.PARSED,
        pages=[
            _page(
                1,
                tables=[
                    RawTableRecord(
                        table_id="alpha-p1-t1",
                        page_number=1,
                        rows=[["Fee", "10"]],
                        row_page_numbers=[1],
                        has_header=False,
                        raw_markdown="| Fee | 10 |",
                        raw_html="<table></table>",
                        header_signature=["", ""],
                        caption="Table A",
                        following_context=["continued"],
                    )
                ],
            ),
            _page(
                2,
                tables=[
                    RawTableRecord(
                        table_id="alpha-p2-t1",
                        page_number=2,
                        rows=[["Tax", "5"]],
                        row_page_numbers=[2],
                        has_header=False,
                        raw_markdown="| Tax | 5 |",
                        raw_html="<table></table>",
                        header_signature=["", ""],
                        caption="Table A",
                        preceding_context=["continued"],
                    )
                ],
            ),
        ],
    )

    page_map = serialize_document_tables(document)
    merged = page_map[1][0]

    assert merged.table_id == "alpha-p1-t1"
    assert merged.page_span == [1, 2]
    assert [block.source_page_number for block in merged.serialized_blocks] == [1, 2]
