from __future__ import annotations

import json
from pathlib import Path

from src.common.schemas import QuestionRecord
from src.evaluation.contracts import AnswerType, ReferenceAnswerRecord
from src.evaluation.dev_benchmark import (
    BenchmarkQuestionMetadata,
    analyze_benchmark_consistency,
    build_benchmark_report,
    compare_benchmark_reports,
)
from src.evaluation.scorer import ScoreOptions
from src.main import main
from tests.support.documents import write_pdf


def _questions_payload() -> list[dict[str, object]]:
    return [
        {"id": "q1", "question": "Who?", "answer_type": "name"},
        {"id": "q2", "question": "Allowed?", "answer_type": "boolean"},
    ]


def _references_payload() -> list[dict[str, object]]:
    return [
        {
            "question_id": "q1",
            "question": "Who?",
            "answer_type": "name",
            "answer": "Alice",
            "gold_retrieval": [{"doc_id": "alpha", "page_numbers": [1]}],
        },
        {
            "question_id": "q2",
            "question": "Allowed?",
            "answer_type": "boolean",
            "answer": True,
            "gold_retrieval": [{"doc_id": "alpha", "page_numbers": [1]}],
        },
    ]


def _metadata_payload() -> list[dict[str, object]]:
    return [
        {
            "question_id": "q1",
            "source_type": "case",
            "difficulty": "easy",
            "tags": ["entity"],
        },
        {
            "question_id": "q2",
            "source_type": "statute",
            "difficulty": "medium",
            "tags": ["policy"],
        },
    ]


def _submission_payload(*, q1_answer: str = "Alice", q2_answer: bool = True) -> dict[str, object]:
    return {
        "answers": [
            {
                "question_id": "q1",
                "answer": q1_answer,
                "telemetry": {
                    "timing": {"ttft_ms": 450, "tpot_ms": 10, "total_time_ms": 800},
                    "retrieval": {"retrieved_chunk_pages": [{"doc_id": "alpha", "page_numbers": [1]}]},
                    "usage": {"input_tokens": 22, "output_tokens": 3},
                },
            },
            {
                "question_id": "q2",
                "answer": q2_answer,
                "telemetry": {
                    "timing": {"ttft_ms": 500, "tpot_ms": 10, "total_time_ms": 850},
                    "retrieval": {"retrieved_chunk_pages": [{"doc_id": "alpha", "page_numbers": [1]}]},
                    "usage": {"input_tokens": 24, "output_tokens": 2},
                },
            },
        ]
    }


def _question_models() -> list[QuestionRecord]:
    return [QuestionRecord.model_validate(item) for item in _questions_payload()]


def _reference_models() -> list[ReferenceAnswerRecord]:
    return [ReferenceAnswerRecord.model_validate(item) for item in _references_payload()]


def test_build_benchmark_report_generates_metadata_slices() -> None:
    report = build_benchmark_report(
        _submission_payload(),
        benchmark_name="dev-gold",
        references=_reference_models(),
        questions=_question_models(),
        metadata=[BenchmarkQuestionMetadata.model_validate(item) for item in _metadata_payload()],
        options=ScoreOptions(
            validation_question_types={"q1": AnswerType.NAME, "q2": AnswerType.BOOLEAN},
        ),
    )

    slice_ids = {slice_report.slice_id for slice_report in report.slices}
    assert report.benchmark_id == "dev-gold"
    assert report.reference_count == 2
    assert "answer_type:name" in slice_ids
    assert "answer_type:boolean" in slice_ids
    assert "source_type:case" in slice_ids
    assert "source_type:statute" in slice_ids
    assert "difficulty:easy" in slice_ids
    assert "difficulty:medium" in slice_ids
    assert "doc_count:single" in slice_ids
    assert "tag:entity" in slice_ids
    assert "tag:policy" in slice_ids


def test_compare_and_consistency_highlight_regressions() -> None:
    metadata = [BenchmarkQuestionMetadata.model_validate(item) for item in _metadata_payload()]
    options = ScoreOptions(
        validation_question_types={"q1": AnswerType.NAME, "q2": AnswerType.BOOLEAN}
    )

    baseline = build_benchmark_report(
        _submission_payload(),
        benchmark_name="dev-gold",
        references=_reference_models(),
        questions=_question_models(),
        metadata=metadata,
        options=options,
    )
    candidate = build_benchmark_report(
        _submission_payload(q1_answer="Bob"),
        benchmark_name="dev-gold",
        references=_reference_models(),
        questions=_question_models(),
        metadata=metadata,
        options=options,
    )

    comparison = compare_benchmark_reports(baseline, candidate)
    consistency = analyze_benchmark_consistency([baseline, candidate], instability_threshold=0.5)

    assert comparison.overall.delta.total_score < 0
    assert comparison.missing_in_baseline == []
    assert comparison.missing_in_candidate == []
    assert consistency.report_count == 2
    assert [item.question_id for item in consistency.unstable_questions] == ["q1"]


def test_main_benchmark_commands_round_trip(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        json.dumps(
            {
                "version": "v001",
                "api": {
                    "base_url": "https://platform.agentic-challenge.ai/api/v1",
                    "api_key_env": "COMPETITION_API_KEY",
                },
                "storage": {"root_dir": str(tmp_path / "data")},
            }
        ),
        encoding="utf-8",
    )
    env_path = tmp_path / ".env"
    env_path.write_text("COMPETITION_API_KEY=test-key\n", encoding="utf-8")

    questions_path = tmp_path / "questions.json"
    questions_path.write_text(json.dumps(_questions_payload()), encoding="utf-8")
    references_path = tmp_path / "references.json"
    references_path.write_text(json.dumps(_references_payload()), encoding="utf-8")
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps({"metadata": _metadata_payload()}), encoding="utf-8")

    documents_dir = tmp_path / "pdfs"
    documents_dir.mkdir()
    write_pdf(documents_dir / "alpha.pdf", page_count=1, fill_prefix="alpha page ")

    baseline_submission_path = tmp_path / "baseline_submission.json"
    baseline_submission_path.write_text(json.dumps(_submission_payload()), encoding="utf-8")
    candidate_submission_path = tmp_path / "candidate_submission.json"
    candidate_submission_path.write_text(
        json.dumps(_submission_payload(q2_answer=False)),
        encoding="utf-8",
    )

    baseline_report_path = tmp_path / "baseline_report.json"
    candidate_report_path = tmp_path / "candidate_report.json"

    baseline_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "benchmark-summary",
            "--submission-path",
            str(baseline_submission_path),
            "--reference-path",
            str(references_path),
            "--metadata-path",
            str(metadata_path),
            "--benchmark-name",
            "dev-gold",
            "--questions-path",
            str(questions_path),
            "--documents-dir",
            str(documents_dir),
            "--output-path",
            str(baseline_report_path),
        ]
    )
    baseline_output = json.loads(capsys.readouterr().out)

    candidate_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "benchmark-summary",
            "--submission-path",
            str(candidate_submission_path),
            "--reference-path",
            str(references_path),
            "--metadata-path",
            str(metadata_path),
            "--benchmark-name",
            "dev-gold",
            "--questions-path",
            str(questions_path),
            "--documents-dir",
            str(documents_dir),
            "--output-path",
            str(candidate_report_path),
        ]
    )
    candidate_output = json.loads(capsys.readouterr().out)

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
        ]
    )
    compare_output = json.loads(capsys.readouterr().out)

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
        ]
    )
    consistency_output = json.loads(capsys.readouterr().out)

    assert baseline_code == 0
    assert candidate_code == 0
    assert compare_code == 0
    assert consistency_code == 0
    assert baseline_output["benchmark_id"] == "dev-gold"
    assert candidate_output["benchmark_id"] == "dev-gold"
    assert compare_output["overall"]["delta"]["total_score"] < 0
    assert consistency_output["unstable_questions"][0]["question_id"] == "q2"
