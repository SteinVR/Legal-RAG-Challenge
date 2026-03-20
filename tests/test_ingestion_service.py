from __future__ import annotations

import json
from pathlib import Path

from src.common.config import AppConfig
from src.common.schemas import ParseStatus, SourceMode, TriageLabel
from src.ingestion.pdf_parser import DocumentParseResult, PageParseResult, TableCandidate
from src.ingestion.service import CorpusParseService


class StubParser:
    def __init__(self, document: DocumentParseResult) -> None:
        self.document = document

    def parse_document(self, pdf_path: str | Path) -> DocumentParseResult:
        del pdf_path
        return self.document


def test_parse_corpus_writes_serialized_table_blocks(tmp_path: Path) -> None:
    config = AppConfig.model_validate(
        {
            "storage": {"root_dir": str(tmp_path / "data")},
            "ingestion": {"enable_ocr": False},
        }
    )
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    (documents_dir / "alpha.pdf").write_bytes(b"%PDF-1.4\n")

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
                text="Employment Law\nArticle 1",
                native_text="Employment Law\nArticle 1",
                document_title="Employment Law",
                document_family="law_or_regulation",
                triage_label=TriageLabel.NATIVE_CLEAN,
                source_mode=SourceMode.NATIVE,
                parse_status=ParseStatus.PARSED,
                quality_score=0.9,
                quality_flags=["has_tables"],
                text_blocks=["Schedule of fees"],
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

    service = CorpusParseService(config)
    service.parser = StubParser(document)

    result = service.parse_corpus(overwrite=True)

    corpus_path = tmp_path / "data" / "warmup" / "corpus" / "corpus.jsonl"
    corpus_rows = [json.loads(line) for line in corpus_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert result.parsed_document_count == 1
    assert corpus_rows[0]["table_ids"] == ["alpha-p1-t1"]
    assert any(
        block["type"] == "table" and block["table_id"] == "alpha-p1-t1"
        for block in corpus_rows[0]["blocks"]
    )
