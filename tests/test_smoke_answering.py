"""Stage smoke for answering behavior."""

from __future__ import annotations

from typing import Any

from src.answering.service import AnsweringService
from src.common.schemas import QuestionRecord
from tests.support.smoke_harness import NoApiProvider


class StaticPageRetriever:
    """Static retriever used to smoke-check AnsweringService deterministically."""

    def retrieve(self, question: QuestionRecord, *, query_metadata: Any | None = None) -> list[dict[str, Any]]:
        """Return a fixed retrieval payload that supports numeric extraction."""

        del question, query_metadata
        return [
            {
                "doc_id": "synthetic_law",
                "page_number": 2,
                "text": "Under Article 8 of the law, the notice must be filed within 30 days.",
            }
        ]


def test_answering_smoke_returns_typed_answer_without_openai() -> None:
    """Smoke-check typed answering path without calling external model APIs."""

    service = AnsweringService(
        retriever=StaticPageRetriever(),
        provider=NoApiProvider(),
    )
    question = QuestionRecord(
        id="smoke-answering-q1",
        question="How many days are allowed to file the notice?",
        answer_type="number",
    )

    result = service.answer_question(question)

    assert result.answer == 30
    assert result.confidence == 1.0
    assert len(result.evidence_pages) == 1
    assert result.evidence_pages[0].doc_id == "synthetic_law"
    assert result.evidence_pages[0].page_numbers == [2]

