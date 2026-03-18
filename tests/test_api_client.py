from __future__ import annotations

import io
import json
from pathlib import Path
from zipfile import ZipFile

import httpx
import pytest

from src.submission.api_client import CompetitionApiClient


def test_download_questions_saves_json_and_sends_api_key(tmp_path: Path) -> None:
    target_path = tmp_path / "questions.json"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/questions"
        assert request.headers["X-API-Key"] == "secret"
        return httpx.Response(
            200,
            json=[{"id": "q1", "question": "Who?", "answer_type": "name"}],
        )

    client = CompetitionApiClient(
        api_key="secret",
        base_url="https://platform.agentic-challenge.ai/api/v1",
        transport=httpx.MockTransport(handler),
    )
    try:
        questions = client.download_questions(target_path)
    finally:
        client.close()

    saved_payload = json.loads(target_path.read_text(encoding="utf-8"))
    assert len(questions) == 1
    assert saved_payload[0]["id"] == "q1"


def test_download_documents_writes_zip_and_extracts_pdfs(tmp_path: Path) -> None:
    archive_path = tmp_path / "documents.zip"
    extract_dir = tmp_path / "documents"
    extract_dir.mkdir(parents=True)
    (extract_dir / "stale.txt").write_text("old", encoding="utf-8")

    zip_buffer = io.BytesIO()
    with ZipFile(zip_buffer, "w") as zip_file:
        zip_file.writestr("alpha.pdf", b"%PDF-1.4 alpha")
        zip_file.writestr("nested/beta.pdf", b"%PDF-1.4 beta")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/documents"
        return httpx.Response(200, content=zip_buffer.getvalue())

    client = CompetitionApiClient(
        api_key="secret",
        base_url="https://platform.agentic-challenge.ai/api/v1",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = client.download_documents(archive_path, extract_dir)
    finally:
        client.close()

    assert archive_path.exists()
    assert not (extract_dir / "stale.txt").exists()
    assert sorted(result.document_files) == ["alpha.pdf", "nested/beta.pdf"]
    assert (extract_dir / "alpha.pdf").exists()
    assert (extract_dir / "nested" / "beta.pdf").exists()


def test_download_documents_rejects_unsafe_archive_paths(tmp_path: Path) -> None:
    archive_path = tmp_path / "documents.zip"
    extract_dir = tmp_path / "documents"

    zip_buffer = io.BytesIO()
    with ZipFile(zip_buffer, "w") as zip_file:
        zip_file.writestr("../escape.txt", b"bad")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/documents"
        return httpx.Response(200, content=zip_buffer.getvalue())

    client = CompetitionApiClient(
        api_key="secret",
        base_url="https://platform.agentic-challenge.ai/api/v1",
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(ValueError, match="Unsafe archive member path"):
            client.download_documents(archive_path, extract_dir)
    finally:
        client.close()

    assert not (tmp_path / "escape.txt").exists()


def test_submit_submission_posts_expected_multipart_payload(tmp_path: Path) -> None:
    submission_path = tmp_path / "submission.json"
    submission_path.write_text('{"answers":[]}', encoding="utf-8")
    archive_path = tmp_path / "code_archive.zip"
    archive_path.write_bytes(b"PK\x03\x04")

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content
        assert request.url.path == "/api/v1/submissions"
        assert request.headers["content-type"].startswith("multipart/form-data; boundary=")
        assert b'name="file"' in body
        assert b'name="code_archive"' in body
        assert b"submission.json" in body
        assert b"code_archive.zip" in body
        return httpx.Response(
            202,
            json={
                "uuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "status": "queued",
                "phase": "warmup",
                "version": "1",
                "created_at": "2026-02-24T12:00:00Z",
                "payload_sha256": "abc123",
            },
        )

    client = CompetitionApiClient(
        api_key="secret",
        base_url="https://platform.agentic-challenge.ai/api/v1",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = client.submit_submission(submission_path, archive_path)
    finally:
        client.close()

    assert result["uuid"] == "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    assert result["phase"] == "warmup"


def test_get_submission_status_parses_metrics() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/submissions/3fa85f64-5717-4562-b3fc-2c963f66afa6/status"
        return httpx.Response(
            200,
            json={
                "uuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "phase": "final",
                "version": "final_v3",
                "status": "completed",
                "review_status": "active",
                "metrics": {
                    "deterministic": 0.825,
                    "assistant": 0.74,
                    "grounding": 0.87,
                    "telemetry": 0.95,
                    "ttft_ms": 310,
                    "ttft_multiplier": 1.0,
                    "total_score": 0.783,
                },
            },
        )

    client = CompetitionApiClient(
        api_key="secret",
        base_url="https://platform.agentic-challenge.ai/api/v1",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = client.get_submission_status("3fa85f64-5717-4562-b3fc-2c963f66afa6")
    finally:
        client.close()

    assert result["metrics"]["total_score"] == 0.783
