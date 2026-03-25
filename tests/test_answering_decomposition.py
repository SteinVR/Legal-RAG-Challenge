"""Tests for W4E cross-case decomposition module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from src.answering.decomposition import (
    SubQuestionResult,
    answer_with_decomposition,
    decompose_question,
    extract_case_refs,
    recompose_answer,
    should_decompose,
)
from src.answering.page_attribution import build_page_trace
from src.answering.service import AnswerResult, QueryMetadata
from src.common.schemas import QuestionRecord
from src.evaluation.contracts import PageReference

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _metadata(*case_ids: str, multi: bool = True) -> QueryMetadata:
    from src.answering.service import LegalEntityMetadata

    entities = tuple(
        LegalEntityMetadata(entity_type="case_id", raw_value=c, normalized_value=c, is_strong=True) for c in case_ids
    )
    return QueryMetadata(legal_entities=entities, document_title_cues=(), likely_multi_document=multi)


def _question(text: str, answer_type: str, qid: str = "q1") -> QuestionRecord:
    return QuestionRecord(id=qid, question=text, answer_type=answer_type)


def _answer_result(
    answer: Any,
    *,
    qid: str = "q1",
    confidence: float = 0.9,
    pages: list[PageReference] | None = None,
) -> AnswerResult:
    pages = pages or []
    trace = build_page_trace(
        raw_retrieved_chunk_pages=pages,
        pass_a_pages=pages,
        solver_reported_pages=[],
        final_emitted_pages=pages,
        validation_action="test",
        collapsed_answer=False,
    )
    return AnswerResult(
        question_id=qid,
        answer=answer,
        confidence=confidence,
        evidence_pages=pages,
        page_trace=trace,
    )


def _page_ref(doc_id: str = "doc1", page_numbers: list[int] | None = None) -> PageReference:
    return PageReference(doc_id=doc_id, page_numbers=page_numbers or [1])


# ---------------------------------------------------------------------------
# extract_case_refs
# ---------------------------------------------------------------------------


class TestExtractCaseRefs:
    def test_extracts_two_difc_case_refs(self) -> None:
        text = "Is there any party common to both case CFI 057/2025 and case SCT 295/2025?"
        refs = extract_case_refs(text)
        assert refs == ["CFI 057/2025", "SCT 295/2025"]

    def test_extracts_refs_without_case_prefix(self) -> None:
        text = "Between ARB 034/2025 and SCT 295/2025, which was issued first?"
        refs = extract_case_refs(text)
        assert refs == ["ARB 034/2025", "SCT 295/2025"]

    def test_deduplicates_repeated_refs(self) -> None:
        text = "In case CFI 057/2025, was CFI 057/2025 heard before SCT 295/2025?"
        refs = extract_case_refs(text)
        assert refs == ["CFI 057/2025", "SCT 295/2025"]

    def test_handles_various_prefixes(self) -> None:
        text = "DEC 001/2025 and TCD 001/2024 and ENF 269/2023 and CA 005/2025"
        refs = extract_case_refs(text)
        assert len(refs) == 4
        assert "DEC 001/2025" in refs
        assert "CA 005/2025" in refs

    def test_empty_for_no_case_refs(self) -> None:
        text = "What is Article 8 of the Operating Law?"
        assert extract_case_refs(text) == []


# ---------------------------------------------------------------------------
# should_decompose
# ---------------------------------------------------------------------------


class TestShouldDecompose:
    def test_returns_false_when_disabled(self) -> None:
        q = _question("Is X common to both case CFI 057/2025 and SCT 295/2025?", "boolean")
        meta = _metadata("CFI 057/2025", "SCT 295/2025")
        assert should_decompose(q, meta, enabled=False) is False

    def test_returns_false_for_single_case(self) -> None:
        q = _question("What is the date of case CFI 057/2025?", "boolean")
        meta = _metadata("CFI 057/2025")
        assert should_decompose(q, meta, enabled=True) is False

    def test_returns_false_for_non_decomposable_type(self) -> None:
        q = _question("Both case CFI 057/2025 and SCT 295/2025 are about...", "free_text")
        meta = _metadata("CFI 057/2025", "SCT 295/2025")
        assert should_decompose(q, meta, enabled=True) is False

    def test_returns_true_for_boolean_two_cases(self) -> None:
        q = _question("Is there any party common to both case CFI 057/2025 and SCT 295/2025?", "boolean")
        meta = _metadata("CFI 057/2025", "SCT 295/2025")
        assert should_decompose(q, meta, enabled=True) is True

    def test_returns_true_for_name_two_cases(self) -> None:
        q = _question("Which case has earlier date: CFI 057/2025 or SCT 295/2025?", "name")
        meta = _metadata("CFI 057/2025", "SCT 295/2025")
        assert should_decompose(q, meta, enabled=True) is True


# ---------------------------------------------------------------------------
# decompose_question
# ---------------------------------------------------------------------------


class TestDecomposeQuestion:
    def test_boolean_party_question_produces_names_subquestions(self) -> None:
        q = _question("Is there any main party common to both case CFI 057/2025 and case SCT 295/2025?", "boolean")
        meta = _metadata("CFI 057/2025", "SCT 295/2025")
        subs = decompose_question(q, meta)
        assert len(subs) == 2
        ref0, sq0 = subs[0]
        ref1, sq1 = subs[1]
        assert ref0 == "CFI 057/2025"
        assert ref1 == "SCT 295/2025"
        assert sq0.answer_type == "names"
        assert sq1.answer_type == "names"
        assert "CFI 057/2025" in sq0.question
        assert "SCT 295/2025" in sq1.question

    def test_boolean_judge_question_produces_names_subquestions(self) -> None:
        q = _question("Is there a judge who presided over both case CFI 057/2025 and case ENF 269/2023?", "boolean")
        meta = _metadata("CFI 057/2025", "ENF 269/2023")
        subs = decompose_question(q, meta)
        assert len(subs) == 2
        assert subs[0][1].answer_type == "names"
        assert "judge" in subs[0][1].question.lower()

    def test_name_date_comparison_produces_date_subquestions(self) -> None:
        q = _question("Which case has an earlier Date of Issue: CFI 010/2024 or CFI 016/2025?", "name")
        meta = _metadata("CFI 010/2024", "CFI 016/2025")
        subs = decompose_question(q, meta)
        assert len(subs) == 2
        assert subs[0][1].answer_type == "date"
        assert subs[1][1].answer_type == "date"

    def test_name_claim_comparison_produces_number_subquestions(self) -> None:
        q = _question("Identify the case with the higher monetary claim: SCT 169/2025 or SCT 295/2025?", "name")
        meta = _metadata("SCT 169/2025", "SCT 295/2025")
        subs = decompose_question(q, meta)
        assert len(subs) == 2
        assert subs[0][1].answer_type == "number"

    def test_generic_fallback_preserves_original_type(self) -> None:
        q = _question("Compare case CFI 057/2025 and SCT 295/2025 outcomes.", "name")
        meta = _metadata("CFI 057/2025", "SCT 295/2025")
        subs = decompose_question(q, meta)
        assert len(subs) == 2
        assert subs[0][1].answer_type == "name"

    def test_respects_max_subquestions(self) -> None:
        q = _question(
            "DEC 001/2025 and TCD 001/2024 and ENF 269/2023 and CA 005/2025 and SCT 514/2025 overlap?",
            "boolean",
        )
        meta = _metadata("DEC 001/2025", "TCD 001/2024", "ENF 269/2023", "CA 005/2025", "SCT 514/2025")
        subs = decompose_question(q, meta, max_subquestions=3)
        assert len(subs) == 3

    def test_returns_empty_for_single_case(self) -> None:
        q = _question("What about case CFI 057/2025?", "boolean")
        meta = _metadata("CFI 057/2025")
        assert decompose_question(q, meta) == []


# ---------------------------------------------------------------------------
# recompose_answer — boolean
# ---------------------------------------------------------------------------


class TestRecomposeBooleanAnswer:
    def test_intersection_found_returns_true(self) -> None:
        q = _question("Is there any party common to both?", "boolean")
        subs = [
            SubQuestionResult("CFI 057/2025", q, _answer_result(["Alice", "Bob"])),
            SubQuestionResult("SCT 295/2025", q, _answer_result(["Bob", "Charlie"])),
        ]
        result = recompose_answer(q, subs)
        assert result.answer is True

    def test_no_intersection_returns_false(self) -> None:
        q = _question("Is there any party common to both?", "boolean")
        subs = [
            SubQuestionResult("CFI 057/2025", q, _answer_result(["Alice"])),
            SubQuestionResult("SCT 295/2025", q, _answer_result(["Bob"])),
        ]
        result = recompose_answer(q, subs)
        assert result.answer is False

    def test_null_sub_answers_return_false(self) -> None:
        q = _question("Is there any party common to both?", "boolean")
        subs = [
            SubQuestionResult("CFI 057/2025", q, _answer_result(None)),
            SubQuestionResult("SCT 295/2025", q, _answer_result(None)),
        ]
        result = recompose_answer(q, subs)
        assert result.answer is False

    def test_case_insensitive_intersection(self) -> None:
        q = _question("Common judge?", "boolean")
        subs = [
            SubQuestionResult("A", q, _answer_result(["Judge Smith"])),
            SubQuestionResult("B", q, _answer_result(["judge smith"])),
        ]
        result = recompose_answer(q, subs)
        assert result.answer is True

    def test_comma_separated_string_answer(self) -> None:
        q = _question("Common party?", "boolean")
        subs = [
            SubQuestionResult("A", q, _answer_result("Alice, Bob")),
            SubQuestionResult("B", q, _answer_result("Bob, Charlie")),
        ]
        result = recompose_answer(q, subs)
        assert result.answer is True


# ---------------------------------------------------------------------------
# recompose_answer — name comparison
# ---------------------------------------------------------------------------


class TestRecomposeNameAnswer:
    def test_earlier_date_picks_smaller(self) -> None:
        q = _question("Which case has an earlier Date of Issue?", "name")
        subs = [
            SubQuestionResult("CFI 010/2024", q, _answer_result("2024-03-15")),
            SubQuestionResult("CFI 016/2025", q, _answer_result("2025-01-10")),
        ]
        result = recompose_answer(q, subs)
        assert result.answer == "CFI 010/2024"

    def test_higher_claim_picks_larger_number(self) -> None:
        q = _question("Identify the case with the higher monetary claim", "name")
        subs = [
            SubQuestionResult("SCT 169/2025", q, _answer_result("50000")),
            SubQuestionResult("SCT 295/2025", q, _answer_result("120000")),
        ]
        result = recompose_answer(q, subs)
        assert result.answer == "SCT 295/2025"

    def test_null_sub_answer_excluded(self) -> None:
        q = _question("Which case has earlier date?", "name")
        subs = [
            SubQuestionResult("A", q, _answer_result(None)),
            SubQuestionResult("B", q, _answer_result("2025-01-01")),
        ]
        result = recompose_answer(q, subs)
        assert result.answer == "B"

    def test_all_null_returns_none(self) -> None:
        q = _question("Which case has earlier date?", "name")
        subs = [
            SubQuestionResult("A", q, _answer_result(None)),
            SubQuestionResult("B", q, _answer_result(None)),
        ]
        result = recompose_answer(q, subs)
        assert result.answer is None


# ---------------------------------------------------------------------------
# Evidence page merging
# ---------------------------------------------------------------------------


class TestRecomposePreservesPages:
    def test_merges_evidence_pages_from_sub_results(self) -> None:
        q = _question("Common party?", "boolean")
        pages_a = [_page_ref("doc_a", [1, 2])]
        pages_b = [_page_ref("doc_b", [3])]
        subs = [
            SubQuestionResult("A", q, _answer_result(["X"], pages=pages_a)),
            SubQuestionResult("B", q, _answer_result(["Y"], pages=pages_b)),
        ]
        result = recompose_answer(q, subs)
        assert len(result.evidence_pages) == 2

    def test_deduplicates_evidence_pages(self) -> None:
        q = _question("Common party?", "boolean")
        shared = [_page_ref("doc1", [1])]
        subs = [
            SubQuestionResult("A", q, _answer_result(["X"], pages=shared)),
            SubQuestionResult("B", q, _answer_result(["Y"], pages=shared)),
        ]
        result = recompose_answer(q, subs)
        assert len(result.evidence_pages) == 1

    def test_page_trace_present(self) -> None:
        q = _question("Common party?", "boolean")
        subs = [
            SubQuestionResult("A", q, _answer_result(["X"], pages=[_page_ref()])),
            SubQuestionResult("B", q, _answer_result(["Y"], pages=[_page_ref("doc2")])),
        ]
        result = recompose_answer(q, subs)
        assert result.page_trace is not None
        assert result.page_trace.validation_action == "decomposition_recomposed"


# ---------------------------------------------------------------------------
# answer_with_decomposition (integration with mocked service)
# ---------------------------------------------------------------------------


class TestAnswerWithDecomposition:
    def test_calls_service_per_subquestion_and_recomposes(self) -> None:
        q = _question("Is there any party common to both case CFI 057/2025 and case SCT 295/2025?", "boolean")
        meta = _metadata("CFI 057/2025", "SCT 295/2025")

        call_count = 0

        def mock_answer(question: QuestionRecord) -> AnswerResult:
            nonlocal call_count
            call_count += 1
            if "CFI 057/2025" in question.question:
                return _answer_result(["Alice", "Bob"], pages=[_page_ref("doc_cfi")])
            return _answer_result(["Bob", "Charlie"], pages=[_page_ref("doc_sct")])

        service = MagicMock(spec=["answer_question"])
        service.answer_question.side_effect = mock_answer

        result = answer_with_decomposition(q, meta, service)

        assert service.answer_question.call_count == 2
        assert result.answer is True
        assert result.question_id == "q1"
        assert len(result.evidence_pages) == 2

    def test_falls_back_to_baseline_when_no_subquestions(self) -> None:
        q = _question("What about case CFI 057/2025?", "boolean")
        meta = _metadata("CFI 057/2025")

        service = MagicMock(spec=["answer_question"])
        service.answer_question.return_value = _answer_result(True)

        result = answer_with_decomposition(q, meta, service)
        service.answer_question.assert_called_once_with(q)
        assert result.answer is True


# ---------------------------------------------------------------------------
# Config integration
# ---------------------------------------------------------------------------


class TestDecompositionConfig:
    def test_default_config_has_decomposition_disabled(self) -> None:
        from src.common.config import AppConfig

        config = AppConfig()
        assert config.decomposition.enabled is False
        assert config.decomposition.max_subquestions == 4

    def test_env_override_enables_decomposition(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COMPETITION_DECOMPOSITION_ENABLED", "true")

        # Load with a minimal config
        import tempfile

        from src.common.config import load_app_config

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("version: v001\n")
            f.flush()
            config = load_app_config(f.name, env_file="/dev/null")

        assert config.decomposition.enabled is True
