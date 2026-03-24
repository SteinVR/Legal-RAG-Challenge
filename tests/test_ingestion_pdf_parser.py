from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from src.common.config import AppConfig
from src.common.schemas import ParserRoute, ParseStatus, SourceMode, TriageLabel
from src.ingestion.ocr_engine import (
    OcrPageResult,
    OcrTableExtraction,
    _should_treat_first_row_as_header,
)
from src.ingestion.pdf_parser import _has_struct_tree, parse_pdf_document


def _write_pdf(path: Path, *, pages: list[str], title: str | None = None) -> None:
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    if title:
        document.set_metadata({"title": title})
    document.save(path)
    document.close()


class StubOcrEngine:
    def __init__(self, page_results: list[OcrPageResult]) -> None:
        self._page_results = page_results
        self.calls = 0

    def extract_page(self, page: fitz.Page) -> OcrPageResult:
        del page
        result = self._page_results[self.calls]
        self.calls += 1
        return result


def _long_native_text() -> str:
    return (
        "DIFC LAW NO. 1\nArticle 1\n"
        "This law governs employment relations, notice periods, remedies, "
        "jurisdiction, compliance obligations, and administrative procedures "
        "for all covered parties in detailed legal language. "
        "It also defines employer duties, worker protections, documentary "
        "evidence standards, enforcement pathways, administrative penalties, "
        "transitional arrangements, exemptions, appeal routes, and procedural "
        "time limits across multiple fact patterns."
    )


def _suspicious_native_text() -> str:
    return (
        "Article 1\n"
        "Short legal text with enough words to avoid scan routing but still remain "
        "below the suspicious threshold for native parsing quality."
    )


def test_parse_pdf_document_extracts_title_family_and_pages(tmp_path: Path) -> None:
    pdf_path = tmp_path / "alpha.pdf"
    _write_pdf(
        pdf_path,
        pages=[
            (
                "DIFC LAW NO. 1\nArticle 1\nSection 1\nThis law governs employment and procedures. "
                "It defines scope, jurisdiction, obligations, notice periods, remedies, enforcement pathways, "
                "and transitional provisions in detailed legal language for the employment framework."
            ),
            (
                "Article 2\nSection 2\nThis provision defines the duties of the parties in detail. "
                "It specifies compliance requirements, formal notices, documentary evidence, payment timing, "
                "and administrative obligations across multiple scenarios to preserve a clean native page."
            ),
        ],
        title="DIFC Law",
    )
    config = AppConfig.model_validate({"ingestion": {"enable_ocr": False, "suspicious_text_max_chars": 10}})

    parsed = parse_pdf_document(pdf_path, config)

    assert parsed.doc_id == "alpha"
    assert parsed.document_title == "DIFC Law"
    assert parsed.document_family == "law_or_regulation"
    assert parsed.page_count == 2
    assert parsed.parse_status is ParseStatus.PARSED
    assert all(page.source_mode is SourceMode.NATIVE for page in parsed.pages)
    assert parsed.pages[0].triage_label is TriageLabel.NATIVE_CLEAN


def test_parse_pdf_document_emits_pymupdf_raw_parse_sidecar(tmp_path: Path) -> None:
    pdf_path = tmp_path / "alpha.pdf"
    _write_pdf(pdf_path, pages=["DIFC LAW NO. 1\nArticle 1"])
    config = AppConfig.model_validate({"ingestion": {"enable_ocr": False}})

    parsed = parse_pdf_document(pdf_path, config)

    sidecar = parsed.raw_parse_sidecars["pymupdf"]
    assert sidecar.parser_route is not None
    assert sidecar.parser_provenance == "pymupdf:native"
    assert sidecar.page_geometry[1] == [0.0, 0.0, 595.0, 842.0]
    assert sidecar.nodes[0].text == "DIFC LAW NO. 1\nArticle 1"


def test_parse_pdf_document_uses_resolved_parser_route_in_raw_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "alpha.pdf"
    _write_pdf(pdf_path, pages=["DIFC LAW NO. 1\nArticle 1"])
    config = AppConfig.model_validate({"ingestion": {"enable_ocr": False}})

    monkeypatch.setattr(
        "src.ingestion.pdf_parser.resolve_parser_route",
        lambda *_args, **_kwargs: ParserRoute.HYBRID,
    )

    parsed = parse_pdf_document(pdf_path, config)

    sidecar = parsed.raw_parse_sidecars["pymupdf"]
    assert sidecar.parser_route is ParserRoute.HYBRID
    assert sidecar.route_decisions == ["hybrid_selected"]


def test_parse_pdf_document_emits_structural_sidecar_and_provenance_for_routed_opendataloader_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "alpha.pdf"
    _write_pdf(pdf_path, pages=["Part 1\nArticle 1\nSchedule of fees"])
    config = AppConfig.model_validate({"ingestion": {"enable_ocr": False}})

    monkeypatch.setattr(
        "src.ingestion.pdf_parser.resolve_parser_route",
        lambda *_args, **_kwargs: ParserRoute.TAGGED,
    )

    parsed = parse_pdf_document(pdf_path, config)

    assert parsed.parser_provenance == "opendataloader:tagged"
    assert "opendataloader" in parsed.raw_parse_sidecars
    structural_sidecar = parsed.raw_parse_sidecars["opendataloader"]
    assert structural_sidecar.parser_route is ParserRoute.TAGGED
    assert structural_sidecar.parser_provenance == "opendataloader:tagged"
    assert structural_sidecar.nodes


def test_has_struct_tree_treats_xref_key_as_present() -> None:
    class StubDocument:
        def pdf_catalog(self) -> int:
            return 1

        def xref_get_key(self, xref: int, key: str) -> tuple[str, str]:
            assert xref == 1
            assert key == "StructTreeRoot"
            return ("xref", "5 0 R")

    assert _has_struct_tree(StubDocument()) is True


def test_parse_pdf_document_marks_empty_page_as_degraded_when_ocr_is_unavailable(tmp_path: Path) -> None:
    pdf_path = tmp_path / "scan_like.pdf"
    _write_pdf(pdf_path, pages=[""])
    config = AppConfig()

    parsed = parse_pdf_document(pdf_path, config, ocr_engine=None)

    assert parsed.page_count == 1
    assert parsed.parse_status is ParseStatus.DEGRADED
    assert parsed.pages[0].triage_label is TriageLabel.SCAN
    assert parsed.pages[0].parse_status is ParseStatus.DEGRADED


def test_parse_pdf_document_marks_scan_page_as_degraded_when_ocr_is_disabled(tmp_path: Path) -> None:
    pdf_path = tmp_path / "scan_like.pdf"
    _write_pdf(pdf_path, pages=[""])
    config = AppConfig.model_validate({"ingestion": {"enable_ocr": False}})

    parsed = parse_pdf_document(pdf_path, config)

    assert parsed.page_count == 1
    assert parsed.parse_status is ParseStatus.DEGRADED
    assert parsed.pages[0].triage_label is TriageLabel.SCAN
    assert parsed.pages[0].parse_status is ParseStatus.DEGRADED


def test_parse_pdf_document_marks_short_scan_text_as_degraded_without_ocr(tmp_path: Path) -> None:
    pdf_path = tmp_path / "short_scan.pdf"
    _write_pdf(pdf_path, pages=["Court order"])
    config = AppConfig.model_validate({"ingestion": {"enable_ocr": False}})

    parsed = parse_pdf_document(pdf_path, config)

    assert parsed.page_count == 1
    assert parsed.parse_status is ParseStatus.DEGRADED
    assert parsed.pages[0].triage_label is TriageLabel.SCAN
    assert parsed.pages[0].text == "Court order"
    assert parsed.pages[0].parse_status is ParseStatus.DEGRADED


@pytest.mark.parametrize(
    (
        "config",
        "page_text",
        "ocr_result",
        "expected_triage",
        "expected_source_mode",
        "expected_status",
        "expected_calls",
    ),
    [
        (
            AppConfig.model_validate({"ingestion": {"suspicious_text_max_chars": 50}}),
            _long_native_text(),
            OcrPageResult(text="Should not be used"),
            TriageLabel.NATIVE_CLEAN,
            SourceMode.NATIVE,
            ParseStatus.PARSED,
            0,
        ),
        (
            AppConfig(),
            "",
            OcrPageResult(text=""),
            TriageLabel.SCAN,
            SourceMode.NATIVE,
            ParseStatus.DEGRADED,
            1,
        ),
        (
            AppConfig(),
            "",
            OcrPageResult(text="DIFC LAW NO. 1\nArticle 1"),
            TriageLabel.SCAN,
            SourceMode.OCR,
            ParseStatus.PARSED,
            1,
        ),
        (
            AppConfig(),
            _suspicious_native_text(),
            OcrPageResult(text="Article 1"),
            TriageLabel.SUSPICIOUS,
            SourceMode.NATIVE,
            ParseStatus.PARSED,
            1,
        ),
        (
            AppConfig(),
            _suspicious_native_text(),
            OcrPageResult(
                text=(
                    "DIFC LAW NO. 1\nArticle 1\nDetailed OCR replacement text with additional clauses, "
                    "cross-references, remedies, timelines, and procedural obligations exceeding the native text."
                )
            ),
            TriageLabel.SUSPICIOUS,
            SourceMode.OCR,
            ParseStatus.PARSED,
            1,
        ),
    ],
)
def test_parse_pdf_document_resolution_matrix(
    tmp_path: Path,
    config: AppConfig,
    page_text: str,
    ocr_result: OcrPageResult,
    expected_triage: TriageLabel,
    expected_source_mode: SourceMode,
    expected_status: ParseStatus,
    expected_calls: int,
) -> None:
    pdf_path = tmp_path / "matrix.pdf"
    _write_pdf(pdf_path, pages=[page_text])
    ocr_engine = StubOcrEngine([ocr_result])

    parsed = parse_pdf_document(pdf_path, config, ocr_engine=ocr_engine)

    assert parsed.pages[0].triage_label is expected_triage
    assert parsed.pages[0].source_mode is expected_source_mode
    assert parsed.pages[0].parse_status is expected_status
    assert ocr_engine.calls == expected_calls


def test_parse_pdf_document_marks_suspicious_native_page_as_degraded_when_ocr_is_disabled(tmp_path: Path) -> None:
    pdf_path = tmp_path / "suspicious_no_ocr.pdf"
    _write_pdf(pdf_path, pages=[_suspicious_native_text()])
    config = AppConfig.model_validate({"ingestion": {"enable_ocr": False}})

    parsed = parse_pdf_document(pdf_path, config)

    assert parsed.pages[0].triage_label is TriageLabel.SUSPICIOUS
    assert parsed.pages[0].source_mode is SourceMode.NATIVE
    assert parsed.pages[0].parse_status is ParseStatus.DEGRADED
    assert parsed.parse_status is ParseStatus.DEGRADED


def test_parse_pdf_document_uses_ocr_tables_and_recomputes_first_page_metadata(tmp_path: Path) -> None:
    pdf_path = tmp_path / "ocr_first_page.pdf"
    _write_pdf(pdf_path, pages=[""])
    config = AppConfig()
    ocr_engine = StubOcrEngine(
        [
            OcrPageResult(
                text="DIFC LAW NO. 1\nArticle 1",
                text_blocks=["Schedule of fees", "Type Amount", "Fee 10"],
                table_candidates=[
                    OcrTableExtraction(
                        cells=[["Type", "Amount"], ["Fee", "10"]],
                        raw_markdown="| Type | Amount |\n| --- | --- |\n| Fee | 10 |",
                        raw_html="<table></table>",
                        header_signature=["Type", "Amount"],
                        has_header=True,
                        caption="Schedule of fees",
                        context_before=["Schedule of fees"],
                        context_after=["Footnote"],
                        row_page_numbers=[1, 1],
                    )
                ],
            )
        ]
    )

    parsed = parse_pdf_document(pdf_path, config, ocr_engine=ocr_engine)

    assert parsed.document_title == "DIFC LAW NO. 1"
    assert parsed.document_family == "law_or_regulation"
    assert parsed.pages[0].source_mode is SourceMode.OCR
    assert parsed.pages[0].text == "DIFC LAW NO. 1\nArticle 1"
    assert parsed.pages[0].document_title == "DIFC LAW NO. 1"
    assert parsed.pages[0].document_family == "law_or_regulation"
    assert parsed.pages[0].tables[0].rows == [["Type", "Amount"], ["Fee", "10"]]
    assert parsed.pages[0].tables[0].row_page_numbers == [1, 1]
    assert parsed.pages[0].tables[0].has_header is True


def test_parse_pdf_document_preserves_ocr_header_semantics_for_blank_leading_header(tmp_path: Path) -> None:
    pdf_path = tmp_path / "ocr_header_preserved.pdf"
    _write_pdf(pdf_path, pages=[""])
    config = AppConfig()
    ocr_engine = StubOcrEngine(
        [
            OcrPageResult(
                text="Schedule of fees\nFee 10",
                text_blocks=["Schedule of fees", "Fee 10"],
                table_candidates=[
                    OcrTableExtraction(
                        cells=[["", "Amount"], ["Fee", "10"]],
                        raw_markdown="|  | Amount |\n| --- | --- |\n| Fee | 10 |",
                        raw_html="<table></table>",
                        header_signature=["", "Amount"],
                        has_header=True,
                        caption="Schedule of fees",
                        context_before=["Schedule of fees"],
                        context_after=["Footnote"],
                        row_page_numbers=[1, 1],
                    )
                ],
            )
        ]
    )

    parsed = parse_pdf_document(pdf_path, config, ocr_engine=ocr_engine)

    assert parsed.pages[0].source_mode is SourceMode.OCR
    assert parsed.pages[0].tables[0].has_header is True
    assert parsed.pages[0].tables[0].header_signature == ["", "Amount"]


def test_ocr_header_inference_keeps_headerless_rows_as_data() -> None:
    assert _should_treat_first_row_as_header([["Fee", "10"], ["Tax", "5"]]) is False
    assert _should_treat_first_row_as_header([["", "Amount"], ["Fee", "10"]]) is True


def test_ocr_header_inference_is_conservative_for_value_like_first_rows() -> None:
    assert _should_treat_first_row_as_header([["Year", "2024"], ["Fee", "10"]]) is False
    assert _should_treat_first_row_as_header([["2024", "10"], ["Fee", "Tax"]]) is False
    assert _should_treat_first_row_as_header([["Type", "Amount"], ["Fee", "10"]]) is True


def test_parse_pdf_document_marks_suspicious_ocr_replacement_as_ocr(tmp_path: Path) -> None:
    pdf_path = tmp_path / "suspicious.pdf"
    _write_pdf(pdf_path, pages=["Article 1"])
    config = AppConfig()
    ocr_engine = StubOcrEngine(
        [
            OcrPageResult(
                text="DIFC LAW NO. 1\nArticle 1\nDetailed OCR replacement text.",
                text_blocks=["DIFC LAW NO. 1", "Article 1", "Detailed OCR replacement text."],
                table_candidates=[],
            )
        ]
    )

    parsed = parse_pdf_document(pdf_path, config, ocr_engine=ocr_engine)

    assert parsed.pages[0].triage_label is TriageLabel.SCAN or parsed.pages[0].triage_label is TriageLabel.SUSPICIOUS
    assert parsed.pages[0].source_mode is SourceMode.OCR
    assert parsed.pages[0].text.startswith("DIFC LAW NO. 1")


def test_parse_pdf_document_aggregates_document_status_from_page_statuses(tmp_path: Path) -> None:
    pdf_path = tmp_path / "mixed.pdf"
    _write_pdf(pdf_path, pages=[_long_native_text(), ""])
    config = AppConfig.model_validate({"ingestion": {"suspicious_text_max_chars": 50}})
    ocr_engine = StubOcrEngine([OcrPageResult(text="Recovered OCR page 2 text.")])

    parsed = parse_pdf_document(pdf_path, config, ocr_engine=ocr_engine)

    assert parsed.pages[0].parse_status is ParseStatus.PARSED
    assert parsed.pages[1].parse_status is ParseStatus.PARSED
    assert parsed.parse_status is ParseStatus.PARSED

    degraded = parse_pdf_document(
        pdf_path,
        AppConfig.model_validate({"ingestion": {"enable_ocr": False}}),
    )
    assert degraded.pages[1].parse_status is ParseStatus.DEGRADED
    assert degraded.parse_status is ParseStatus.DEGRADED
