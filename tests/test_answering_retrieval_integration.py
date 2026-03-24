from __future__ import annotations

import importlib
from collections.abc import Mapping
from typing import Any

from src.answering.service import AnsweringService
from src.common.schemas import QuestionRecord
from src.evaluation.contracts import PageReference
from src.retrieval.service import RetrievalResult, RetrievedChunk


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


class RetrievalResultRetriever:
    def __init__(self, result: RetrievalResult) -> None:
        self._result = result
        self.calls: list[QuestionRecord] = []

    def retrieve(self, question: QuestionRecord) -> RetrievalResult:
        self.calls.append(question)
        return self._result


def _load_page_attribution_module() -> Any:
    return importlib.import_module("src.answering.page_attribution")


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
