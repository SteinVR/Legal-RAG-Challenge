"""Thin httpx-based client for the competition API."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO
from zipfile import ZipFile

import httpx

from src.common.config import AppConfig
from src.common.schemas import QuestionRecord


@dataclass(frozen=True)
class DocumentsDownloadResult:
    archive_path: Path
    extract_dir: Path
    document_files: list[str]


class CompetitionApiClient:
    """Minimal client for downloading phase assets and handling submissions."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float = 120.0,
        user_agent: str = "agentic-rag-challenge/0.1.0",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            headers={
                "X-API-Key": api_key,
                "User-Agent": user_agent,
                "Accept": "application/json, application/zip",
            },
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=True,
            transport=transport,
        )

    @classmethod
    def from_config(
        cls,
        config: AppConfig,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> "CompetitionApiClient":
        return cls(
            api_key=config.resolve_api_key(),
            base_url=config.api.base_url,
            timeout_seconds=config.api.timeout_seconds,
            user_agent=config.api.user_agent,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CompetitionApiClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def download_questions(self, target_path: str | Path | None = None) -> list[QuestionRecord]:
        response = self._client.get("questions")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Expected /questions to return a JSON list.")
        questions = [QuestionRecord.model_validate(item) for item in payload]
        if target_path is not None:
            self._write_json(Path(target_path), [question.model_dump(mode="json") for question in questions])
        return questions

    def stream_documents(self, destination: BinaryIO, *, chunk_size: int = 1_048_576) -> None:
        with self._client.stream("GET", "documents") as response:
            response.raise_for_status()
            for chunk in response.iter_bytes(chunk_size=chunk_size):
                if chunk:
                    destination.write(chunk)

    def download_documents(self, zip_path: str | Path, extract_dir: str | Path) -> DocumentsDownloadResult:
        archive_path = Path(zip_path)
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with archive_path.open("wb") as archive_handle:
            self.stream_documents(archive_handle)

        documents_dir = Path(extract_dir)
        self._extract_archive(archive_path, documents_dir)

        return DocumentsDownloadResult(
            archive_path=archive_path,
            extract_dir=documents_dir,
            document_files=sorted(str(path.relative_to(documents_dir)) for path in documents_dir.rglob("*.pdf")),
        )

    def submit_submission(self, submission_path: str | Path, code_archive_path: str | Path) -> dict[str, Any]:
        submission = Path(submission_path)
        code_archive = Path(code_archive_path)

        with submission.open("rb") as submission_handle, code_archive.open("rb") as archive_handle:
            response = self._client.post(
                "submissions",
                files={
                    "file": (submission.name, submission_handle, "application/json"),
                    "code_archive": (code_archive.name, archive_handle, "application/zip"),
                },
            )

        response.raise_for_status()
        return response.json()

    def get_submission_status(self, submission_uuid: str) -> dict[str, Any]:
        response = self._client.get(f"submissions/{submission_uuid}/status")
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _write_json(path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _extract_archive(archive_path: Path, extract_dir: Path) -> None:
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=True)

        with ZipFile(archive_path) as archive:
            target_root = extract_dir.resolve()
            for member in archive.infolist():
                destination = (extract_dir / member.filename).resolve()
                try:
                    destination.relative_to(target_root)
                except ValueError as exc:
                    raise ValueError(f"Unsafe archive member path: {member.filename}") from exc
                archive.extract(member, path=extract_dir)
