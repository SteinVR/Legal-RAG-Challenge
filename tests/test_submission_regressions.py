from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from typing import Any

from src.answering.service import AnswerResult, CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER
from src.common.config import AppConfig
from src.common.schemas import QuestionRecord
from src.evaluation.contracts import AnswerType
from src.main import _run_build_submission
from src.submission.pipeline import BuildSubmissionService


def test_run_build_submission_forwards_env_file_to_service(monkeypatch: Any, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    class FakeBuildSubmissionService:
        def __init__(self, config: AppConfig, **kwargs: Any) -> None:
            captured["config"] = config
            captured["kwargs"] = kwargs

        def build_submission(self, *, questions_path: str, documents_dir: str, output_dir: str) -> Any:
            captured["paths"] = {
                "questions_path": questions_path,
                "documents_dir": documents_dir,
                "output_dir": output_dir,
            }
            return type(
                "FakeResult",
                (),
                {
                    "command": "build-submission",
                    "phase": "warmup",
                    "answer_count": 0,
                    "reused_corpus": False,
                    "reused_index": False,
                    "output_dir": Path(output_dir),
                    "submission_path": Path(output_dir) / "submission.json",
                    "code_archive_path": Path(output_dir) / "code_archive.zip",
                    "trace_manifest_path": Path(output_dir) / "trace_manifest.json",
                },
            )()

    monkeypatch.setattr("src.main.BuildSubmissionService", FakeBuildSubmissionService)
    monkeypatch.setattr("src.main._resolve_provider_api_key", lambda env_file: f"token:{env_file.name}")

    config = AppConfig.model_validate({"phase": "warmup", "storage": {"root_dir": str(tmp_path / "data")}})
    args = Namespace(
        env_file=str(tmp_path / "custom.env"),
        questions_path="questions.json",
        documents_dir="documents",
        output_dir="out",
    )

    _run_build_submission(args, config)

    assert captured["kwargs"]["env_file"] == tmp_path / "custom.env"
    assert captured["kwargs"]["provider_api_key"] == "token:custom.env"


def test_build_submission_reuses_custom_env_file_for_corpus_rebuild(monkeypatch: Any, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    class FakeCorpusParseService:
        def __init__(self, config: AppConfig, *, env_file: Path | None = None) -> None:
            captured["env_file"] = env_file

        def parse_corpus(self, *, dry_run: bool, overwrite: bool) -> None:
            captured["dry_run"] = dry_run
            captured["overwrite"] = overwrite

    monkeypatch.setattr("src.submission.pipeline.CorpusParseService", FakeCorpusParseService)

    config = AppConfig.model_validate({"phase": "warmup", "storage": {"root_dir": str(tmp_path / "data")}})
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    env_file = tmp_path / "custom.env"
    service = BuildSubmissionService(config, env_file=env_file)

    reused = service._ensure_corpus(config, documents_dir)

    assert reused is False
    assert captured["env_file"] == env_file
    assert captured["dry_run"] is False
    assert captured["overwrite"] is True


def test_build_submission_question_fallback_preserves_typed_no_answer() -> None:
    class FakeAnsweringService:
        def answer_question(self, question: QuestionRecord) -> AnswerResult:
            raise ValueError("Provider structured payload must be valid JSON.")

    config = AppConfig.model_validate({"phase": "warmup"})
    service = BuildSubmissionService(config)
    question = QuestionRecord(id="q-number", question="How many days?", answer_type=AnswerType.NUMBER.value)

    result = service._answer_question(question=question, answering_service=FakeAnsweringService())

    assert result.answer is None
    assert result.confidence == 0.0
    assert result.evidence_pages == []


def test_build_submission_question_fallback_preserves_free_text_unanswerable() -> None:
    class FakeAnsweringService:
        def answer_question(self, question: QuestionRecord) -> AnswerResult:
            raise TypeError("Provider response must be a JSON object.")

    config = AppConfig.model_validate({"phase": "warmup"})
    service = BuildSubmissionService(config)
    question = QuestionRecord(id="q-free", question="Explain the rule.", answer_type=AnswerType.FREE_TEXT.value)

    result = service._answer_question(question=question, answering_service=FakeAnsweringService())

    assert result.answer == CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER
    assert result.confidence == 0.0
    assert result.evidence_pages == []
