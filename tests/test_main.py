from __future__ import annotations

import io
import json
from pathlib import Path
from zipfile import ZipFile

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
