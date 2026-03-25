from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.main import main
from tests.support.config import write_main_test_config
from tests.support.documents import write_pdf

pytestmark = pytest.mark.integration


def test_validate_and_score_commands_use_phase_defaults(tmp_path: Path, capsys) -> None:
    config_path, env_path = write_main_test_config(tmp_path)
    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    questions_path.parent.mkdir(parents=True, exist_ok=True)
    questions_path.write_text(
        json.dumps([{"id": "q1", "question": "Who?", "answer_type": "name"}]),
        encoding="utf-8",
    )

    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    write_pdf(documents_dir / "alpha.pdf", page_count=1)

    submission_path = tmp_path / "submission.json"
    submission_path.write_text(
        json.dumps(
            {
                "answers": [
                    {
                        "question_id": "q1",
                        "answer": "Alice",
                        "telemetry": {
                            "timing": {"ttft_ms": 450, "tpot_ms": 10, "total_time_ms": 800},
                            "retrieval": {"retrieved_chunk_pages": [{"doc_id": "alpha", "page_numbers": [1]}]},
                            "usage": {"input_tokens": 22, "output_tokens": 3},
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    reference_path = tmp_path / "reference.json"
    reference_path.write_text(
        json.dumps(
            [
                {
                    "question_id": "q1",
                    "answer_type": "name",
                    "answer": "alice",
                    "gold_retrieval": [{"doc_id": "alpha", "page_numbers": [1]}],
                }
            ]
        ),
        encoding="utf-8",
    )

    validate_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "validate-submission",
            "--submission-path",
            str(submission_path),
        ]
    )
    validate_output = json.loads(capsys.readouterr().out)

    score_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "score-submission",
            "--submission-path",
            str(submission_path),
            "--reference-path",
            str(reference_path),
        ]
    )
    score_output = json.loads(capsys.readouterr().out)

    assert validate_code == 0
    assert score_code == 0
    assert validate_output["valid"] is True
    assert score_output["metrics"]["deterministic"] == 1.0
    assert score_output["metrics"]["grounding"] == 1.0


def test_validate_submission_requires_documents_dir_for_corpus_backed_checks(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path, env_path = write_main_test_config(tmp_path)
    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    questions_path.parent.mkdir(parents=True, exist_ok=True)
    questions_path.write_text(
        json.dumps([{"id": "q1", "question": "Who?", "answer_type": "name"}]),
        encoding="utf-8",
    )

    submission_path = tmp_path / "submission.json"
    submission_path.write_text(
        json.dumps(
            {
                "answers": [
                    {
                        "question_id": "q1",
                        "answer": "Alice",
                        "telemetry": {
                            "timing": {"ttft_ms": 450, "tpot_ms": 10, "total_time_ms": 800},
                            "retrieval": {"retrieved_chunk_pages": [{"doc_id": "alpha", "page_numbers": [1]}]},
                            "usage": {"input_tokens": 22, "output_tokens": 3},
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--config",
                str(config_path),
                "--env-file",
                str(env_path),
                "validate-submission",
                "--submission-path",
                str(submission_path),
            ]
        )

    assert exc_info.value.code == 1
    assert "Documents directory does not exist" in capsys.readouterr().err


def test_score_submission_requires_documents_dir_for_corpus_backed_checks(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path, env_path = write_main_test_config(tmp_path)
    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    questions_path.parent.mkdir(parents=True, exist_ok=True)
    questions_path.write_text(
        json.dumps([{"id": "q1", "question": "Who?", "answer_type": "name"}]),
        encoding="utf-8",
    )

    submission_path = tmp_path / "submission.json"
    submission_path.write_text(
        json.dumps(
            {
                "answers": [
                    {
                        "question_id": "q1",
                        "answer": "Alice",
                        "telemetry": {
                            "timing": {"ttft_ms": 450, "tpot_ms": 10, "total_time_ms": 800},
                            "retrieval": {"retrieved_chunk_pages": [{"doc_id": "alpha", "page_numbers": [1]}]},
                            "usage": {"input_tokens": 22, "output_tokens": 3},
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    reference_path = tmp_path / "reference.json"
    reference_path.write_text(
        json.dumps(
            [
                {
                    "question_id": "q1",
                    "answer_type": "name",
                    "answer": "Alice",
                    "gold_retrieval": [{"doc_id": "alpha", "page_numbers": [1]}],
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--config",
                str(config_path),
                "--env-file",
                str(env_path),
                "score-submission",
                "--submission-path",
                str(submission_path),
                "--reference-path",
                str(reference_path),
            ]
        )

    assert exc_info.value.code == 1
    assert "Documents directory does not exist" in capsys.readouterr().err


def test_benchmark_commands_generate_summary_compare_and_consistency(tmp_path: Path) -> None:
    config_path, env_path = write_main_test_config(tmp_path)
    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    questions_path.parent.mkdir(parents=True, exist_ok=True)
    questions_path.write_text(
        json.dumps(
            [
                {"id": "q1", "question": "How many days?", "answer_type": "number"},
                {"id": "q2", "question": "Summarize the order.", "answer_type": "free_text"},
            ]
        ),
        encoding="utf-8",
    )

    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    write_pdf(documents_dir / "alpha.pdf", page_count=1)
    write_pdf(documents_dir / "beta.pdf", page_count=1)

    baseline_submission_path = tmp_path / "baseline_submission.json"
    baseline_submission_path.write_text(
        json.dumps(
            {
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
        ),
        encoding="utf-8",
    )

    candidate_submission_path = tmp_path / "candidate_submission.json"
    candidate_submission_path.write_text(
        json.dumps(
            {
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
        ),
        encoding="utf-8",
    )

    benchmark_path = tmp_path / "benchmark.json"
    benchmark_path.write_text(
        json.dumps(
            {
                "benchmark_id": "dev-gold",
                "title": "dev-gold",
                "references": [
                    {
                        "question_id": "q1",
                        "question": "How many days?",
                        "answer_type": "number",
                        "answer": 30,
                        "difficulty": "easy",
                        "source_type": "statute",
                        "tags": ["deterministic", "single_page"],
                        "gold_retrieval": [{"doc_id": "alpha", "page_numbers": [1]}],
                    },
                    {
                        "question_id": "q2",
                        "question": "Summarize the order.",
                        "answer_type": "free_text",
                        "answer": "The application was dismissed with costs.",
                        "difficulty": "hard",
                        "source_type": "case",
                        "tags": ["free_text", "multi_document"],
                        "gold_retrieval": [
                            {"doc_id": "alpha", "page_numbers": [1]},
                            {"doc_id": "beta", "page_numbers": [1]},
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    assistant_scores_path = tmp_path / "assistant_scores.json"
    assistant_scores_path.write_text(
        json.dumps([{"question_id": "q2", "assistant_score": 0.8}]),
        encoding="utf-8",
    )

    baseline_report_path = tmp_path / "baseline_report.json"
    candidate_report_path = tmp_path / "candidate_report.json"
    comparison_path = tmp_path / "comparison.json"
    consistency_path = tmp_path / "consistency.json"

    baseline_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "benchmark-summary",
            "--submission-path",
            str(baseline_submission_path),
            "--benchmark-path",
            str(benchmark_path),
            "--assistant-scores-path",
            str(assistant_scores_path),
            "--output-path",
            str(baseline_report_path),
        ]
    )
    candidate_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "benchmark-summary",
            "--submission-path",
            str(candidate_submission_path),
            "--benchmark-path",
            str(benchmark_path),
            "--assistant-scores-path",
            str(assistant_scores_path),
            "--output-path",
            str(candidate_report_path),
        ]
    )
    compare_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "compare-benchmark-runs",
            "--baseline-path",
            str(baseline_report_path),
            "--candidate-path",
            str(candidate_report_path),
            "--output-path",
            str(comparison_path),
        ]
    )
    consistency_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "analyze-benchmark-consistency",
            "--report-path",
            str(baseline_report_path),
            "--report-path",
            str(candidate_report_path),
            "--instability-threshold",
            "0.5",
            "--output-path",
            str(consistency_path),
        ]
    )

    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    consistency = json.loads(consistency_path.read_text(encoding="utf-8"))

    assert baseline_code == 0
    assert candidate_code == 0
    assert compare_code == 0
    assert consistency_code == 0
    assert comparison["overall"]["delta"]["total_score"] < 0
    unstable_ids = {record["question_id"] for record in consistency["unstable_questions"]}
    assert "q1" in unstable_ids
