"""Stage smoke for answering behavior."""

from __future__ import annotations

from typing import Any

from src.answering.service import AnsweringService
from src.answering.service_types import FreeTextAnswerSchema
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


class AmbiguousLawNumberRetriever:
    """Retriever that returns a law-number page and a year-like distractor page."""

    def retrieve(self, question: QuestionRecord, *, query_metadata: Any | None = None) -> list[dict[str, Any]]:
        """Return pages that previously caused law-number ambiguity (`2` vs `2018`)."""

        del question, query_metadata
        return [
            {
                "doc_id": "synthetic_law",
                "page_number": 1,
                "text": "COMMON REPORTING STANDARD LAW DIFC LAW NO. 2 OF 2018.",
            },
            {
                "doc_id": "synthetic_law",
                "page_number": 3,
                "text": "This Law may be cited as the Common Reporting Standard Law 2018.",
            },
        ]


class ListedClaimantRetriever:
    """Retriever that mixes caption claimant and narrative claimant distractor pages."""

    def retrieve(self, question: QuestionRecord, *, query_metadata: Any | None = None) -> list[dict[str, Any]]:
        """Return pages that should resolve to the caption-listed claimant only."""

        del question, query_metadata
        return [
            {
                "doc_id": "synthetic_case",
                "page_number": 1,
                "text": (
                    "Claim No: SCT 295/2025 THE COURT BETWEEN OLEXA Claimant/Applicant "
                    "and ODON Defendant/Respondent."
                ),
            },
            {
                "doc_id": "synthetic_case",
                "page_number": 2,
                "text": "The Parties. The Claimant is Obasi. The Defendant is Oreana.",
            },
        ]


class MultiDateIssueRetriever:
    """Retriever that includes multiple procedural dates plus a header issue date."""

    def retrieve(self, question: QuestionRecord, *, query_metadata: Any | None = None) -> list[dict[str, Any]]:
        """Return a page where the issue date appears in the header."""

        del question, query_metadata
        return [
            {
                "doc_id": "synthetic_case",
                "page_number": 1,
                "text": (
                    "ARB 034/2025 Ohtli v Onora DECEMBER 19, 2025 ARBITRATION - ORDERS. "
                    "UPON the Claimant's application dated 9 September 2025. "
                    "UPON the Defendant's application dated 25 November 2025."
                ),
            }
        ]


class DuplicatePageIssueDateRetriever:
    """Retriever with duplicate page entries where only the longer chunk has header issue date."""

    def retrieve(self, question: QuestionRecord, *, query_metadata: Any | None = None) -> list[dict[str, Any]]:
        """Return same-page chunks ordered as narrow-then-full to stress dedup selection."""

        del question, query_metadata
        return [
            {
                "doc_id": "synthetic_case",
                "page_number": 1,
                "text": "Justice Shamlan Al Sawalehi dated 12 September 2025 granting interim anti-suit relief.",
            },
            {
                "doc_id": "synthetic_case",
                "page_number": 1,
                "text": (
                    "ARB 034/2025 Ohtli v Onora DECEMBER 19, 2025 ARBITRATION - ORDERS. "
                    "UPON the Claimant's application dated 9 September 2025. "
                    "UPON the Defendant's application dated 25 November 2025."
                ),
            },
        ]


class MultiCaseGenericBooleanRetriever:
    """Retriever for multi-case boolean questions that should bypass unsupported decomposition."""

    def retrieve(self, question: QuestionRecord, *, query_metadata: Any | None = None) -> list[dict[str, Any]]:
        """Return one permissive sentence for baseline boolean extraction."""

        del question, query_metadata
        return [
            {
                "doc_id": "synthetic_case",
                "page_number": 4,
                "text": "Interim relief is permitted.",
            }
        ]


class RerankOrderedIssueDateRetriever:
    """Retriever where top-ranked page has later physical index but correct issue date."""

    def retrieve(self, question: QuestionRecord, *, query_metadata: Any | None = None) -> list[dict[str, Any]]:
        """Return pages in rerank order: correct issue page first, distractor page second."""

        del question, query_metadata
        return [
            {
                "doc_id": "synthetic_case",
                "page_number": 10,
                "text": "Date of Issue: 19 December 2025. ARBITRATION ORDER.",
            },
            {
                "doc_id": "synthetic_case",
                "page_number": 1,
                "text": "UPON the hearing dated 1 January 2020 the parties made submissions.",
            },
        ]


class NarrativeClaimantListRetriever:
    """Retriever for list-style claimant question without caption markup."""

    def retrieve(self, question: QuestionRecord, *, query_metadata: Any | None = None) -> list[dict[str, Any]]:
        """Return sentence-style role text only, without caption lines."""

        del question, query_metadata
        return [
            {
                "doc_id": "synthetic_case",
                "page_number": 2,
                "text": "The Claimant is Obasi. The Defendant is Oreana.",
            }
        ]


def test_free_text_schema_smoke_exports_char_limit() -> None:
    """Ensure structured-output schema includes the free_text character contract."""

    schema = FreeTextAnswerSchema.model_json_schema()
    final_answer_schema = schema["properties"]["final_answer"]
    assert final_answer_schema["type"] == "string"
    assert final_answer_schema["minLength"] == 1
    assert final_answer_schema["maxLength"] == 280


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


def test_answering_smoke_prefers_explicit_law_number_over_year_literal() -> None:
    """Ensure law-number questions stay answerable when nearby year literals appear."""

    service = AnsweringService(
        retriever=AmbiguousLawNumberRetriever(),
        provider=NoApiProvider(),
    )
    question = QuestionRecord(
        id="smoke-answering-law-number-q1",
        question="According to the title page, what is the official DIFC Law number?",
        answer_type="number",
    )

    result = service.answer_question(question)

    assert result.answer == 2
    assert result.confidence == 1.0
    assert result.evidence_pages
    assert result.evidence_pages[0].doc_id == "synthetic_law"


def test_answering_smoke_prefers_caption_listed_claimant_for_names_questions() -> None:
    """Ensure listed-claimant extraction ignores narrative-role distractors."""

    service = AnsweringService(
        retriever=ListedClaimantRetriever(),
        provider=NoApiProvider(),
    )
    question = QuestionRecord(
        id="smoke-answering-listed-claimant-q1",
        question="Who are listed as the claimants in the case documents for SCT 295/2025?",
        answer_type="names",
    )

    result = service.answer_question(question)

    assert isinstance(result.answer, list)
    assert [item.casefold() for item in result.answer] == ["olexa"]
    assert result.confidence == 1.0
    assert result.evidence_pages
    assert result.evidence_pages[0].doc_id == "synthetic_case"


def test_answering_smoke_issue_date_prefers_header_issue_date() -> None:
    """Ensure issue-date extraction prefers the header issue date over procedural dates."""

    service = AnsweringService(
        retriever=MultiDateIssueRetriever(),
        provider=NoApiProvider(),
    )
    question = QuestionRecord(
        id="smoke-answering-issue-date-q1",
        question="What is the date of issue of the document in case ARB 034/2025?",
        answer_type="date",
    )

    result = service.answer_question(question)

    assert result.answer == "2025-12-19"
    assert result.confidence == 1.0
    assert result.evidence_pages
    assert result.evidence_pages[0].doc_id == "synthetic_case"


def test_answering_smoke_issue_date_prefers_strongest_duplicate_page_chunk() -> None:
    """Ensure duplicate same-page entries prefer the fuller chunk for issue-date extraction."""

    service = AnsweringService(
        retriever=DuplicatePageIssueDateRetriever(),
        provider=NoApiProvider(),
    )
    question = QuestionRecord(
        id="smoke-answering-issue-date-dedupe-q1",
        question="What is the date of issue of the document in case ARB 034/2025?",
        answer_type="date",
    )

    result = service.answer_question(question)

    assert result.answer == "2025-12-19"
    assert result.confidence == 1.0
    assert result.evidence_pages
    assert result.evidence_pages[0].doc_id == "synthetic_case"


def test_answering_smoke_multicase_boolean_falls_back_without_recursive_decomposition() -> None:
    """Ensure unsupported decomposition subject falls back to baseline once without recursion."""

    service = AnsweringService(
        retriever=MultiCaseGenericBooleanRetriever(),
        provider=NoApiProvider(),
    )
    question = QuestionRecord(
        id="smoke-answering-decomposition-fallback-q1",
        question="Do CFI 057/2025 and ARB 034/2025 permit interim relief?",
        answer_type="boolean",
    )

    result = service.answer_question(question)

    assert result.answer is True
    assert result.model_name != "decomposition_w4e"
    assert result.confidence == 1.0
    assert result.evidence_pages
    assert result.evidence_pages[0].doc_id == "synthetic_case"


def test_answering_smoke_issue_date_keeps_rerank_priority_over_page_number_order() -> None:
    """Ensure issue-date selection does not reorder candidates by physical page number."""

    service = AnsweringService(
        retriever=RerankOrderedIssueDateRetriever(),
        provider=NoApiProvider(),
    )
    question = QuestionRecord(
        id="smoke-answering-issue-date-rerank-q1",
        question="What is the date of issue of the document in case ARB 034/2025?",
        answer_type="date",
    )

    result = service.answer_question(question)

    assert result.answer == "2025-12-19"
    assert result.confidence == 1.0
    assert result.evidence_pages
    assert result.evidence_pages[0].doc_id == "synthetic_case"


def test_answering_smoke_list_claimants_without_listed_still_uses_sentence_role_extraction() -> None:
    """Ensure generic 'list' wording does not force caption-only claimant extraction."""

    service = AnsweringService(
        retriever=NarrativeClaimantListRetriever(),
        provider=NoApiProvider(),
    )
    question = QuestionRecord(
        id="smoke-answering-list-claimant-q1",
        question="List the claimants in the case documents for SCT 295/2025.",
        answer_type="names",
    )

    result = service.answer_question(question)

    assert isinstance(result.answer, list)
    assert [item.casefold() for item in result.answer] == ["obasi"]
    assert result.confidence == 1.0
    assert result.evidence_pages
    assert result.evidence_pages[0].doc_id == "synthetic_case"
