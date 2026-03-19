from __future__ import annotations

from src.common.schemas import QuestionRecord
from src.evaluation.contracts import (
    AnswerType,
    AssistantScoreRecord,
    BenchmarkDifficulty,
    BenchmarkSourceType,
    PageReference,
    ReferenceAnswerRecord,
    UnanswerableRetrievalPolicy,
)
from src.evaluation.dev_benchmark import (
    BenchmarkQuestionMetadata,
    analyze_benchmark_consistency,
    build_benchmark_report,
    compare_benchmark_reports,
)
from src.evaluation.scorer import ScoreOptions


def test_build_benchmark_report_emits_slices_and_regressions() -> None:
    questions = [
        QuestionRecord(id="q1", question="How many days?", answer_type="number"),
        QuestionRecord(id="q2", question="Summarize the order.", answer_type="free_text"),
    ]
    references = [
        ReferenceAnswerRecord(
            question_id="q1",
            answer_type=AnswerType.NUMBER,
            answer=30,
            gold_retrieval=[PageReference(doc_id="alpha", page_numbers=[1])],
        ),
        ReferenceAnswerRecord(
            question_id="q2",
            answer_type=AnswerType.FREE_TEXT,
            answer="The application was dismissed with costs.",
            gold_retrieval=[
                PageReference(doc_id="alpha", page_numbers=[1]),
                PageReference(doc_id="beta", page_numbers=[1]),
            ],
        ),
    ]
    metadata = [
        BenchmarkQuestionMetadata(
            question_id="q1",
            difficulty=BenchmarkDifficulty.EASY,
            source_type=BenchmarkSourceType.STATUTE,
            tags=["deterministic", "single_page"],
        ),
        BenchmarkQuestionMetadata(
            question_id="q2",
            difficulty=BenchmarkDifficulty.HARD,
            source_type=BenchmarkSourceType.CASE,
            tags=["free_text", "multi_document"],
        ),
    ]
    assistant_scores = [AssistantScoreRecord(question_id="q2", assistant_score=0.8)]
    options = ScoreOptions(
        unanswerable_retrieval_policy=UnanswerableRetrievalPolicy.ALLOW_EMPTY,
        validation_question_types={"q1": AnswerType.NUMBER, "q2": AnswerType.FREE_TEXT},
    )

    baseline_submission = {
        "answers": [
            {
                "question_id": "q1",
                "answer": 30,
                "telemetry": {
                    "timing": {"ttft_ms": 900, "tpot_ms": 20, "total_time_ms": 1500},
                    "retrieval": {"retrieved_chunk_pages": [{"doc_id": "alpha", "page_numbers": [1]}]},
                    "usage": {"input_tokens": 20, "output_tokens": 4},
                },
            },
            {
                "question_id": "q2",
                "answer": "The application was dismissed with costs.",
                "telemetry": {
                    "timing": {"ttft_ms": 1200, "tpot_ms": 25, "total_time_ms": 1600},
                    "retrieval": {
                        "retrieved_chunk_pages": [
                            {"doc_id": "alpha", "page_numbers": [1]},
                            {"doc_id": "beta", "page_numbers": [1]},
                        ]
                    },
                    "usage": {"input_tokens": 30, "output_tokens": 8},
                },
            },
        ]
    }
    candidate_submission = {
        "answers": [
            {
                "question_id": "q1",
                "answer": 0,
                "telemetry": {
                    "timing": {"ttft_ms": 900, "tpot_ms": 20, "total_time_ms": 1500},
                    "retrieval": {"retrieved_chunk_pages": [{"doc_id": "alpha", "page_numbers": [1]}]},
                    "usage": {"input_tokens": 20, "output_tokens": 4},
                },
            },
            {
                "question_id": "q2",
                "answer": "The application was dismissed with costs.",
                "telemetry": {
                    "timing": {"ttft_ms": 1200, "tpot_ms": 25, "total_time_ms": 1600},
                    "retrieval": {
                        "retrieved_chunk_pages": [
                            {"doc_id": "alpha", "page_numbers": [1]},
                            {"doc_id": "beta", "page_numbers": [1]},
                        ]
                    },
                    "usage": {"input_tokens": 30, "output_tokens": 8},
                },
            },
        ]
    }

    baseline_report = build_benchmark_report(
        baseline_submission,
        benchmark_name="dev-gold",
        references=references,
        questions=questions,
        metadata=metadata,
        assistant_scores=assistant_scores,
        options=options,
    )
    candidate_report = build_benchmark_report(
        candidate_submission,
        benchmark_name="dev-gold",
        references=references,
        questions=questions,
        metadata=metadata,
        assistant_scores=assistant_scores,
        options=options,
    )

    slice_keys = {(slice_report.dimension, slice_report.value) for slice_report in baseline_report.slices}
    assert ("answer_type", "number") in slice_keys
    assert ("answer_type", "free_text") in slice_keys
    assert ("difficulty", "easy") in slice_keys
    assert ("difficulty", "hard") in slice_keys
    assert ("source_type", "statute") in slice_keys
    assert ("source_type", "case") in slice_keys
    assert ("doc_count", "1") in slice_keys
    assert ("doc_count", "2") in slice_keys
    assert ("tag", "deterministic") in slice_keys
    assert ("tag", "free_text") in slice_keys

    comparison = compare_benchmark_reports(
        baseline_report,
        candidate_report,
        baseline_label="baseline",
        candidate_label="candidate",
    )
    assert comparison.overall.delta.total_score < 0
    assert comparison.regressions[0] == "q1"

    consistency = analyze_benchmark_consistency(
        [baseline_report, candidate_report],
        instability_threshold=0.5,
    )
    unstable_ids = {record.question_id for record in consistency.unstable_questions}
    assert "q1" in unstable_ids
