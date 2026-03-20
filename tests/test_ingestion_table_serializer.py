from __future__ import annotations

from src.common.schemas import ParseStatus, SourceMode, TriageLabel
from src.ingestion.pdf_parser import DocumentParseResult, PageParseResult, TableCandidate
from src.ingestion.table_serializer import serialize_document_tables


def test_serialize_document_tables_merges_adjacent_tables_and_keeps_page_span() -> None:
    document = DocumentParseResult(
        doc_id="alpha",
        filename="alpha.pdf",
        sha256="deadbeef",
        page_count=2,
        document_title="Employment Law",
        document_family="law_or_regulation",
        parse_status=ParseStatus.PARSED,
        pages=[
            PageParseResult(
                doc_id="alpha",
                page_number=1,
                text="Page one text",
                native_text="Page one text",
                document_title="Employment Law",
                document_family="law_or_regulation",
                triage_label=TriageLabel.NATIVE_CLEAN,
                source_mode=SourceMode.NATIVE,
                parse_status=ParseStatus.PARSED,
                quality_score=0.9,
                quality_flags=[],
                text_blocks=["Table 1 continued"],
                table_candidates=[
                    TableCandidate(
                        table_id="alpha-p1-t1",
                        page_number=1,
                        raw_markdown="| Name | Value |\n| --- | --- |\n| Fee | 10 |",
                        raw_html="<table></table>",
                        cells=[["Name", "Value"], ["Fee", "10"]],
                        header_signature=["Name", "Value"],
                        context_before=["Schedule of fees"],
                        context_after=["continued"],
                        caption="Table 1",
                    )
                ],
            ),
            PageParseResult(
                doc_id="alpha",
                page_number=2,
                text="Page two text",
                native_text="Page two text",
                document_title="Employment Law",
                document_family="law_or_regulation",
                triage_label=TriageLabel.NATIVE_CLEAN,
                source_mode=SourceMode.NATIVE,
                parse_status=ParseStatus.PARSED,
                quality_score=0.9,
                quality_flags=[],
                text_blocks=["continued"],
                table_candidates=[
                    TableCandidate(
                        table_id="alpha-p2-t1",
                        page_number=2,
                        raw_markdown="| Name | Value |\n| --- | --- |\n| Tax | 5 |",
                        raw_html="<table></table>",
                        cells=[["Name", "Value"], ["Tax", "5"]],
                        header_signature=["Name", "Value"],
                        context_before=["continued"],
                        context_after=["Notes"],
                        caption="Table 1",
                    )
                ],
            ),
        ],
    )

    page_map = serialize_document_tables(document)

    assert set(page_map) == {1, 2}
    assert page_map[1][0].table_id == "alpha-p1-t1"
    assert page_map[1][0].page_span == [1, 2]
    assert [block.block_id for block in page_map[1][0].serialized_blocks] == [
        "alpha-p1-t1-row-1",
        "alpha-p1-t1-row-2",
    ]
    assert "Name: Fee; Value: 10" in page_map[1][0].serialized_blocks[0].text
    assert "Name: Tax; Value: 5" in page_map[2][0].serialized_blocks[1].text
