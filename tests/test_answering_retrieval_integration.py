from __future__ import annotations

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

    assert result.question_id == "q-free"
    assert result.answer == "The tribunal dismissed the claim and ordered payment within 14 days."
    assert result.confidence == 0.83
    assert result.evidence_pages == [PageReference(doc_id="alpha", page_numbers=[2, 3])]
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


def test_answering_service_passes_query_metadata_to_retrieval_as_soft_guidance() -> None:
    question = QuestionRecord(
        id="q-meta",
        question="Across Case No. 12/2024 and Case No. 18/2023, which DIFC Employment Law provisions apply?",
        answer_type="free_text",
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
                text="Case 12/2024 and Case 18/2023 both apply DIFC Employment Law.",
                retrieval_score=0.88,
            )
        ],
        retrieved_chunk_pages=[PageReference(doc_id="alpha", page_numbers=[4])],
        is_unanswerable=False,
    )
    retriever = RetrievalResultRetriever(retrieval)
    provider = StubProvider(
        {
            "answer": "Case 12/2024 and Case 18/2023 both apply DIFC Employment Law.",
            "confidence": 0.74,
        }
    )
    service = AnsweringService(retriever=retriever, provider=provider)

    result = service.answer_question(question)

    assert result.answer == "Case 12/2024 and Case 18/2023 both apply DIFC Employment Law."
    assert len(retriever.query_metadata) == 1
    metadata = retriever.query_metadata[0]
    assert metadata is not None
    assert getattr(metadata, "likely_multi_document") is True
    normalized_entities = {
        (
            str(getattr(entity, "entity_type")),
            str(getattr(entity, "normalized_value")),
            bool(getattr(entity, "is_strong")),
        )
        for entity in getattr(metadata, "legal_entities")
    }
    assert ("case_id", "12/2024", True) in normalized_entities
    assert ("case_id", "18/2023", True) in normalized_entities
    assert ("statute_id", "difc employment law", True) in normalized_entities
