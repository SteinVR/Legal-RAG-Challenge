from __future__ import annotations

from pathlib import Path

from src.evaluation.contracts import (
    AnswerType,
    AssistantScoreRecord,
    PageReference,
    ReferenceAnswerRecord,
    UnanswerableRetrievalPolicy,
)
from src.evaluation.scorer import (
    ScoreOptions,
    score_deterministic_answer,
    score_grounding,
    score_submission,
    score_ttft,
)
from tests.support.documents import write_pdf


def test_score_submission_calculates_expected_metrics(tmp_path: Path) -> None:
    documents_dir = tmp_path / "documents" / "pdfs"
    documents_dir.mkdir(parents=True)
    write_pdf(documents_dir / "alpha.pdf", page_count=3)

    submission = {
        "answers": [
            {
                "question_id": "q1",
                "answer": 101,
                "telemetry": {
                    "timing": {"ttft_ms": 900, "tpot_ms": 20, "total_time_ms": 1500},
                    "retrieval": {"retrieved_chunk_pages": [{"doc_id": "alpha", "page_numbers": [1, 2]}]},
                    "usage": {"input_tokens": 50, "output_tokens": 4},
                },
            },
            {
                "question_id": "q2",
                "answer": "No information in the provided documents.",
                "telemetry": {
                    "timing": {"ttft_ms": 2500, "tpot_ms": 40, "total_time_ms": 2500},
                    "retrieval": {"retrieved_chunk_pages": []},
                    "usage": {"input_tokens": 60, "output_tokens": 8},
                },
            },
        ]
    }
    references = [
        ReferenceAnswerRecord(
            question_id="q1",
            answer_type=AnswerType.NUMBER,
            answer=100,
            gold_retrieval=[PageReference(doc_id="alpha", page_numbers=[1, 2])],
        ),
        ReferenceAnswerRecord(
            question_id="q2",
            answer_type=AnswerType.FREE_TEXT,
            answer="There is no information on this question in the provided documents.",
            gold_retrieval=[],
        ),
    ]
    assistant_scores = [AssistantScoreRecord(question_id="q2", assistant_score=0.8)]

    report = score_submission(
        submission,
        references=references,
        assistant_scores=assistant_scores,
        options=ScoreOptions(
            unanswerable_retrieval_policy=UnanswerableRetrievalPolicy.ALLOW_EMPTY,
            documents_dir=str(documents_dir),
        ),
    )

    assert report.validation.valid is True
    assert report.metrics.deterministic == 1.0
    assert report.metrics.assistant == 0.8
    assert report.metrics.grounding == 1.0
    assert report.metrics.telemetry == 1.0
    assert report.metrics.ttft_multiplier == 1.025
    assert report.metrics.total_score == 0.9634999999999999


def test_score_submission_validates_raw_extra_answers_without_breaking_subset_scoring(tmp_path: Path) -> None:
    documents_dir = tmp_path / "documents" / "pdfs"
    documents_dir.mkdir(parents=True)
    write_pdf(documents_dir / "alpha.pdf", page_count=1)

    submission = {
        "answers": [
            {
                "question_id": "q1",
                "answer": "Alice",
                "telemetry": {
                    "timing": {"ttft_ms": 900, "tpot_ms": 20, "total_time_ms": 1500},
                    "retrieval": {"retrieved_chunk_pages": [{"doc_id": "alpha", "page_numbers": [1]}]},
                    "usage": {"input_tokens": 50, "output_tokens": 4},
                },
            },
            {
                "question_id": "qx",
                "answer": "Ghost",
                "telemetry": {
                    "timing": {"ttft_ms": 900, "tpot_ms": 20, "total_time_ms": 1500},
                    "retrieval": {"retrieved_chunk_pages": [{"doc_id": "alpha", "page_numbers": [1]}]},
                    "usage": {"input_tokens": 50, "output_tokens": 4},
                },
            },
        ]
    }
    references = [
        ReferenceAnswerRecord(
            question_id="q1",
            answer_type=AnswerType.NAME,
            answer="alice",
            gold_retrieval=[PageReference(doc_id="alpha", page_numbers=[1])],
        )
    ]

    report = score_submission(
        submission,
        references=references,
        options=ScoreOptions(
            unanswerable_retrieval_policy=UnanswerableRetrievalPolicy.ALLOW_EMPTY,
            documents_dir=str(documents_dir),
            validation_question_types={"q1": AnswerType.NAME, "q2": AnswerType.NAME},
        ),
    )

    assert report.validation.valid is False
    assert report.unscored_question_ids == ["qx"]
    unknown_answer = next(answer for answer in report.validation.answers if answer.question_id == "qx")
    assert {issue.code for issue in unknown_answer.issues} == {"submission.question_id.unknown"}


def test_scoring_helpers_cover_edge_cases() -> None:
    assert score_deterministic_answer(answer_type=AnswerType.NUMBER, predicted=100.9, expected=100) == 1.0
    assert score_deterministic_answer(answer_type=AnswerType.NUMBER, predicted=101.1, expected=100) == 0.0
    assert score_deterministic_answer(answer_type=AnswerType.NAME, predicted="  Alice  ", expected="alice") == 1.0
    assert score_deterministic_answer(
        answer_type=AnswerType.NAMES,
        predicted=["Alice", "Bob"],
        expected=["alice", "Charlie"],
    ) == 1 / 3
    assert score_deterministic_answer(answer_type=AnswerType.DATE, predicted="2026-03-19", expected="2026-03-19") == 1.0

    assert score_grounding(predicted_pairs=set(), gold_pairs=set()) == 1.0
    assert score_grounding(predicted_pairs={("a", 1)}, gold_pairs=set()) == 0.0
    assert score_ttft(500) == 1.05
    assert score_ttft(1500) == 1.02
    assert score_ttft(2500) == 1.0
    assert score_ttft(3000) == 1.0
    assert round(score_ttft(10_000), 2) == 0.85
