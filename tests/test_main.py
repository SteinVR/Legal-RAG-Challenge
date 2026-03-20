from __future__ import annotations

import io
import json
from pathlib import Path
from zipfile import ZipFile

import fitz
import pytest
import yaml

from src.common.schemas import QuestionRecord
from src.main import main


class StubClient:
    def __init__(self) -> None:
        self.closed = False

    def download_questions(self) -> list[QuestionRecord]:
        return [QuestionRecord(id="q1", question="Who?", answer_type="name")]

    def stream_documents(self, destination, *, chunk_size: int = 1_048_576) -> None:
        zip_buffer = io.BytesIO()
        with ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("alpha.pdf", b"%PDF-1.4 alpha")
        destination.write(zip_buffer.getvalue())

    def submit_submission(self, submission_path: str | Path, code_archive_path: str | Path):
        return {
            "uuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "phase": "warmup",
            "version": "1",
            "status": "queued",
        }

    def get_submission_status(self, submission_uuid: str):
        return {
            "uuid": submission_uuid,
            "status": "completed",
            "phase": "warmup",
            "review_status": "active",
        }

    def close(self) -> None:
        self.closed = True


def _write_config(tmp_path: Path) -> tuple[Path, Path]:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
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
    return config_path, env_path


def test_sync_phase_writes_phase_artifacts_and_manifest(tmp_path: Path) -> None:
    config_path, env_path = _write_config(tmp_path)
    stub_client = StubClient()

    exit_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "sync-phase",
            "--phase",
            "warmup",
        ],
        client_factory=lambda _: stub_client,
    )

    assert exit_code == 0
    assert stub_client.closed is True
    assert (tmp_path / "data" / "warmup" / "questions" / "questions.json").exists()
    assert (tmp_path / "data" / "warmup" / "documents" / "documents.zip").exists()
    manifest = json.loads(
        (tmp_path / "data" / "warmup" / "manifests" / "sync_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["phase"] == "warmup"
    assert manifest["questions_count"] == 1
    assert manifest["extracted_pdf_count"] == 1


def test_parse_corpus_writes_canonical_outputs(tmp_path: Path) -> None:
    config_path, env_path = _write_config(tmp_path)
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    _write_pdf(documents_dir / "alpha.pdf", page_count=1, page_texts=["DIFC LAW\nArticle 1\nA fine applies."])

    exit_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "parse-corpus",
        ]
    )

    assert exit_code == 0
    corpus_path = tmp_path / "data" / "warmup" / "corpus" / "corpus.jsonl"
    page_map_path = tmp_path / "data" / "warmup" / "corpus" / "page_map.json"
    manifest_path = tmp_path / "data" / "warmup" / "corpus" / "corpus_manifest.json"
    debug_path = tmp_path / "data" / "warmup" / "corpus" / "debug" / "alpha.md"
    assert corpus_path.exists()
    assert page_map_path.exists()
    assert manifest_path.exists()
    assert debug_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["document_count"] == 1
    assert manifest["failed_document_count"] == 0


def test_submit_and_status_commands_return_success(tmp_path: Path) -> None:
    config_path, env_path = _write_config(tmp_path)
    submission_path = tmp_path / "submission.json"
    submission_path.write_text('{"answers":[]}', encoding="utf-8")
    archive_path = tmp_path / "code_archive.zip"
    archive_path.write_bytes(b"PK\x03\x04")

    submit_client = StubClient()
    status_client = StubClient()

    submit_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "submit",
            "--submission-path",
            str(submission_path),
            "--code-archive-path",
            str(archive_path),
        ],
        client_factory=lambda _: submit_client,
    )
    status_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "submission-status",
            "--submission-uuid",
            "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        ],
        client_factory=lambda _: status_client,
    )

    assert submit_code == 0
    assert status_code == 0
    assert submit_client.closed is True
    assert status_client.closed is True


def test_parse_corpus_dry_run_reports_planned_paths(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config_path, env_path = _write_config(tmp_path)

    exit_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "parse-corpus",
            "--dry-run",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "command: parse-corpus" in output
    assert "dry_run: true" in output
    assert "corpus.jsonl" in output
    assert "page_map.json" in output
    assert "corpus_manifest.json" in output


def test_parse_corpus_requires_downloaded_documents(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config_path, env_path = _write_config(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--config",
                str(config_path),
                "--env-file",
                str(env_path),
                "parse-corpus",
            ]
        )

    assert exc_info.value.code == 1
    assert "Documents directory does not exist" in capsys.readouterr().err


def test_parse_corpus_writes_canonical_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.ingestion.pdf_parser.build_ocr_engine", lambda _settings: None)
    config_path, env_path = _write_config(tmp_path)
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    _write_pdf(
        documents_dir / "alpha.pdf",
        page_count=1,
        page_texts=["EMPLOYMENT LAW\nArticle 1\nThe law applies."],
    )

    exit_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "parse-corpus",
            "--force",
        ]
    )
    output = capsys.readouterr().out

    corpus_path = tmp_path / "data" / "warmup" / "corpus" / "corpus.jsonl"
    page_map_path = tmp_path / "data" / "warmup" / "corpus" / "page_map.json"
    manifest_path = tmp_path / "data" / "warmup" / "corpus" / "corpus_manifest.json"
    debug_path = tmp_path / "data" / "warmup" / "corpus" / "debug" / "alpha.md"

    assert exit_code == 0
    assert "parsed_document_count: 1" in output
    assert corpus_path.exists()
    assert page_map_path.exists()
    assert manifest_path.exists()
    assert debug_path.exists()
    corpus_rows = [json.loads(line) for line in corpus_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert corpus_rows[0]["doc_id"] == "alpha"
    assert corpus_rows[0]["page_number"] == 1


def test_validate_and_score_commands_use_phase_defaults(tmp_path: Path, capsys) -> None:
    config_path, env_path = _write_config(tmp_path)
    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    questions_path.parent.mkdir(parents=True, exist_ok=True)
    questions_path.write_text(
        json.dumps([{"id": "q1", "question": "Who?", "answer_type": "name"}]),
        encoding="utf-8",
    )

    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    _write_pdf(documents_dir / "alpha.pdf", page_count=1)

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
    config_path, env_path = _write_config(tmp_path)
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
    config_path, env_path = _write_config(tmp_path)
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
    config_path, env_path = _write_config(tmp_path)
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
    documents_dir.mkdir(parents=True, exist_ok=True)
    _write_pdf(documents_dir / "alpha.pdf", page_count=1)
    _write_pdf(documents_dir / "beta.pdf", page_count=1)

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


def _write_pdf(path: Path, *, page_count: int, page_texts: list[str] | None = None) -> None:
    document = fitz.open()
    page_texts = page_texts or []
    for page_index in range(page_count):
        page = document.new_page()
        if page_index < len(page_texts):
            page.insert_text((72, 72), page_texts[page_index])
    document.save(path)
    document.close()
