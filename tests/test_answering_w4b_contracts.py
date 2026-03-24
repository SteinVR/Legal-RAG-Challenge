from __future__ import annotations

import importlib
from collections.abc import Mapping
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from src.answering.service import AnsweringService, CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER
from src.common.schemas import QuestionRecord
from src.evaluation.contracts import PageReference


class ListRetriever:
    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self._pages = list(pages)
        self.calls: list[QuestionRecord] = []
        self.query_metadata: list[Any] = []

    def retrieve(self, question: QuestionRecord, *, query_metadata: Any | None = None) -> list[dict[str, Any]]:
        self.calls.append(question)
        self.query_metadata.append(query_metadata)
        return list(self._pages)


class StructuredProviderStub:
    def __init__(self, response: Mapping[str, Any]) -> None:
        self._response = dict(response)
        self.calls: list[dict[str, Any]] = []

    def generate(self, **_: Any) -> dict[str, Any]:
        raise AssertionError(
            "TASK-W4B requires schema-bound structured solving for every answer type; "
            "the free-text `generate(...)` path must not be used here."
        )

    def generate_structured(
        self,
        *,
        question: str,
        answer_type: str,
        evidence_pages: list[dict[str, Any]],
        answer_schema: type[BaseModel],
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


def _question(*, text: str, answer_type: str, question_id: str = "q1") -> QuestionRecord:
    return QuestionRecord(id=question_id, question=text, answer_type=answer_type)


def _page(*, doc_id: str = "alpha", page_number: int, text: str) -> dict[str, Any]:
    return {
        "doc_id": doc_id,
        "page_number": page_number,
        "text": text,
    }


def _build_service(*, pages: list[dict[str, Any]], response: Mapping[str, Any]) -> tuple[AnsweringService, ListRetriever, StructuredProviderStub]:
    retriever = ListRetriever(pages)
    provider = StructuredProviderStub(response)
    return AnsweringService(retriever=retriever, provider=provider), retriever, provider


def _load_schema_registry() -> Mapping[str, type[BaseModel]]:
    module = importlib.import_module("src.answering.service")
    registry = getattr(module, "ANSWER_SCHEMA_REGISTRY", None)
    if registry is None:
        pytest.fail("TASK-W4B missing `ANSWER_SCHEMA_REGISTRY` in `src.answering.service`.")
    if not isinstance(registry, Mapping):
        pytest.fail("`ANSWER_SCHEMA_REGISTRY` must be a mapping of answer type to Pydantic schema.")
    return registry


def _coerce_metadata_field(metadata: Any, field: str) -> Any:
    if isinstance(metadata, Mapping):
        return metadata[field]
    return getattr(metadata, field)


def _coerce_entity_field(entity: Any, field: str) -> Any:
    if isinstance(entity, Mapping):
        return entity[field]
    return getattr(entity, field)


def test_w4b_schema_registry_covers_every_answer_type_and_unanswerable_contract() -> None:
    registry = _load_schema_registry()
    expected_types = {
        "boolean": True,
        "number": 1250.5,
        "name": "Jane Smith",
        "names": ["Alice Smith", "Bob Jones"],
        "date": "2026-03-05",
        "free_text": "Payment must be made within 10 days.",
    }

    assert set(expected_types) <= set(registry)

    for answer_type, sample_answer in expected_types.items():
        schema = registry[answer_type]
        assert issubclass(schema, BaseModel)
        assert {"is_answerable", "final_answer", "relevant_pages", "reasoning_summary"} <= set(schema.model_fields)

        answerable = schema.model_validate(
            {
                "is_answerable": True,
                "final_answer": sample_answer,
                "relevant_pages": [2],
                "reasoning_summary": "Retrieved evidence directly supports the answer.",
            }
        )
        assert answerable.final_answer == sample_answer
        assert answerable.relevant_pages == [2]

        if answer_type == "free_text":
            unanswerable = schema.model_validate(
                {
                    "is_answerable": False,
                    "final_answer": CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER,
                    "relevant_pages": [],
                    "reasoning_summary": "Retrieved evidence does not answer the question.",
                }
            )
            assert unanswerable.final_answer == CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER
            with pytest.raises(ValidationError):
                schema.model_validate(
                    {
                        "is_answerable": False,
                        "final_answer": None,
                        "relevant_pages": [],
                        "reasoning_summary": "Retrieved evidence does not answer the question.",
                    }
                )
            continue

        unanswerable = schema.model_validate(
            {
                "is_answerable": False,
                "final_answer": None,
                "relevant_pages": [],
                "reasoning_summary": "Retrieved evidence does not answer the question.",
            }
        )
        assert unanswerable.final_answer is None


@pytest.mark.parametrize(
    ("answer_type", "question_text", "pages", "response", "expected_answer", "expected_refs", "expected_effort"),
    [
        (
            "boolean",
            "Is assignment without consent permitted?",
            [
                _page(
                    page_number=4,
                    text="Assignment without consent is not permitted under the lease.",
                )
            ],
            {
                "is_answerable": True,
                "final_answer": False,
                "relevant_pages": [4],
                "reasoning_summary": "The clause expressly prohibits assignment without consent.",
                "confidence": 0.92,
            },
            False,
            [PageReference(doc_id="alpha", page_numbers=[4])],
            "high",
        ),
        (
            "number",
            "What is the administrative fine?",
            [
                _page(page_number=1, text="Case No. 12 of 2024"),
                _page(page_number=2, text="The administrative fine is AED 1,250.50 payable within five days."),
            ],
            {
                "is_answerable": True,
                "final_answer": 1250.5,
                "relevant_pages": [2],
                "reasoning_summary": "The fine amount is stated directly on page 2.",
                "confidence": 0.87,
            },
            1250.5,
            [PageReference(doc_id="alpha", page_numbers=[2])],
            "medium",
        ),
        (
            "name",
            "Who is the appointed liquidator?",
            [_page(page_number=3, text="The appointed liquidator is Jane Smith.")],
            {
                "is_answerable": True,
                "final_answer": "Jane Smith",
                "relevant_pages": [3],
                "reasoning_summary": "The appointment sentence gives the liquidator by name.",
                "confidence": 0.9,
            },
            "Jane Smith",
            [PageReference(doc_id="alpha", page_numbers=[3])],
            "high",
        ),
        (
            "date",
            "What is the date of issue?",
            [_page(page_number=6, text="Date of issue: 5 March 2026.")],
            {
                "is_answerable": True,
                "final_answer": "2026-03-05",
                "relevant_pages": [6],
                "reasoning_summary": "The date appears verbatim in the issue block.",
                "confidence": 0.84,
            },
            "2026-03-05",
            [PageReference(doc_id="alpha", page_numbers=[6])],
            "medium",
        ),
    ],
)
def test_w4b_answering_service_dispatches_schema_bound_typed_solving(
    answer_type: str,
    question_text: str,
    pages: list[dict[str, Any]],
    response: Mapping[str, Any],
    expected_answer: Any,
    expected_refs: list[PageReference],
    expected_effort: str,
) -> None:
    service, retriever, provider = _build_service(pages=pages, response=response)

    result = service.answer_question(_question(text=question_text, answer_type=answer_type))

    assert result.answer == expected_answer
    assert result.confidence == pytest.approx(response["confidence"])
    assert result.evidence_pages == expected_refs
    assert [question.id for question in retriever.calls] == ["q1"]
    assert len(provider.calls) == 1
    assert provider.calls[0]["question"] == question_text
    assert provider.calls[0]["answer_type"] == answer_type
    assert provider.calls[0]["evidence_pages"] == [
        {
            **page,
            "page_numbers": [page["page_number"]],
        }
        for page in pages
    ]
    assert provider.calls[0]["reasoning_effort"] == expected_effort
    assert {"is_answerable", "final_answer", "relevant_pages", "reasoning_summary"} <= set(
        provider.calls[0]["answer_schema"].model_fields
    )


def test_w4b_free_text_uses_structured_schema_and_preserves_canonical_unanswerable_sentence() -> None:
    pages = [_page(page_number=8, text="The order addresses costs only and does not explain the tribunal's reasoning.")]
    response = {
        "is_answerable": False,
        "final_answer": CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER,
        "relevant_pages": [],
        "reasoning_summary": "Retrieved evidence contains no reasoning section.",
        "confidence": 0.18,
    }
    service, _, provider = _build_service(pages=pages, response=response)

    result = service.answer_question(
        _question(text="Summarize the tribunal's reasoning.", answer_type="free_text")
    )

    assert result.answer == CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER
    assert result.evidence_pages == []
    assert len(provider.calls) == 1
    assert provider.calls[0]["answer_type"] == "free_text"
    assert provider.calls[0]["reasoning_effort"] == "medium"


def test_w4b_boolean_guardrail_abstains_when_structured_answer_flips_explicit_negation() -> None:
    service, _, _ = _build_service(
        pages=[
            _page(
                page_number=9,
                text="Assignment without consent is not permitted under this lease.",
            )
        ],
        response={
            "is_answerable": True,
            "final_answer": True,
            "relevant_pages": [9],
            "reasoning_summary": "The clause supposedly allows assignment.",
            "confidence": 0.78,
        },
    )

    result = service.answer_question(
        _question(text="Is assignment without consent permitted?", answer_type="boolean")
    )

    assert result.answer is None
    assert result.confidence == pytest.approx(0.0)
    assert result.evidence_pages == []


def test_w4b_number_guardrail_rejects_title_page_year_as_spurious_literal() -> None:
    service, _, _ = _build_service(
        pages=[
            _page(page_number=1, text="Case No. 12 of 2024"),
            _page(page_number=7, text="The administrative fine is AED 1,250.50 payable within five days."),
        ],
        response={
            "is_answerable": True,
            "final_answer": 2024,
            "relevant_pages": [1],
            "reasoning_summary": "Selected the only number seen on the title page.",
            "confidence": 0.61,
        },
    )

    result = service.answer_question(_question(text="What is the administrative fine?", answer_type="number"))

    assert result.answer is None
    assert result.confidence == pytest.approx(0.0)
    assert result.evidence_pages == []


def test_w4b_query_metadata_exposes_legal_prefilters_and_multi_document_signal() -> None:
    module = importlib.import_module("src.answering.service")
    extractor = getattr(module, "extract_query_metadata", None)
    if not callable(extractor):
        pytest.fail("TASK-W4B missing `extract_query_metadata(...)` in `src.answering.service`.")

    metadata = extractor(
        "Across Case No. 12/2024 and Case No. 18/2023, which DIFC Employment Law provisions govern "
        "the Share Purchase Agreement dispute?"
    )

    legal_entities = _coerce_metadata_field(metadata, "legal_entities")
    document_title_cues = _coerce_metadata_field(metadata, "document_title_cues")
    likely_multi_document = _coerce_metadata_field(metadata, "likely_multi_document")

    normalized_entities = {
        (
            str(_coerce_entity_field(entity, "entity_type")),
            str(_coerce_entity_field(entity, "normalized_value")),
            bool(_coerce_entity_field(entity, "is_strong")),
        )
        for entity in legal_entities
    }

    assert ("case_id", "12/2024", True) in normalized_entities
    assert ("case_id", "18/2023", True) in normalized_entities
    assert ("statute_id", "difc employment law", True) in normalized_entities
    assert "Share Purchase Agreement" in list(document_title_cues)
    assert likely_multi_document is True
