from __future__ import annotations

import pytest

from src.common.schemas import CanonicalPageRecord, ParseStatus, SourceMode, TriageLabel
from tests.support.imports import load_indexing_module
from tests.support.indexing import legal_fixture_pages, page_record, text_block


def test_build_index_chunks_carries_last_seen_headings_across_continuation_pages() -> None:
    module = load_indexing_module()
    page_one_text = (
        "PART 2 TERMINATION\n\n"
        "Section 4 Notice\n\n"
        "4. Notice period. An employer must provide thirty calendar days of written notice before termination."
    )
    continuation_text = (
        "The employee remains entitled to wages and benefits during the notice period.\n\n"
        "Payment in lieu may be agreed in writing."
    )
    pages = [
        page_record(
            doc_id="alpha",
            page_number=1,
            text=page_one_text,
            blocks=[text_block("alpha", 1, "text-1", page_one_text)],
        ),
        page_record(
            doc_id="alpha",
            page_number=2,
            text=continuation_text,
            blocks=[text_block("alpha", 2, "text-1", continuation_text)],
        ),
    ]

    chunks = module.build_index_chunks(pages)
    page_one_clause = next(chunk for chunk in chunks if chunk.chunk_id == "alpha-p1-clause-1")
    page_two_clause = next(chunk for chunk in chunks if chunk.chunk_id == "alpha-p2-clause-1")

    assert page_two_clause.section == page_one_clause.section
    assert page_two_clause.neighboring_headings == page_one_clause.neighboring_headings
    assert page_two_clause.text.startswith("The employee remains entitled")


def test_build_index_chunks_preserves_legal_numbering_and_real_section_spans() -> None:
    module = load_indexing_module()

    chunks = module.build_index_chunks(legal_fixture_pages())
    notice_clause = next(chunk for chunk in chunks if chunk.chunk_id == "alpha-p2-clause-1")
    notice_section = next(
        chunk
        for chunk in chunks
        if chunk.chunk_type == "section" and chunk.section == "Section 4 Notice"
    )
    full_notice_page = next(chunk for chunk in chunks if chunk.chunk_id == "alpha-p2-page")

    assert notice_clause.section == "Section 4 Notice"
    assert notice_clause.neighboring_headings == ["Part 2 TERMINATION", "Section 4 Notice"]
    assert notice_section.text != full_notice_page.text
    assert not notice_section.text.startswith("PART 2 TERMINATION")


def test_build_index_chunks_preserves_first_real_paragraph_when_synthesizing_clauses() -> None:
    module = load_indexing_module()
    text = (
        "PART 5 BENEFITS\n\n"
        "Section 12 Leave\n\n"
        "Employees are entitled to annual leave after completing probation.\n\n"
        "Unused leave may be carried over subject to employer approval."
    )
    page = page_record(
        doc_id="gamma",
        page_number=1,
        text=text,
        blocks=[text_block("gamma", 1, "text-1", text)],
    )

    chunks = module.build_index_chunks([page])
    clause_texts = [chunk.text for chunk in chunks if chunk.chunk_type == "clause"]
    microchunk_texts = [chunk.text for chunk in chunks if chunk.chunk_type == "microchunk"]

    assert clause_texts[0].startswith("Employees are entitled to annual leave")
    assert any(text.startswith("Employees are entitled to annual leave") for text in microchunk_texts)


def test_build_index_chunks_recognizes_article_headings_and_preserves_real_clause_labels() -> None:
    module = load_indexing_module()
    text = (
        "ARTICLE 3 GENERAL OBLIGATIONS\n\n"
        "(a) The employer must maintain a written policy manual.\n\n"
        "(1) The manual must be accessible to employees.\n\n"
        "10A Supplemental obligations apply to branch offices."
    )
    page = page_record(
        doc_id="delta",
        page_number=1,
        text=text,
        blocks=[text_block("delta", 1, "text-1", text)],
    )

    chunks = module.build_index_chunks([page])
    clause_chunks = [chunk for chunk in chunks if chunk.chunk_type == "clause"]
    section_chunk = next(chunk for chunk in chunks if chunk.chunk_type == "section")

    assert [chunk.clause for chunk in clause_chunks] == ["(a)", "(1)", "10A"]
    assert all(chunk.section == "Article 3 GENERAL OBLIGATIONS" for chunk in clause_chunks)
    assert all(chunk.neighboring_headings == ["Article 3 GENERAL OBLIGATIONS"] for chunk in clause_chunks)
    assert section_chunk.section == "Article 3 GENERAL OBLIGATIONS"


def test_build_index_chunks_preserves_orphan_lead_in_before_numbered_clauses() -> None:
    module = load_indexing_module()
    text = (
        "Section 9 Duties\n\n"
        "These duties apply to all licensed entities operating in the DIFC.\n\n"
        "(a) The entity must maintain accurate records.\n\n"
        "(1) Records must be retained for six years."
    )
    page = page_record(
        doc_id="epsilon",
        page_number=1,
        text=text,
        blocks=[text_block("epsilon", 1, "text-1", text)],
    )

    chunks = module.build_index_chunks([page])
    clause_chunks = [chunk for chunk in chunks if chunk.chunk_type == "clause"]
    microchunk_chunks = [chunk for chunk in chunks if chunk.chunk_type == "microchunk"]

    assert clause_chunks[0].clause == "lead-in"
    assert clause_chunks[0].text.startswith("These duties apply to all licensed entities")
    assert [chunk.clause for chunk in clause_chunks[1:]] == ["(a)", "(1)"]
    assert microchunk_chunks[0].clause == "lead-in"
    assert microchunk_chunks[0].text.startswith("These duties apply to all licensed entities")


def test_build_index_chunks_preserves_body_from_merged_heading_paragraph() -> None:
    module = load_indexing_module()
    text = "Section 9 Duties The entity must maintain records.\n\nAdditional rules apply."
    page = page_record(
        doc_id="zeta",
        page_number=1,
        text=text,
        blocks=[text_block("zeta", 1, "text-1", text)],
    )

    chunks = module.build_index_chunks([page])
    clause_chunks = [chunk for chunk in chunks if chunk.chunk_type == "clause"]
    section_chunk = next(chunk for chunk in chunks if chunk.chunk_type == "section")

    assert clause_chunks[0].section == "Section 9 Duties"
    assert clause_chunks[0].text.startswith("The entity must maintain records.")
    assert all("Section 9 Duties The entity must maintain records." not in chunk.text for chunk in clause_chunks)
    assert section_chunk.section == "Section 9 Duties"
    assert section_chunk.text.startswith("The entity must maintain records.")
    assert not section_chunk.text.startswith("Section 9 Duties")


def test_split_microchunks_uses_token_budget_and_overlap_when_configured() -> None:
    module = load_indexing_module()
    text = "Alpha beta gamma.\n\nDelta epsilon zeta.\n\nEta theta iota."

    microchunks = module._split_microchunks(
        text,
        token_chunk_size=6,
        token_chunk_overlap=3,
        token_counter=lambda value: len(value.replace(".", "").split()),
    )

    assert microchunks == [
        "Alpha beta gamma. Delta epsilon zeta.",
        "Delta epsilon zeta. Eta theta iota.",
    ]


def test_count_tokens_uses_qwen_compatible_counter_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_indexing_module()

    monkeypatch.setattr(
        module,
        "_resolve_qwen_token_counter",
        lambda: (lambda value: len(value.replace(" ", ""))),
    )

    assert module._count_tokens("Alpha beta") == len("Alphabeta")


def test_build_index_chunks_respects_enabled_chunk_families() -> None:
    module = load_indexing_module()

    chunks = module.build_index_chunks(
        legal_fixture_pages(),
        enabled_chunk_families={"page", "clause"},
    )

    assert chunks
    assert {chunk.chunk_type for chunk in chunks} == {"page", "clause"}


def test_build_index_chunks_preserves_w4c_structural_metadata_in_payload() -> None:
    module = load_indexing_module()
    page = CanonicalPageRecord(
        doc_id="alpha",
        page_number=1,
        document_title="Alpha Law",
        document_family="law_or_regulation",
        triage_label=TriageLabel.NATIVE_CLEAN,
        source_mode=SourceMode.NATIVE,
        parse_status=ParseStatus.PARSED,
        quality_score=0.95,
        quality_flags=[],
        parser_provenance="opendataloader:tagged",
        heading_path=["Part 1", "Section 4"],
        block_roles=["clause"],
        source_block_ids=["h1", "c1"],
        text="Section 4 Notice. Notice must be given within 30 days.",
        blocks=[text_block("alpha", 1, "text-1", "Section 4 Notice. Notice must be given within 30 days.")],
        table_ids=[],
    )

    chunks = module.build_index_chunks([page], enabled_chunk_families={"page"})

    assert len(chunks) == 1
    payload = chunks[0].payload()
    assert payload["parser_provenance"] == "opendataloader:tagged"
    assert payload["heading_path"] == ["Part 1", "Section 4"]
    assert payload["source_block_ids"] == ["h1", "c1"]


def test_format_build_index_result_reports_chunk_and_document_counts(tmp_path) -> None:
    module = load_indexing_module()
    manifest_path = tmp_path / "warmup" / "index_manifest.json"
    result = module.BuildIndexResult(
        command="build-indices",
        phase="warmup",
        dry_run=False,
        manifest_path=manifest_path,
        planned_paths=[tmp_path / "warmup" / "qdrant"],
        written_paths=[tmp_path / "warmup" / "qdrant"],
        indexed_document_count=2,
        indexed_page_count=3,
        chunk_count=11,
    )

    formatted = module.format_build_index_result(result)

    assert "command: build-indices" in formatted
    assert "indexed_document_count: 2" in formatted
    assert "indexed_page_count: 3" in formatted
    assert "chunk_count: 11" in formatted
