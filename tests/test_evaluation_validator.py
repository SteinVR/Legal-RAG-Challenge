from __future__ import annotations

from src.evaluation.contracts import AnswerType, UnanswerableRetrievalPolicy
from src.evaluation.validator import SubmissionValidator, ValidationPolicy, build_corpus_registry
from tests.support.documents import write_pdf


def test_validator_allows_empty_retrieval_for_unanswerable_policy(tmp_path: Path) -> None:
    question_types = {"q1": AnswerType.NAME}
    submission = {
        "answers": [
            {
                "question_id": "q1",
                "answer": None,
                "telemetry": {
                    "timing": {"ttft_ms": 120, "tpot_ms": 10, "total_time_ms": 120},
                    "retrieval": {"retrieved_chunk_pages": []},
                    "usage": {"input_tokens": 12, "output_tokens": 0},
                    "model_name": "baseline-v1",
                },
            }
        ]
    }

    report = SubmissionValidator(
        question_types=question_types,
        policy=ValidationPolicy(
            unanswerable_retrieval_policy=UnanswerableRetrievalPolicy.ALLOW_EMPTY,
            require_full_question_coverage=True,
            emit_ambiguity_warning=True,
        ),
    ).validate(submission)

    assert report.valid is True
    assert report.malformed_answers == 0
    assert report.warning_count == 1
    assert report.answers[0].telemetry_malformed is False
    assert report.answers[0].issues[0].code == "telemetry.retrieval.empty_allowed"


def test_validator_rejects_empty_retrieval_when_policy_requires_non_empty(tmp_path: Path) -> None:
    question_types = {"q1": AnswerType.NAME}
    submission = {
        "answers": [
            {
                "question_id": "q1",
                "answer": None,
                "telemetry": {
                    "timing": {"ttft_ms": 120, "tpot_ms": 10, "total_time_ms": 120},
                    "retrieval": {"retrieved_chunk_pages": []},
                    "usage": {"input_tokens": 12, "output_tokens": 0},
                },
            }
        ]
    }

    report = SubmissionValidator(
        question_types=question_types,
        policy=ValidationPolicy(
            unanswerable_retrieval_policy=UnanswerableRetrievalPolicy.REQUIRE_NON_EMPTY,
            require_full_question_coverage=True,
            emit_ambiguity_warning=True,
        ),
    ).validate(submission)

    assert report.valid is False
    assert report.malformed_answers == 1
    assert report.answers[0].telemetry_malformed is True
    assert {issue.code for issue in report.answers[0].issues} == {"telemetry.retrieval.empty_disallowed"}


def test_validator_checks_doc_existence_and_page_bounds(tmp_path: Path) -> None:
    documents_dir = tmp_path / "documents" / "pdfs"
    documents_dir.mkdir(parents=True)
    write_pdf(documents_dir / "alpha.pdf", page_count=2)

    submission = {
        "answers": [
            {
                "question_id": "q1",
                "answer": "Alice",
                "telemetry": {
                    "timing": {"ttft_ms": 100, "tpot_ms": 5, "total_time_ms": 200},
                    "retrieval": {
                        "retrieved_chunk_pages": [
                            {"doc_id": "missing", "page_numbers": [1]},
                            {"doc_id": "alpha", "page_numbers": [3]},
                        ]
                    },
                    "usage": {"input_tokens": 10, "output_tokens": 3},
                },
            }
        ]
    }

    report = SubmissionValidator(
        question_types={"q1": AnswerType.NAME},
        corpus_registry=build_corpus_registry(documents_dir),
        policy=ValidationPolicy(),
    ).validate(submission)

    issue_codes = {issue.code for issue in report.answers[0].issues}
    assert report.valid is False
    assert report.malformed_answers == 1
    assert "telemetry.retrieval.doc_id_unknown" in issue_codes
    assert "telemetry.retrieval.page_number_out_of_range" in issue_codes


def test_validator_rejects_question_id_with_surrounding_whitespace() -> None:
    submission = {
        "answers": [
            {
                "question_id": "q1",
                "answer": "Alice",
                "telemetry": {
                    "timing": {"ttft_ms": 100, "tpot_ms": 5, "total_time_ms": 200},
                    "retrieval": {"retrieved_chunk_pages": [{"doc_id": "alpha", "page_numbers": [1]}]},
                    "usage": {"input_tokens": 10, "output_tokens": 3},
                },
            },
            {
                "question_id": " q1 ",
                "answer": "Alice",
                "telemetry": {
                    "timing": {"ttft_ms": 100, "tpot_ms": 5, "total_time_ms": 200},
                    "retrieval": {"retrieved_chunk_pages": [{"doc_id": "alpha", "page_numbers": [1]}]},
                    "usage": {"input_tokens": 10, "output_tokens": 3},
                },
            },
        ]
    }

    report = SubmissionValidator(
        question_types={"q1": AnswerType.NAME},
        policy=ValidationPolicy(require_full_question_coverage=True, emit_ambiguity_warning=False),
    ).validate(submission)

    exact_answer = next(answer for answer in report.answers if answer.question_id == "q1")
    whitespace_answer = next(answer for answer in report.answers if answer.question_id == " q1 ")
    exact_issue_codes = {issue.code for issue in exact_answer.issues}
    issue_codes = {issue.code for issue in whitespace_answer.issues}

    assert report.valid is False
    assert "submission.question_id.duplicate" in exact_issue_codes
    assert "submission.question_id.whitespace" in issue_codes
    assert "submission.question_id.unknown" not in issue_codes
