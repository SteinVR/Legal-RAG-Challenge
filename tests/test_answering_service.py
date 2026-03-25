from __future__ import annotations

import importlib
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

import pytest

from src.common.schemas import QuestionRecord

CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER = "There is no information on this question in the provided documents."


class StubRetriever:
    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self._pages = list(pages)
        self.calls: list[QuestionRecord] = []
        self.query_metadata: list[Any] = []

    def retrieve(self, question: QuestionRecord, *, query_metadata: Any | None = None) -> list[dict[str, Any]]:
        self.calls.append(question)
        self.query_metadata.append(query_metadata)
        return list(self._pages)


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


def _load_answering_service():
    module = importlib.import_module("src.answering.service")
    return module.AnsweringService


def _question(*, text: str, answer_type: str, question_id: str = "q1") -> QuestionRecord:
    return QuestionRecord(id=question_id, question=text, answer_type=answer_type)


def _page(*, doc_id: str = "alpha", page_number: int, text: str) -> dict[str, Any]:
    return {
        "doc_id": doc_id,
        "page_number": page_number,
        "text": text,
    }


def _result_field(result: Any, field: str) -> Any:
    if isinstance(result, Mapping):
        return result[field]
    return getattr(result, field)


def _collect_ref_pages(normalized: dict[str, set[int]], ref: Any) -> None:
    if isinstance(ref, Mapping):
        doc_id = str(ref["doc_id"])
        if "page_numbers" in ref:
            normalized[doc_id].update(int(page) for page in ref["page_numbers"])
            return

        normalized[doc_id].add(int(ref["page_number"]))
        return

    doc_id = str(ref.doc_id)
    if hasattr(ref, "page_numbers"):
        normalized[doc_id].update(int(page) for page in ref.page_numbers)
        return

    normalized[doc_id].add(int(ref.page_number))


def _grouped_refs(result: Any) -> list[tuple[str, list[int]]]:
    refs = _result_field(result, "evidence_pages")
    normalized: dict[str, set[int]] = defaultdict(set)
    for ref in refs:
        _collect_ref_pages(normalized, ref)

    return sorted((doc_id, sorted(page_numbers)) for doc_id, page_numbers in normalized.items())


def _build_service(*, pages: list[dict[str, Any]], provider_response: Mapping[str, Any] | None = None):
    service_cls = _load_answering_service()
    retriever = StubRetriever(pages)
    provider = StubProvider(provider_response or {"answer": "unused", "confidence": 0.0})
    return service_cls(retriever=retriever, provider=provider), retriever, provider


def test_answering_service_extracts_number_without_provider_and_keeps_supporting_pages_only() -> None:
    service, retriever, provider = _build_service(
        pages=[
            _page(page_number=1, text="Article 2 describes the obligation."),
            _page(page_number=2, text="The administrative fine is AED 1,250.50 payable within five days."),
        ]
    )

    result = service.answer_question(_question(text="What is the administrative fine?", answer_type="number"))

    assert _result_field(result, "question_id") == "q1"
    assert _result_field(result, "answer") == pytest.approx(1250.5)
    assert _result_field(result, "confidence") == pytest.approx(1.0)
    assert _grouped_refs(result) == [("alpha", [2])]
    assert [question.id for question in retriever.calls] == ["q1"]
    assert provider.calls == []


def test_answering_service_extracts_boolean_from_textual_evidence_without_provider() -> None:
    service, _, provider = _build_service(
        pages=[
            _page(
                page_number=4,
                text=(
                    "The claimant may assign the lease only with the landlord's consent. "
                    "Assignment without consent is not permitted."
                ),
            )
        ]
    )

    result = service.answer_question(
        _question(text="Is assignment without consent permitted?", answer_type="boolean")
    )

    assert _result_field(result, "answer") is False
    assert _result_field(result, "confidence") == pytest.approx(1.0)
    assert _grouped_refs(result) == [("alpha", [4])]
    assert provider.calls == []


def test_answering_service_does_not_treat_notice_as_negative_boolean_cue() -> None:
    service, _, provider = _build_service(
        pages=[_page(page_number=26, text="The notice period is 30 days.")]
    )

    result = service.answer_question(_question(text="Is notice prohibited?", answer_type="boolean"))

    assert _result_field(result, "answer") is None
    assert _result_field(result, "confidence") == pytest.approx(0.0)
    assert _grouped_refs(result) == []
    assert provider.calls == []


def test_answering_service_does_not_treat_cancellation_as_positive_boolean_cue() -> None:
    service, _, provider = _build_service(
        pages=[_page(page_number=27, text="The cancellation procedure is described in Schedule A.")]
    )

    result = service.answer_question(_question(text="Is cancellation permitted?", answer_type="boolean"))

    assert _result_field(result, "answer") is None
    assert _result_field(result, "confidence") == pytest.approx(0.0)
    assert _grouped_refs(result) == []
    assert provider.calls == []


def test_answering_service_normalizes_name_answer_without_provider() -> None:
    service, _, provider = _build_service(
        pages=[_page(page_number=3, text="The appointed liquidator is   Jane   Smith   .")]
    )

    result = service.answer_question(_question(text="Who is the appointed liquidator?", answer_type="name"))

    assert _result_field(result, "answer") == "Jane Smith"
    assert _result_field(result, "confidence") == pytest.approx(1.0)
    assert _grouped_refs(result) == [("alpha", [3])]
    assert provider.calls == []


def test_answering_service_extracts_uppercase_entity_name_without_provider() -> None:
    service, _, provider = _build_service(
        pages=[_page(page_number=28, text="The respondent is ACME LTD.")]
    )

    result = service.answer_question(_question(text="Who is the respondent?", answer_type="name"))

    assert _result_field(result, "answer") == "ACME LTD"
    assert _result_field(result, "confidence") == pytest.approx(1.0)
    assert _grouped_refs(result) == [("alpha", [28])]
    assert provider.calls == []


def test_answering_service_extracts_single_token_acronym_name_without_provider() -> None:
    service, _, provider = _build_service(
        pages=[_page(page_number=30, text="The respondent is ADNOC.")]
    )

    result = service.answer_question(_question(text="Who is the respondent?", answer_type="name"))

    assert _result_field(result, "answer") == "ADNOC"
    assert _result_field(result, "confidence") == pytest.approx(1.0)
    assert _grouped_refs(result) == [("alpha", [30])]
    assert provider.calls == []


def test_answering_service_extracts_single_token_titlecase_entity_without_provider() -> None:
    service, _, provider = _build_service(
        pages=[_page(page_number=31, text="The respondent is Beta.")]
    )

    result = service.answer_question(_question(text="Who is the respondent?", answer_type="name"))

    assert _result_field(result, "answer") == "Beta"
    assert _result_field(result, "confidence") == pytest.approx(1.0)
    assert _grouped_refs(result) == [("alpha", [31])]
    assert provider.calls == []


def test_answering_service_normalizes_names_answer_deduplicates_and_preserves_first_seen_order() -> None:
    service, _, provider = _build_service(
        pages=[
            _page(
                page_number=5,
                text="The panel members are Alice Smith,  Bob Jones, and Alice Smith.",
            )
        ]
    )

    result = service.answer_question(_question(text="Who are the panel members?", answer_type="names"))

    assert _result_field(result, "answer") == ["Alice Smith", "Bob Jones"]
    assert _result_field(result, "confidence") == pytest.approx(1.0)
    assert _grouped_refs(result) == [("alpha", [5])]
    assert provider.calls == []


def test_answering_service_extracts_uppercase_entity_names_list_without_provider() -> None:
    service, _, provider = _build_service(
        pages=[_page(page_number=29, text="The parties are ACME LTD., BETA LLC, and ACME LTD.")]
    )

    result = service.answer_question(_question(text="Who are the parties?", answer_type="names"))

    assert _result_field(result, "answer") == ["ACME LTD", "BETA LLC"]
    assert _result_field(result, "confidence") == pytest.approx(1.0)
    assert _grouped_refs(result) == [("alpha", [29])]
    assert provider.calls == []


def test_answering_service_normalizes_date_to_iso8601_without_provider() -> None:
    service, _, provider = _build_service(
        pages=[_page(page_number=6, text="Date of issue: 5 March 2026.")]
    )

    result = service.answer_question(_question(text="What is the date of issue?", answer_type="date"))

    assert _result_field(result, "answer") == "2026-03-05"
    assert _result_field(result, "confidence") == pytest.approx(1.0)
    assert _grouped_refs(result) == [("alpha", [6])]
    assert provider.calls == []


def test_answering_service_normalizes_iso_date_without_provider() -> None:
    service, _, provider = _build_service(
        pages=[_page(page_number=16, text="Date of issue: 2026-03-05.")]
    )

    result = service.answer_question(_question(text="What is the date of issue?", answer_type="date"))

    assert _result_field(result, "answer") == "2026-03-05"
    assert _result_field(result, "confidence") == pytest.approx(1.0)
    assert _grouped_refs(result) == [("alpha", [16])]
    assert provider.calls == []


@pytest.mark.parametrize(
    ("evidence_text", "page_number"),
    [
        ("Date of issue: March 5, 2026.", 33),
        ("Date of issue: March 5 2026.", 34),
    ],
)
def test_answering_service_normalizes_month_first_date_without_provider(
    evidence_text: str,
    page_number: int,
) -> None:
    service, _, provider = _build_service(
        pages=[_page(page_number=page_number, text=evidence_text)]
    )

    result = service.answer_question(_question(text="What is the date of issue?", answer_type="date"))

    assert _result_field(result, "answer") == "2026-03-05"
    assert _result_field(result, "confidence") == pytest.approx(1.0)
    assert _grouped_refs(result) == [("alpha", [page_number])]
    assert provider.calls == []


def test_answering_service_returns_null_for_conflicting_deterministic_evidence() -> None:
    service, _, provider = _build_service(
        pages=[
            _page(page_number=7, text="The response deadline is 10 days from service."),
            _page(page_number=8, text="The response deadline is 15 days from service."),
        ]
    )

    result = service.answer_question(_question(text="How many days are allowed for a response?", answer_type="number"))

    assert _result_field(result, "answer") is None
    assert _result_field(result, "confidence") == pytest.approx(0.0)
    assert _grouped_refs(result) == []
    assert provider.calls == []


def test_answering_service_prefers_amount_over_deadline_when_question_asks_for_fine() -> None:
    service, _, provider = _build_service(
        pages=[_page(page_number=11, text="The fine is 500, payable within 10 days.")]
    )

    result = service.answer_question(_question(text="What is the fine?", answer_type="number"))

    assert _result_field(result, "answer") == pytest.approx(500)
    assert _result_field(result, "confidence") == pytest.approx(1.0)
    assert _grouped_refs(result) == [("alpha", [11])]
    assert provider.calls == []


def test_answering_service_prefers_duration_over_amount_when_question_asks_for_days() -> None:
    service, _, provider = _build_service(
        pages=[_page(page_number=20, text="The fine is 500, payable within 10 days.")]
    )

    result = service.answer_question(_question(text="How many days are allowed for payment?", answer_type="number"))

    assert _result_field(result, "answer") == pytest.approx(10)
    assert _result_field(result, "confidence") == pytest.approx(1.0)
    assert _grouped_refs(result) == [("alpha", [20])]
    assert provider.calls == []


def test_answering_service_extracts_written_number_duration_without_provider() -> None:
    service, _, provider = _build_service(
        pages=[_page(page_number=22, text="Costs must be paid within five days of the order.")]
    )

    result = service.answer_question(_question(text="How many days are allowed for payment?", answer_type="number"))

    assert _result_field(result, "answer") == pytest.approx(5)
    assert _result_field(result, "confidence") == pytest.approx(1.0)
    assert _grouped_refs(result) == [("alpha", [22])]
    assert provider.calls == []


def test_answering_service_returns_null_for_empty_deterministic_retrieval_without_provider() -> None:
    service, retriever, provider = _build_service(pages=[])

    result = service.answer_question(_question(text="Who signed the agreement?", answer_type="name"))

    assert _result_field(result, "answer") is None
    assert _result_field(result, "confidence") == pytest.approx(0.0)
    assert _grouped_refs(result) == []
    assert [question.id for question in retriever.calls] == ["q1"]
    assert provider.calls == []


def test_answering_service_uses_provider_for_free_text_with_evidence_and_280_char_budget() -> None:
    service, retriever, provider = _build_service(
        pages=[
            _page(page_number=2, text="The tribunal dismissed the claim and ordered the claimant to pay costs."),
            _page(page_number=3, text="Costs must be paid within 14 days of the order."),
        ],
        provider_response={
            "answer": "The tribunal dismissed the claim and ordered the claimant to pay costs within 14 days.",
            "confidence": 0.82,
        },
    )

    result = service.answer_question(_question(text="Summarize the order.", answer_type="free_text"))

    assert _result_field(result, "answer") == (
        "The tribunal dismissed the claim and ordered the claimant to pay costs within 14 days."
    )
    assert _result_field(result, "confidence") == pytest.approx(0.82)
    assert _grouped_refs(result) == [("alpha", [2, 3])]
    assert [question.id for question in retriever.calls] == ["q1"]
    assert provider.calls == [
        {
            "question": "Summarize the order.",
            "evidence_pages": [
                {
                    **_page(
                        page_number=2,
                        text="The tribunal dismissed the claim and ordered the claimant to pay costs.",
                    ),
                    "page_numbers": [2],
                },
                {
                    **_page(page_number=3, text="Costs must be paid within 14 days of the order."),
                    "page_numbers": [3],
                },
            ],
            "max_chars": 280,
        }
    ]


def test_answering_service_returns_canonical_unanswerable_free_text_without_provider_call() -> None:
    service, retriever, provider = _build_service(pages=[])

    result = service.answer_question(_question(text="Summarize the tribunal's reasoning.", answer_type="free_text"))

    assert _result_field(result, "answer") == CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER
    assert _result_field(result, "confidence") == pytest.approx(0.0)
    assert _grouped_refs(result) == []
    assert [question.id for question in retriever.calls] == ["q1"]
    assert provider.calls == []


def test_answering_service_rejects_free_text_provider_output_longer_than_280_chars() -> None:
    service, _, _ = _build_service(
        pages=[_page(page_number=9, text="The order contains enough detail for a grounded summary.")],
        provider_response={
            "answer": "A" * 281,
            "confidence": 0.75,
        },
    )

    with pytest.raises(ValueError, match="280"):
        service.answer_question(_question(text="Summarize the order.", answer_type="free_text"))


def test_answering_service_rejects_free_text_that_introduces_date_not_present_in_evidence() -> None:
    service, _, _ = _build_service(
        pages=[_page(page_number=10, text="The agreement terminates on 5 March 2026.")],
        provider_response={
            "answer": "The agreement terminates on 6 March 2026.",
            "confidence": 0.71,
        },
    )

    result = service.answer_question(_question(text="Summarize the termination date.", answer_type="free_text"))

    assert _result_field(result, "answer") == CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER
    assert _grouped_refs(result) == []
    assert getattr(result, "page_trace").collapsed_answer is True


@pytest.mark.parametrize(
    "answer_text",
    [
        "The agreement terminates on March 5, 2026.",
        "The agreement terminates on March 5 2026.",
    ],
)
def test_answering_service_accepts_month_first_free_text_date_grounding(answer_text: str) -> None:
    service, _, _ = _build_service(
        pages=[_page(page_number=35, text="The agreement terminates on March 5, 2026.")],
        provider_response={
            "answer": answer_text,
            "confidence": 0.64,
        },
    )

    result = service.answer_question(_question(text="Summarize the termination date.", answer_type="free_text"))

    assert _result_field(result, "answer") == answer_text
    assert _result_field(result, "confidence") == pytest.approx(0.64)
    assert _grouped_refs(result) == [("alpha", [35])]


def test_answering_service_accepts_written_number_evidence_for_digit_summary() -> None:
    service, _, _ = _build_service(
        pages=[_page(page_number=17, text="Costs must be paid within five days of the order.")],
        provider_response={
            "answer": "Costs must be paid within 5 days of the order.",
            "confidence": 0.66,
        },
    )

    result = service.answer_question(_question(text="Summarize the order.", answer_type="free_text"))

    assert _result_field(result, "answer") == "Costs must be paid within 5 days of the order."
    assert _result_field(result, "confidence") == pytest.approx(0.66)
    assert _grouped_refs(result) == [("alpha", [17])]


def test_answering_service_rejects_free_text_that_introduces_number_not_present_in_evidence() -> None:
    service, _, _ = _build_service(
        pages=[_page(page_number=12, text="The claim was dismissed with costs reserved.")],
        provider_response={
            "answer": "The claim was dismissed and costs were 5000.",
            "confidence": 0.44,
        },
    )

    result = service.answer_question(_question(text="Summarize the order.", answer_type="free_text"))

    assert _result_field(result, "answer") == CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER
    assert _grouped_refs(result) == []
    assert getattr(result, "page_trace").collapsed_answer is True


def test_answering_service_treats_names_answers_as_order_insensitive_across_pages() -> None:
    service, _, provider = _build_service(
        pages=[
            _page(page_number=18, text="The panel members are Alice Smith and Bob Jones."),
            _page(page_number=19, text="The panel members are Bob Jones and Alice Smith."),
        ]
    )

    result = service.answer_question(_question(text="Who are the panel members?", answer_type="names"))

    assert _result_field(result, "answer") == ["Alice Smith", "Bob Jones"]
    assert _result_field(result, "confidence") == pytest.approx(1.0)
    assert _grouped_refs(result) == [("alpha", [18, 19])]
    assert provider.calls == []


def test_answering_service_rejects_free_text_that_introduces_name_not_present_in_evidence() -> None:
    service, _, _ = _build_service(
        pages=[_page(page_number=13, text="The appointed liquidator is Jane Smith.")],
        provider_response={
            "answer": "Jane Smith and John Doe were appointed.",
            "confidence": 0.58,
        },
    )

    result = service.answer_question(_question(text="Summarize the appointment.", answer_type="free_text"))

    assert _result_field(result, "answer") == CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER
    assert _grouped_refs(result) == []
    assert getattr(result, "page_trace").collapsed_answer is True


def test_answering_service_rejects_free_text_that_introduces_unsupported_single_token_name() -> None:
    service, _, _ = _build_service(
        pages=[_page(page_number=32, text="The respondent is ADNOC.")],
        provider_response={
            "answer": "The respondent is Beta.",
            "confidence": 0.55,
        },
    )

    result = service.answer_question(_question(text="Summarize the respondent.", answer_type="free_text"))

    assert _result_field(result, "answer") == CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER
    assert _grouped_refs(result) == []
    assert getattr(result, "page_trace").collapsed_answer is True


def test_answering_service_does_not_treat_no_later_than_as_negative_boolean_cue() -> None:
    service, _, provider = _build_service(
        pages=[_page(page_number=36, text="Payment must be made no later than 10 days from the invoice.")]
    )

    result = service.answer_question(_question(text="Is payment prohibited?", answer_type="boolean"))

    assert _result_field(result, "answer") is None
    assert _result_field(result, "confidence") == pytest.approx(0.0)
    assert _grouped_refs(result) == []
    assert provider.calls == []


def test_answering_service_rejects_free_text_that_introduces_outcome_not_present_in_evidence() -> None:
    service, _, _ = _build_service(
        pages=[_page(page_number=14, text="The tribunal dismissed the claim.")],
        provider_response={
            "answer": "The tribunal granted the claim.",
            "confidence": 0.51,
        },
    )

    result = service.answer_question(_question(text="Summarize the outcome.", answer_type="free_text"))

    assert _result_field(result, "answer") == CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER
    assert _grouped_refs(result) == []
    assert getattr(result, "page_trace").collapsed_answer is True


def test_answering_service_rejects_free_text_that_flips_outcome_polarity() -> None:
    service, _, _ = _build_service(
        pages=[_page(page_number=23, text="The tribunal dismissed the claim.")],
        provider_response={
            "answer": "The tribunal did not dismiss the claim.",
            "confidence": 0.37,
        },
    )

    result = service.answer_question(_question(text="Summarize the outcome.", answer_type="free_text"))

    assert _result_field(result, "answer") == CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER
    assert _grouped_refs(result) == []
    assert getattr(result, "page_trace").collapsed_answer is True


def test_answering_service_rejects_free_text_that_flips_contract_validity() -> None:
    service, _, _ = _build_service(
        pages=[_page(page_number=24, text="The contract was void.")],
        provider_response={
            "answer": "The contract was valid.",
            "confidence": 0.41,
        },
    )

    result = service.answer_question(_question(text="Summarize the rationale.", answer_type="free_text"))

    assert _result_field(result, "answer") == CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER
    assert _grouped_refs(result) == []
    assert getattr(result, "page_trace").collapsed_answer is True


def test_answering_service_rejects_free_text_that_introduces_unsupported_rationale_clause() -> None:
    service, _, _ = _build_service(
        pages=[_page(page_number=21, text="The tribunal dismissed the claim.")],
        provider_response={
            "answer": "The tribunal dismissed the claim because the contract was void.",
            "confidence": 0.43,
        },
    )

    result = service.answer_question(_question(text="Summarize the outcome.", answer_type="free_text"))

    assert _result_field(result, "answer") == CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER
    assert _grouped_refs(result) == []
    assert getattr(result, "page_trace").collapsed_answer is True


def test_answering_service_rejects_invalid_iso_date_evidence_for_deterministic_answer() -> None:
    service, _, provider = _build_service(
        pages=[_page(page_number=25, text="Date of issue: 2026-13-05.")]
    )

    result = service.answer_question(_question(text="What is the date of issue?", answer_type="date"))

    assert _result_field(result, "answer") is None
    assert _result_field(result, "confidence") == pytest.approx(0.0)
    assert _grouped_refs(result) == []
    assert provider.calls == []


@pytest.mark.parametrize("confidence", [float("nan"), float("inf"), -0.01, 1.01])
def test_answering_service_rejects_invalid_provider_confidence(confidence: float) -> None:
    service, _, _ = _build_service(
        pages=[_page(page_number=15, text="The tribunal dismissed the claim.")],
        provider_response={
            "answer": "The tribunal dismissed the claim.",
            "confidence": confidence,
        },
    )

    with pytest.raises(ValueError, match="confidence|0.0|1.0|finite"):
        service.answer_question(_question(text="Summarize the outcome.", answer_type="free_text"))


def test_answering_service_rejects_unsupported_answer_type() -> None:
    service, _, _ = _build_service(pages=[_page(page_number=1, text="Any text.")])

    with pytest.raises(ValueError, match="Unsupported answer_type"):
        service.answer_question(_question(text="Classify the dispute.", answer_type="currency"))
