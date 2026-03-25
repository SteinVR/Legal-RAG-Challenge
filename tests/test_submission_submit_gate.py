from __future__ import annotations

from pathlib import Path

import pytest

from src.evaluation.contracts import UnanswerableRetrievalPolicy
from tests.support.documents import write_pdf, write_questions
from tests.support.imports import load_module
from tests.support.submission import validate_submission_bundle


def test_submit_gate_rejects_code_archives_larger_than_25_mb(tmp_path: Path) -> None:
    questions_path = tmp_path / "questions.json"
    documents_dir = tmp_path / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)
    write_questions(
        questions_path,
        [{"id": "q1", "question": "How many days?", "answer_type": "number"}],
    )
    write_pdf(documents_dir / "alpha.pdf", page_texts=["Payment must be made within 10 days."])

    oversized_archive = tmp_path / "code_archive.zip"
    with oversized_archive.open("wb") as handle:
        handle.truncate((25 * 1024 * 1024) + 1)

    valid_submission_payload = {
        "architecture_summary": "Minimal baseline pipeline with local validation.",
        "answers": [
            {
                "question_id": "q1",
                "answer": 10,
                "telemetry": {
                    "timing": {"ttft_ms": 900, "tpot_ms": 0, "total_time_ms": 900},
                    "retrieval": {"retrieved_chunk_pages": [{"doc_id": "alpha", "page_numbers": [1]}]},
                    "usage": {"input_tokens": 20, "output_tokens": 1},
                    "model_name": "deterministic-extractor",
                },
            }
        ],
    }

    with pytest.raises(ValueError, match="25 MB|25MB|archive size"):
        validate_submission_bundle(
            submission_payload=valid_submission_payload,
            questions_path=questions_path,
            documents_dir=documents_dir,
            code_archive_path=oversized_archive,
        )


def test_submit_gate_honors_configured_unanswerable_retrieval_policy(tmp_path: Path) -> None:
    submit_gate_module = load_module("src.submission.submit_gate", feature="W3D submit gate")
    questions_path = tmp_path / "questions.json"
    documents_dir = tmp_path / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)
    write_questions(
        questions_path,
        [{"id": "q1", "question": "How many days?", "answer_type": "number"}],
    )
    write_pdf(documents_dir / "alpha.pdf", page_texts=["Payment must be made within 10 days."])

    archive_path = tmp_path / "code_archive.zip"
    archive_path.write_bytes(b"PK\x03\x04")
    submission_payload = {
        "architecture_summary": "Minimal baseline pipeline with local validation.",
        "answers": [
            {
                "question_id": "q1",
                "answer": None,
                "telemetry": {
                    "timing": {"ttft_ms": 100, "tpot_ms": 0, "total_time_ms": 100},
                    "retrieval": {"retrieved_chunk_pages": []},
                    "usage": {"input_tokens": 1, "output_tokens": 0},
                    "model_name": "deterministic-extractor",
                },
            }
        ],
    }

    gate = submit_gate_module.SubmitGate(
        unanswerable_retrieval_policy=UnanswerableRetrievalPolicy.REQUIRE_NON_EMPTY
    )
    with pytest.raises(ValueError, match="retrieved_chunk_pages must be non-empty"):
        gate.validate(
            submission_payload=submission_payload,
            questions_path=questions_path,
            documents_dir=documents_dir,
            code_archive_path=archive_path,
        )
