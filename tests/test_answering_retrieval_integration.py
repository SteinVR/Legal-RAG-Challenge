from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from src.answering.page_attribution import CandidatePage, PageAttributionConfig, PassAResult
from src.answering.service import AnsweringService
from src.common.schemas import QuestionRecord
from src.evaluation.contracts import PageReference
from src.retrieval.service import RetrievalResult, RetrievedChunk
from tests.support.imports import load_page_attribution_module as _load_page_attribution_module


class StubProvider:
    def __init__(self, response: Mapping[str, Any]) -> None:
        self._response = dict(response)
        self.calls: list[dict[str, Any]] = []

    def generate(self, *, question: str, evidence_pages: list[dict[str, Any]], max_chars: int) -> dict[str, Any]:
        self.calls.append(
            {
                "question": question,
                "evidence_pages": list(evidence_pages),
                "max_chars": max_chars,
            }
        )
        return dict(self._response)


class StructuredProviderStub:
    def __init__(self, response: Mapping[str, Any]) -> None:
        self._response = dict(response)
        self.calls: list[dict[str, Any]] = []

    def generate(self, **_: Any) -> dict[str, Any]:
        raise AssertionError(
            "TASK-W4B retrieval-backed typed solving must use `generate_structured(...)`, not `generate(...)`."
        )

    def generate_structured(
        self,
        *,
        question: str,
        answer_type: str,
        evidence_pages: list[dict[str, Any]],
        answer_schema: type[Any],
        reasoning_effort: str,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "question": question,
                "answer_type": answer_type,
                "evidence_pages": list(evidence_pages),
                "answer_schema": answer_schema,
                "reasoning_effort": reasoning_effort,
            }
        )
        return dict(self._response)


class RetrievalResultRetriever:
    def __init__(self, result: RetrievalResult) -> None:
        self._result = result
        self.calls: list[QuestionRecord] = []
        self.query_metadata: list[Any] = []

    def retrieve(self, question: QuestionRecord, *, query_metadata: Any | None = None) -> RetrievalResult:
        self.calls.append(question)
        self.query_metadata.append(query_metadata)
        return self._result


def test_answering_service_accepts_retrieval_result_for_deterministic_answers() -> None:
    question = QuestionRecord(id="q-number", question="What is the administrative fine?", answer_type="number")
    retrieval = RetrievalResult(
        question_id=question.id,
        query=question.question,
        answer_type=question.answer_type,
        candidate_count=2,
        reranked_count=1,
        evidence_chunks=[
            RetrievedChunk(
                chunk_id="c1",
                doc_id="alpha",
                page_span=[2],
                chunk_type="clause",
                text="The administrative fine is AED 500.",
                retrieval_score=0.91,
            )
        ],
        retrieved_chunk_pages=[PageReference(doc_id="alpha", page_numbers=[2])],
        is_unanswerable=False,
    )
    retriever = RetrievalResultRetriever(retrieval)
    provider = StubProvider({"answer": "unused", "confidence": 0.0})
    service = AnsweringService(retriever=retriever, provider=provider)

    result = service.answer_question(question)

    assert result.question_id == "q-number"
    assert result.answer == 500
    assert result.confidence == 1.0
    assert result.evidence_pages == [PageReference(doc_id="alpha", page_numbers=[2])]
    assert [call.id for call in retriever.calls] == ["q-number"]
    assert provider.calls == []


def test_answering_service_accepts_retrieval_result_for_free_text_answers() -> None:
    question = QuestionRecord(id="q-free", question="Summarize the order.", answer_type="free_text")
    retrieval = RetrievalResult(
        question_id=question.id,
        query=question.question,
        answer_type=question.answer_type,
        candidate_count=3,
        reranked_count=2,
        evidence_chunks=[
            RetrievedChunk(
                chunk_id="c1",
                doc_id="alpha",
                page_span=[2, 3],
                chunk_type="clause",
                text="The tribunal dismissed the claim and ordered payment within 14 days.",
                retrieval_score=0.88,
            )
        ],
        retrieved_chunk_pages=[PageReference(doc_id="alpha", page_numbers=[2, 3])],
        is_unanswerable=False,
    )
    retriever = RetrievalResultRetriever(retrieval)
    provider = StubProvider(
        {
            "answer": "The tribunal dismissed the claim and ordered payment within 14 days.",
            "confidence": 0.83,
        }
    )
    service = AnsweringService(retriever=retriever, provider=provider)

    result = service.answer_question(question)
    page_attribution = _load_page_attribution_module()
    page_trace = result.page_trace

    assert result.question_id == "q-free"
    assert result.answer == "The tribunal dismissed the claim and ordered payment within 14 days."
    assert result.confidence == 0.83
    assert result.evidence_pages == [PageReference(doc_id="alpha", page_numbers=[2, 3])]
    assert isinstance(page_trace, page_attribution.PageAttributionTrace)
    assert page_trace.raw_retrieved_chunk_pages == [PageReference(doc_id="alpha", page_numbers=[2, 3])]
    assert page_trace.pass_a_pages == [PageReference(doc_id="alpha", page_numbers=[2, 3])]
    assert page_trace.solver_reported_pages == []
    assert page_trace.final_emitted_pages == [PageReference(doc_id="alpha", page_numbers=[2, 3])]
    assert page_trace.validation_action == "preserved_pages"
    assert page_trace.collapsed_answer is False
    assert provider.calls == [
        {
            "question": "Summarize the order.",
            "evidence_pages": [
                {
                    "doc_id": "alpha",
                    "page_number": 2,
                    "page_numbers": [2, 3],
                    "text": "The tribunal dismissed the claim and ordered payment within 14 days.",
                }
            ],
            "max_chars": 280,
        }
    ]


def test_w4a_pass_a_prunes_title_pages_before_free_text_answering() -> None:
    question = QuestionRecord(id="q-free", question="Summarize the order.", answer_type="free_text")
    retrieval = RetrievalResult(
        question_id=question.id,
        query=question.question,
        answer_type=question.answer_type,
        candidate_count=3,
        reranked_count=2,
        evidence_chunks=[
            RetrievedChunk(
                chunk_id="cover",
                doc_id="alpha",
                page_span=[1],
                chunk_type="title",
                text="Service Agreement Table of Contents",
                retrieval_score=0.92,
                rerank_score=0.99,
            ),
            RetrievedChunk(
                chunk_id="c1",
                doc_id="alpha",
                page_span=[3],
                chunk_type="clause",
                text="The tribunal dismissed the claim and ordered payment within 14 days.",
                retrieval_score=0.81,
                rerank_score=0.94,
            ),
        ],
        retrieved_chunk_pages=[PageReference(doc_id="alpha", page_numbers=[1, 3])],
        is_unanswerable=False,
    )
    retriever = RetrievalResultRetriever(retrieval)
    provider = StubProvider(
        {
            "answer": "The tribunal dismissed the claim and ordered payment within 14 days.",
            "confidence": 0.83,
        }
    )
    service = AnsweringService(retriever=retriever, provider=provider)

    result = service.answer_question(question)
    page_attribution = _load_page_attribution_module()
    page_trace = result.page_trace

    assert isinstance(page_trace, page_attribution.PageAttributionTrace)
    assert page_trace.raw_retrieved_chunk_pages == [PageReference(doc_id="alpha", page_numbers=[1, 3])]
    assert page_trace.pass_a_pages == [PageReference(doc_id="alpha", page_numbers=[3])]
    assert page_trace.final_emitted_pages == [PageReference(doc_id="alpha", page_numbers=[3])]
    assert page_trace.validation_action == "preserved_pages"
    assert result.evidence_pages == [PageReference(doc_id="alpha", page_numbers=[3])]
    assert provider.calls == [
        {
            "question": "Summarize the order.",
            "evidence_pages": [
                {
                    "doc_id": "alpha",
                    "page_number": 3,
                    "page_numbers": [3],
                    "text": "The tribunal dismissed the claim and ordered payment within 14 days.",
                }
            ],
            "max_chars": 280,
        }
    ]


def test_w4a_pass_a_ablation_clips_multi_page_span_without_forcing_no_answer() -> None:
    question = QuestionRecord(id="q-free", question="Summarize the order.", answer_type="free_text")
    retrieval = RetrievalResult(
        question_id=question.id,
        query=question.question,
        answer_type=question.answer_type,
        candidate_count=1,
        reranked_count=1,
        evidence_chunks=[
            RetrievedChunk(
                chunk_id="c1",
                doc_id="alpha",
                page_span=[1, 3],
                chunk_type="clause",
                text=(
                    "Service Agreement Table of Contents. "
                    "The tribunal dismissed the claim and ordered payment within 14 days."
                ),
                retrieval_score=0.91,
                rerank_score=0.95,
            )
        ],
        retrieved_chunk_pages=[PageReference(doc_id="alpha", page_numbers=[1, 3])],
        is_unanswerable=False,
    )
    retriever = RetrievalResultRetriever(retrieval)
    provider = StubProvider(
        {
            "answer": "The tribunal dismissed the claim and ordered payment within 14 days.",
            "confidence": 0.84,
        }
    )
    service = AnsweringService(
        retriever=retriever,
        provider=provider,
        page_attribution_config=PageAttributionConfig(suppress_repeated_boilerplate=False),
    )

    result = service.answer_question(question)

    assert result.answer == "The tribunal dismissed the claim and ordered payment within 14 days."
    assert result.evidence_pages == [PageReference(doc_id="alpha", page_numbers=[3])]
    assert result.page_trace is not None
    assert result.page_trace.raw_retrieved_chunk_pages == [PageReference(doc_id="alpha", page_numbers=[1, 3])]
    assert result.page_trace.pass_a_pages == [PageReference(doc_id="alpha", page_numbers=[3])]
    assert result.page_trace.final_emitted_pages == [PageReference(doc_id="alpha", page_numbers=[3])]
    assert provider.calls == [
        {
            "question": "Summarize the order.",
            "evidence_pages": [
                {
                    "doc_id": "alpha",
                    "page_number": 3,
                    "page_numbers": [3],
                    "text": "The tribunal dismissed the claim and ordered payment within 14 days.",
                }
            ],
            "max_chars": 280,
        }
    ]


def test_w4a_pass_a_fallback_for_non_contiguous_pages_does_not_leak_middle_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    question = QuestionRecord(id="q-free", question="Summarize the order.", answer_type="free_text")
    retrieval = RetrievalResult(
        question_id=question.id,
        query=question.question,
        answer_type=question.answer_type,
        candidate_count=1,
        reranked_count=1,
        evidence_chunks=[
            RetrievedChunk(
                chunk_id="c1",
                doc_id="alpha",
                page_span=[1, 2, 3],
                chunk_type="clause",
                text=(
                    "Procedural background on page one. "
                    "Middle excluded boilerplate from page two. "
                    "The tribunal dismissed the claim on page three."
                ),
                retrieval_score=0.91,
                rerank_score=0.95,
            )
        ],
        retrieved_chunk_pages=[PageReference(doc_id="alpha", page_numbers=[1, 2, 3])],
        is_unanswerable=False,
    )
    retriever = RetrievalResultRetriever(retrieval)
    provider = StubProvider(
        {
            "answer": "The tribunal dismissed the claim on page three.",
            "confidence": 0.84,
        }
    )

    def fake_prune_candidate_pages(*_args: Any, **_kwargs: Any) -> PassAResult:
        return PassAResult(
            selected_pages=[
                CandidatePage(doc_id="alpha", page_number=1, text="Procedural background on page one."),
                CandidatePage(doc_id="alpha", page_number=3, text="The tribunal dismissed the claim on page three."),
            ],
            suppressed_pages=[
                CandidatePage(doc_id="alpha", page_number=2, text="Middle excluded boilerplate from page two.")
            ],
        )

    monkeypatch.setattr("src.answering.service.prune_candidate_pages", fake_prune_candidate_pages)

    service = AnsweringService(retriever=retriever, provider=provider)

    result = service.answer_question(question)

    assert result.answer == "The tribunal dismissed the claim on page three."
    assert provider.calls
    evidence_pages = provider.calls[0]["evidence_pages"]
    all_page_numbers = {page_number for page in evidence_pages for page_number in page["page_numbers"]}
    combined_text = " ".join(page["text"] for page in evidence_pages)

    assert all_page_numbers == {1, 3}
    assert 2 not in all_page_numbers
    assert "Middle excluded boilerplate from page two." not in combined_text
    assert "Procedural background on page one." in combined_text
    assert "The tribunal dismissed the claim on page three." in combined_text


def test_w4b_structured_no_answer_preserves_pages_when_emit_empty_pages_is_disabled() -> None:
    question = QuestionRecord(id="q-name", question="Who is the appointed liquidator?", answer_type="name")
    retrieval = RetrievalResult(
        question_id=question.id,
        query=question.question,
        answer_type=question.answer_type,
        candidate_count=1,
        reranked_count=1,
        evidence_chunks=[
            RetrievedChunk(
                chunk_id="c1",
                doc_id="alpha",
                page_span=[3],
                chunk_type="clause",
                text="Page 3 identifies the respondent but not the liquidator.",
                retrieval_score=0.84,
            )
        ],
        retrieved_chunk_pages=[PageReference(doc_id="alpha", page_numbers=[3])],
        is_unanswerable=False,
    )
    retriever = RetrievalResultRetriever(retrieval)
    provider = StructuredProviderStub(
        {
            "is_answerable": False,
            "final_answer": None,
            "relevant_pages": [3],
            "reasoning_summary": "The retrieved page does not identify a liquidator.",
            "confidence": 0.0,
        }
    )
    service = AnsweringService(
        retriever=retriever,
        provider=provider,
        page_attribution_config=PageAttributionConfig(emit_empty_pages_for_no_answer=False),
    )

    result = service.answer_question(question)

    assert result.answer is None
    assert result.confidence == 0.0
    assert result.evidence_pages == [PageReference(doc_id="alpha", page_numbers=[3])]
    assert result.page_trace is not None
    assert result.page_trace.raw_retrieved_chunk_pages == [PageReference(doc_id="alpha", page_numbers=[3])]
    assert result.page_trace.pass_a_pages == [PageReference(doc_id="alpha", page_numbers=[3])]
    assert result.page_trace.solver_reported_pages == [PageReference(doc_id="alpha", page_numbers=[3])]
    assert result.page_trace.final_emitted_pages == [PageReference(doc_id="alpha", page_numbers=[3])]
    assert result.page_trace.collapsed_answer is False


def test_w4b_relevant_pages_only_narrow_existing_retrieval_pages() -> None:
    question = QuestionRecord(id="q-name", question="Who is the appointed liquidator?", answer_type="name")
    retrieval = RetrievalResult(
        question_id=question.id,
        query=question.question,
        answer_type=question.answer_type,
        candidate_count=3,
        reranked_count=2,
        evidence_chunks=[
            RetrievedChunk(
                chunk_id="c1",
                doc_id="alpha",
                page_span=[3],
                chunk_type="clause",
                text="Page 3 states that the appointed liquidator is Jane Smith.",
                retrieval_score=0.93,
            ),
            RetrievedChunk(
                chunk_id="c2",
                doc_id="beta",
                page_span=[7],
                chunk_type="clause",
                text="The respondent is Beta Holdings.",
                retrieval_score=0.71,
            ),
        ],
        retrieved_chunk_pages=[
            PageReference(doc_id="alpha", page_numbers=[3]),
            PageReference(doc_id="beta", page_numbers=[7]),
        ],
        is_unanswerable=False,
    )
    retriever = RetrievalResultRetriever(retrieval)
    provider = StructuredProviderStub(
        {
            "is_answerable": True,
            "final_answer": "Jane Smith",
            "relevant_pages": [3, 99],
            "reasoning_summary": "Only page 3 from the retrieved evidence supports the appointment.",
            "confidence": 0.89,
        }
    )
    service = AnsweringService(retriever=retriever, provider=provider)

    result = service.answer_question(question)

    assert result.answer == "Jane Smith"
    assert result.confidence == 0.89
    assert result.evidence_pages == [PageReference(doc_id="alpha", page_numbers=[3])]
    assert len(provider.calls) == 1
    assert provider.calls[0]["question"] == "Who is the appointed liquidator?"
    assert provider.calls[0]["answer_type"] == "name"
    assert provider.calls[0]["reasoning_effort"] == "high"
    assert provider.calls[0]["evidence_pages"] == [
        {
            "doc_id": "alpha",
            "page_number": 3,
            "page_numbers": [3],
            "text": "Page 3 states that the appointed liquidator is Jane Smith.",
        },
        {
            "doc_id": "beta",
            "page_number": 7,
            "page_numbers": [7],
            "text": "The respondent is Beta Holdings.",
        },
    ]


def test_w4b_solver_page_narrowing_drops_partial_multi_page_chunks() -> None:
    question = QuestionRecord(id="q-number", question="What is the administrative fine?", answer_type="number")
    retrieval = RetrievalResult(
        question_id=question.id,
        query=question.question,
        answer_type=question.answer_type,
        candidate_count=1,
        reranked_count=1,
        evidence_chunks=[
            RetrievedChunk(
                chunk_id="c1",
                doc_id="alpha",
                page_span=[1, 3],
                chunk_type="clause",
                text="Service Agreement Table of Contents. The administrative fine is AED 500.",
                retrieval_score=0.93,
                rerank_score=0.97,
            ),
        ],
        retrieved_chunk_pages=[PageReference(doc_id="alpha", page_numbers=[1, 3])],
        is_unanswerable=False,
    )
    retriever = RetrievalResultRetriever(retrieval)
    provider = StructuredProviderStub(
        {
            "is_answerable": True,
            "final_answer": 500,
            "relevant_pages": [3],
            "reasoning_summary": "The fine appears on the retained page.",
            "confidence": 0.9,
        }
    )
    service = AnsweringService(retriever=retriever, provider=provider)

    result = service.answer_question(question)

    assert result.answer is None
    assert result.confidence == 0.0
    assert result.evidence_pages == []
    assert result.page_trace is not None
    assert result.page_trace.raw_retrieved_chunk_pages == [PageReference(doc_id="alpha", page_numbers=[1, 3])]
    assert result.page_trace.pass_a_pages == [PageReference(doc_id="alpha", page_numbers=[1, 3])]
    assert result.page_trace.solver_reported_pages == []
    assert result.page_trace.final_emitted_pages == []
    assert result.page_trace.validation_action == "collapsed_answer"
    assert result.page_trace.collapsed_answer is True
    assert len(provider.calls) == 1
    assert provider.calls[0]["question"] == "What is the administrative fine?"
    assert provider.calls[0]["answer_type"] == "number"
    assert provider.calls[0]["reasoning_effort"] == "medium"
    assert provider.calls[0]["evidence_pages"] == [
        {
            "doc_id": "alpha",
            "page_number": 1,
            "page_numbers": [1, 3],
            "text": "Service Agreement Table of Contents. The administrative fine is AED 500.",
        }
    ]


def test_w4b_relevant_pages_do_not_narrow_ambiguous_multi_document_page_numbers() -> None:
    question = QuestionRecord(id="q-name", question="Who is the appointed liquidator?", answer_type="name")
    retrieval = RetrievalResult(
        question_id=question.id,
        query=question.question,
        answer_type=question.answer_type,
        candidate_count=3,
        reranked_count=2,
        evidence_chunks=[
            RetrievedChunk(
                chunk_id="c1",
                doc_id="alpha",
                page_span=[3],
                chunk_type="clause",
                text="Page 3 states that the appointed liquidator is Jane Smith.",
                retrieval_score=0.93,
            ),
            RetrievedChunk(
                chunk_id="c2",
                doc_id="beta",
                page_span=[3],
                chunk_type="clause",
                text="Page 3 identifies Beta Holdings as respondent.",
                retrieval_score=0.71,
            ),
        ],
        retrieved_chunk_pages=[
            PageReference(doc_id="alpha", page_numbers=[3]),
            PageReference(doc_id="beta", page_numbers=[3]),
        ],
        is_unanswerable=False,
    )
    retriever = RetrievalResultRetriever(retrieval)
    provider = StructuredProviderStub(
        {
            "is_answerable": True,
            "final_answer": "Jane Smith",
            "relevant_pages": [3],
            "reasoning_summary": "Page 3 supports the appointment.",
            "confidence": 0.89,
        }
    )
    service = AnsweringService(retriever=retriever, provider=provider)

    result = service.answer_question(question)

    assert result.answer == "Jane Smith"
    assert result.evidence_pages == [
        PageReference(doc_id="alpha", page_numbers=[3]),
        PageReference(doc_id="beta", page_numbers=[3]),
    ]


def test_w4b_multi_document_names_baseline_uses_schema_solver_without_decomposition() -> None:
    question = QuestionRecord(
        id="q-names",
        question="Who are the parties across the related matters?",
        answer_type="names",
    )
    retrieval = RetrievalResult(
        question_id=question.id,
        query=question.question,
        answer_type=question.answer_type,
        candidate_count=4,
        reranked_count=2,
        evidence_chunks=[
            RetrievedChunk(
                chunk_id="c1",
                doc_id="alpha",
                page_span=[11],
                chunk_type="clause",
                text="In Matter A, the claimant is Alice Smith.",
                retrieval_score=0.88,
            ),
            RetrievedChunk(
                chunk_id="c2",
                doc_id="beta",
                page_span=[14],
                chunk_type="clause",
                text="In Matter B, the respondent is Bob Jones.",
                retrieval_score=0.86,
            ),
        ],
        retrieved_chunk_pages=[
            PageReference(doc_id="alpha", page_numbers=[11]),
            PageReference(doc_id="beta", page_numbers=[14]),
        ],
        is_unanswerable=False,
    )
    retriever = RetrievalResultRetriever(retrieval)
    provider = StructuredProviderStub(
        {
            "is_answerable": True,
            "final_answer": ["Bob Jones", "Alice Smith"],
            "relevant_pages": [11, 14],
            "reasoning_summary": "Each retrieved matter contributes one supported party name.",
            "confidence": 0.86,
        }
    )
    service = AnsweringService(retriever=retriever, provider=provider)

    result = service.answer_question(question)

    assert set(result.answer) == {"Alice Smith", "Bob Jones"}
    assert result.confidence == 0.86
    assert result.evidence_pages == [
        PageReference(doc_id="alpha", page_numbers=[11]),
        PageReference(doc_id="beta", page_numbers=[14]),
    ]
    assert len(provider.calls) == 1
    assert provider.calls[0]["answer_type"] == "names"
    assert provider.calls[0]["reasoning_effort"] == "high"


def test_w4b_answering_service_passes_query_metadata_to_retrieval_as_soft_guidance() -> None:
    question = QuestionRecord(
        id="q-meta",
        question="Under DIFC Employment Law, what is the penalty in Case 012/2024 and related matters?",
        answer_type="number",
    )
    retrieval = RetrievalResult(
        question_id=question.id,
        query=question.question,
        answer_type=question.answer_type,
        candidate_count=1,
        reranked_count=1,
        evidence_chunks=[
            RetrievedChunk(
                chunk_id="c1",
                doc_id="alpha",
                page_span=[4],
                chunk_type="clause",
                text="Case 012/2024 states that the penalty is AED 500.",
                retrieval_score=0.91,
            )
        ],
        retrieved_chunk_pages=[PageReference(doc_id="alpha", page_numbers=[4])],
        is_unanswerable=False,
    )
    retriever = RetrievalResultRetriever(retrieval)
    provider = StructuredProviderStub(
        {
            "is_answerable": True,
            "final_answer": 500,
            "relevant_pages": [4],
            "reasoning_summary": "The retrieved clause states the penalty directly.",
            "confidence": 0.89,
        }
    )
    service = AnsweringService(retriever=retriever, provider=provider)

    service.answer_question(question)

    assert len(provider.calls) == 1
    assert len(retriever.query_metadata) == 1
    metadata = retriever.query_metadata[0]
    assert metadata is not None
    assert metadata.likely_multi_document is True
    assert metadata.document_title_cues == ()
    assert [
        (entity.entity_type, entity.normalized_value)
        for entity in metadata.legal_entities
    ] == [
        ("case_id", "012/2024"),
        ("statute_id", "difc employment law"),
    ]
