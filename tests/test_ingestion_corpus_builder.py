from __future__ import annotations

from src.common.schemas import ParseStatus, SerializedTableBlock, SourceMode, TableBlock, TriageLabel
from src.ingestion.corpus_builder import build_corpus_artifacts
from src.ingestion.pdf_parser import DocumentParseResult, PageParseResult, TableCandidate


def test_build_corpus_artifacts_emits_canonical_records_manifest_and_debug_markdown() -> None:
    document = DocumentParseResult(
        doc_id="alpha",
        filename="alpha.pdf",
        sha256="deadbeef",
        page_count=1,
        document_title="Employment Law",
        document_family="law_or_regulation",
        parse_status=ParseStatus.PARSED,
        pages=[
            PageParseResult(
                doc_id="alpha",
                page_number=1,
                text="EMPLOYMENT LAW\nArticle 1",
                native_text="EMPLOYMENT LAW\nArticle 1",
                document_title="Employment Law",
                document_family="law_or_regulation",
                triage_label=TriageLabel.NATIVE_CLEAN,
                source_mode=SourceMode.NATIVE,
                parse_status=ParseStatus.PARSED,
                quality_score=0.95,
                quality_flags=["table_page"],
                text_blocks=["EMPLOYMENT LAW", "Article 1"],
                table_candidates=[
                    TableCandidate(
                        table_id="alpha-p1-t1",
                        page_number=1,
                        raw_markdown="| Type | Amount |\n| --- | --- |\n| Fee | 10 |",
                        raw_html="<table></table>",
                        cells=[["Type", "Amount"], ["Fee", "10"]],
                        header_signature=["Type", "Amount"],
                        context_before=["Schedule of fees"],
                        context_after=["Footnote"],
                        caption="Schedule of fees",
                    )
                ],
            )
        ],
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
