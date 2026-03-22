from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import fitz
import httpx
import pytest
import yaml

from src.answering.service import AnswerResult
from src.common.schemas import QuestionRecord
from src.evaluation.contracts import (
    PageReference,
    UnanswerableRetrievalPolicy,
    load_question_records,
    load_submission_payload,
    question_types_from_questions,
)
from src.evaluation.validator import SubmissionValidator, ValidationPolicy, build_corpus_registry
from src.main import build_parser, main
from src.retrieval.service import RetrievalResult, RetrievedChunk
from src.submission.packager import SubmissionPackager, _is_excluded


class StubDenseEmbedder:
    def encode(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for index, text in enumerate(texts, start=1):
            token_count = max(len(text.split()), 1)
            vectors.append([float(token_count), float(len(text)), float(index)])
        return vectors


def _write_config(
    tmp_path: Path,
    *,
    unanswerable_retrieval_policy: str | None = None,
    include_provider_token: bool = True,
) -> tuple[Path, Path]:
    config_path = tmp_path / "config.yaml"
    config_payload: dict[str, Any] = {
        "version": "v001",
        "phase": "warmup",
        "api": {
            "base_url": "https://platform.agentic-challenge.ai/api/v1",
            "api_key_env": "COMPETITION_API_KEY",
        },
        "storage": {"root_dir": str(tmp_path / "data")},
    }
    if unanswerable_retrieval_policy is not None:
        config_payload["evaluation"] = {
            "unanswerable_retrieval_policy": unanswerable_retrieval_policy,
        }
    config_path.write_text(
        yaml.safe_dump(config_payload),
        encoding="utf-8",
    )
    env_path = tmp_path / ".env"
    env_lines = ["COMPETITION_API_KEY=test-key"]
    if include_provider_token:
        env_lines.append("CODEX_OAUTH_TOKEN=test-token")
    env_path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
    return config_path, env_path


def _write_questions(path: Path, questions: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(questions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_pdf(path: Path, *, page_texts: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    for page_text in page_texts:
        page = document.new_page()
        page.insert_text((72, 72), page_text)
    document.save(path)
    document.close()


def _subparsers(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices
    raise AssertionError("Expected the CLI parser to expose subcommands.")


def _build_submission_parser() -> tuple[str, argparse.ArgumentParser]:
    choices = _subparsers(build_parser())
    for command_name in ("build-submission", "run-pipeline"):
        parser = choices.get(command_name)
        if parser is not None:
            return command_name, parser
    pytest.fail(
        "W3D orchestration CLI missing: expected one of `build-submission` or `run-pipeline` in `src.main`."
    )


def _load_module(import_path: str, *, feature: str) -> Any:
    try:
        return importlib.import_module(import_path)
    except ModuleNotFoundError as exc:
        pytest.fail(f"{feature} missing: expected `{import_path}`. {exc}")


def _build_answer_telemetry(
    *,
    retrieval_result: RetrievalResult,
    answer_result: AnswerResult,
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    total_time_ms: float,
    ttft_ms: float | None = None,
    tpot_ms: float = 0.0,
) -> dict[str, Any]:
    module = _load_module("src.submission.telemetry_packer", feature="W3D telemetry packer")

    if hasattr(module, "build_answer_telemetry"):
        return module.build_answer_telemetry(
            retrieval_result=retrieval_result,
            answer_result=answer_result,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_time_ms=total_time_ms,
            ttft_ms=ttft_ms,
            tpot_ms=tpot_ms,
        )

    if hasattr(module, "pack_answer_telemetry"):
        return module.pack_answer_telemetry(
            retrieval_result=retrieval_result,
            answer_result=answer_result,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_time_ms=total_time_ms,
            ttft_ms=ttft_ms,
            tpot_ms=tpot_ms,
        )

    if hasattr(module, "TelemetryPacker"):
        packer = module.TelemetryPacker()
        for method_name in ("build_answer_telemetry", "pack_answer", "pack_answer_telemetry"):
            if hasattr(packer, method_name):
                return getattr(packer, method_name)(
                    retrieval_result=retrieval_result,
                    answer_result=answer_result,
                    model_name=model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_time_ms=total_time_ms,
                    ttft_ms=ttft_ms,
                    tpot_ms=tpot_ms,
                )

    pytest.fail(
        "W3D telemetry packer contract missing: expected `build_answer_telemetry`, "
        "`pack_answer_telemetry`, or `TelemetryPacker` in `src.submission.telemetry_packer`."
    )


def _validate_submission_bundle(
    *,
    submission_payload: dict[str, Any],
    questions_path: Path,
    documents_dir: Path,
    code_archive_path: Path,
) -> Any:
    module = _load_module("src.submission.submit_gate", feature="W3D submit gate")

    if hasattr(module, "validate_submission_bundle"):
        return module.validate_submission_bundle(
            submission_payload=submission_payload,
            questions_path=questions_path,
            documents_dir=documents_dir,
            code_archive_path=code_archive_path,
        )

    if hasattr(module, "SubmitGate"):
        gate = module.SubmitGate()
        if hasattr(gate, "validate"):
            return gate.validate(
                submission_payload=submission_payload,
                questions_path=questions_path,
                documents_dir=documents_dir,
                code_archive_path=code_archive_path,
            )

    pytest.fail(
        "W3D submit gate contract missing: expected `validate_submission_bundle(...)` or "
        "`SubmitGate.validate(...)` in `src.submission.submit_gate`."
    )


def _validate_payload_against_local_rules(*, questions_path: Path, documents_dir: Path, submission_path: Path) -> Any:
    validator = SubmissionValidator(
        question_types=question_types_from_questions(load_question_records(questions_path)),
        corpus_registry=build_corpus_registry(documents_dir),
        policy=ValidationPolicy(
            unanswerable_retrieval_policy=UnanswerableRetrievalPolicy.ALLOW_EMPTY,
            require_full_question_coverage=True,
            emit_ambiguity_warning=True,
        ),
    )
    return validator.validate(load_submission_payload(submission_path))


def _run_build_submission(
    *,
    config_path: Path,
    env_path: Path,
    questions_path: Path,
    documents_dir: Path,
    output_dir: Path,
    extra_args: list[str] | None = None,
) -> int:
    command_name, _parser = _build_submission_parser()
    argv = [
        "--config",
        str(config_path),
        "--env-file",
        str(env_path),
        command_name,
        "--questions-path",
        str(questions_path),
        "--documents-dir",
        str(documents_dir),
        "--output-dir",
        str(output_dir),
    ]
    if extra_args:
        argv.extend(extra_args)
    return main(argv)


def _simple_qwen_rerank(
    self: Any,
    question: QuestionRecord,
    candidates: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    del self, question
    reranked = [
        {
            **dict(candidate),
            "rerank_score": float(candidate.get("retrieval_score", 0.0)),
        }
        for candidate in candidates
    ]
    reranked.sort(
        key=lambda candidate: (
            -float(candidate["rerank_score"]),
            -float(candidate.get("retrieval_score", 0.0)),
            str(candidate.get("chunk_id") or ""),
        )
    )
    return reranked[: max(int(top_k), 0)]


def _patch_pipeline_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    provider_class: type[Any] | None = None,
    inject_provider_env: bool = True,
) -> None:
    monkeypatch.setattr("src.ingestion.service.build_ocr_engine", lambda _settings: None)
    monkeypatch.setattr("src.indexing.service.build_dense_embedder", lambda _settings: StubDenseEmbedder())
    monkeypatch.setattr("src.retrieval.reranker.QwenReranker.rerank", _simple_qwen_rerank)
    if inject_provider_env:
        monkeypatch.setenv("CODEX_OAUTH_TOKEN", "test-token")

    if provider_class is None:
        return

    monkeypatch.setattr("src.providers.codex_provider.CodexFreeTextProvider", provider_class)
    monkeypatch.setattr("src.providers.CodexFreeTextProvider", provider_class, raising=False)
    monkeypatch.setattr("src.main.CodexFreeTextProvider", provider_class, raising=False)


def test_build_submission_cli_exposes_runtime_path_arguments() -> None:
    command_name, parser = _build_submission_parser()

    assert command_name in {"build-submission", "run-pipeline"}
    destinations = {action.dest for action in parser._actions}
    assert {"questions_path", "documents_dir", "output_dir"} <= destinations


def test_telemetry_packer_prefers_supporting_pages_and_uses_total_time_for_non_streaming_ttft() -> None:
    retrieval_result = RetrievalResult(
        question_id="q-free",
        query="Summarize the order.",
        answer_type="free_text",
        candidate_count=3,
        reranked_count=2,
        evidence_chunks=[
            RetrievedChunk(
                chunk_id="c1",
                doc_id="alpha",
                page_span=[2, 3],
                chunk_type="clause",
                text="The tribunal dismissed the claim and ordered payment within 14 days.",
                retrieval_score=0.91,
            )
        ],
        retrieved_chunk_pages=[PageReference(doc_id="alpha", page_numbers=[2, 3])],
        is_unanswerable=False,
    )
    answer_result = AnswerResult(
        question_id="q-free",
        answer="The tribunal dismissed the claim.",
        confidence=0.82,
        evidence_pages=[PageReference(doc_id="alpha", page_numbers=[3])],
    )

    telemetry = _build_answer_telemetry(
        retrieval_result=retrieval_result,
        answer_result=answer_result,
        model_name="gpt-5-mini",
        input_tokens=144,
        output_tokens=17,
        total_time_ms=1_250,
        ttft_ms=None,
        tpot_ms=0,
    )

    assert telemetry["timing"] == {
        "ttft_ms": pytest.approx(1_250),
        "tpot_ms": pytest.approx(0),
        "total_time_ms": pytest.approx(1_250),
    }
    assert telemetry["retrieval"] == {
        "retrieved_chunk_pages": [{"doc_id": "alpha", "page_numbers": [3]}]
    }
    assert telemetry["usage"] == {"input_tokens": 144, "output_tokens": 17}
    assert telemetry["model_name"] == "gpt-5-mini"


def test_submit_gate_rejects_code_archives_larger_than_25_mb(tmp_path: Path) -> None:
    questions_path = tmp_path / "questions.json"
    documents_dir = tmp_path / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)
    _write_questions(
        questions_path,
        [{"id": "q1", "question": "How many days?", "answer_type": "number"}],
    )
    _write_pdf(documents_dir / "alpha.pdf", page_texts=["Payment must be made within 10 days."])

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
        _validate_submission_bundle(
            submission_payload=valid_submission_payload,
            questions_path=questions_path,
            documents_dir=documents_dir,
            code_archive_path=oversized_archive,
        )


def test_build_submission_runs_real_w3abc_flow_and_writes_locally_valid_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_pipeline_dependencies(monkeypatch)
    config_path, env_path = _write_config(tmp_path)

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    _write_questions(
        questions_path,
        [{"id": "q1", "question": "Within how many days must payment be made?", "answer_type": "number"}],
    )
    _write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["Section 4 Notice. Payment must be made within 10 days after invoice."],
    )

    exit_code = _run_build_submission(
        config_path=config_path,
        env_path=env_path,
        questions_path=questions_path,
        documents_dir=documents_dir,
        output_dir=output_dir,
    )

    submission_path = output_dir / "submission.json"
    archive_path = output_dir / "code_archive.zip"

    assert exit_code == 0
    assert submission_path.exists()
    assert archive_path.exists()
    assert archive_path.stat().st_size <= 25 * 1024 * 1024

    payload = load_submission_payload(submission_path)
    assert payload["answers"][0]["question_id"] == "q1"
    assert payload["answers"][0]["answer"] == pytest.approx(10.0)
    assert payload["answers"][0]["telemetry"]["retrieval"]["retrieved_chunk_pages"] == [
        {"doc_id": "alpha", "page_numbers": [1]}
    ]

    report = _validate_payload_against_local_rules(
        questions_path=questions_path,
        documents_dir=documents_dir,
        submission_path=submission_path,
    )
    assert report.valid is True


def test_build_submission_reuses_persisted_w3a_artifacts_on_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_pipeline_dependencies(monkeypatch)
    config_path, env_path = _write_config(tmp_path)

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    first_output_dir = tmp_path / "artifacts-run-1"
    second_output_dir = tmp_path / "artifacts-run-2"

    _write_questions(
        questions_path,
        [{"id": "q1", "question": "Within how many days must payment be made?", "answer_type": "number"}],
    )
    _write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["Section 4 Notice. Payment must be made within 10 days after invoice."],
    )

    first_exit_code = _run_build_submission(
        config_path=config_path,
        env_path=env_path,
        questions_path=questions_path,
        documents_dir=documents_dir,
        output_dir=first_output_dir,
    )
    first_payload = load_submission_payload(first_output_dir / "submission.json")

    monkeypatch.setattr(
        "src.ingestion.service.CorpusParseService.parse_corpus",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("corpus rebuild should not run on restart")),
    )
    monkeypatch.setattr(
        "src.indexing.service.HybridIndexService.build_indices",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("index rebuild should not run on restart")),
    )

    second_exit_code = _run_build_submission(
        config_path=config_path,
        env_path=env_path,
        questions_path=questions_path,
        documents_dir=documents_dir,
        output_dir=second_output_dir,
    )
    second_payload = load_submission_payload(second_output_dir / "submission.json")

    assert first_exit_code == 0
    assert second_exit_code == 0
    assert second_payload["architecture_summary"] == first_payload["architecture_summary"]
    assert len(second_payload["answers"]) == 1
    assert len(first_payload["answers"]) == 1

    first_answer = first_payload["answers"][0]
    second_answer = second_payload["answers"][0]
    assert second_answer["question_id"] == first_answer["question_id"]
    assert second_answer["answer"] == first_answer["answer"]
    assert second_answer["telemetry"]["retrieval"] == first_answer["telemetry"]["retrieval"]
    assert second_answer["telemetry"]["usage"] == first_answer["telemetry"]["usage"]
    assert second_answer["telemetry"]["model_name"] == first_answer["telemetry"]["model_name"]


def test_build_submission_falls_back_from_gpt_5_4_mini_to_gpt_5_mini_on_http_model_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FallbackAwareProvider:
        seen_models: list[str] = []

        def __init__(self, *, model: str = "gpt-5.4-mini", **_: Any) -> None:
            self.model = model
            type(self).seen_models.append(model)

        def generate(self, *, question: str, evidence_pages: list[dict[str, Any]], max_chars: int) -> dict[str, Any]:
            del question, evidence_pages, max_chars
            if self.model == "gpt-5.4-mini":
                request = httpx.Request("POST", "https://api.openai.com/v1/responses")
                response = httpx.Response(
                    400,
                    request=request,
                    json={"error": {"message": "The model `gpt-5.4-mini` does not exist."}},
                )
                raise httpx.HTTPStatusError("unknown model", request=request, response=response)
            return {
                "answer": "The tribunal dismissed the claim with costs.",
                "confidence": 0.81,
            }

    _patch_pipeline_dependencies(monkeypatch, provider_class=FallbackAwareProvider)
    config_path, env_path = _write_config(tmp_path)

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    _write_questions(
        questions_path,
        [{"id": "q-free", "question": "Summarize the order.", "answer_type": "free_text"}],
    )
    _write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["The tribunal dismissed the claim with costs and ordered payment within 14 days."],
    )

    exit_code = _run_build_submission(
        config_path=config_path,
        env_path=env_path,
        questions_path=questions_path,
        documents_dir=documents_dir,
        output_dir=output_dir,
    )
    payload = load_submission_payload(output_dir / "submission.json")

    assert exit_code == 0
    assert FallbackAwareProvider.seen_models[:2] == ["gpt-5.4-mini", "gpt-5-mini"]
    assert payload["answers"][0]["answer"] == "The tribunal dismissed the claim with costs."
    assert payload["answers"][0]["telemetry"]["model_name"] == "gpt-5-mini"


def test_build_submission_uses_provider_token_from_env_file_when_process_env_is_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class EnvFileAwareProvider:
        seen_api_keys: list[str | None] = []

        def __init__(self, *, model: str = "gpt-5.4-mini", api_key: str | None = None, **_: Any) -> None:
            self.model = model
            self.api_key = api_key
            type(self).seen_api_keys.append(api_key)

        def generate(self, *, question: str, evidence_pages: list[dict[str, Any]], max_chars: int) -> dict[str, Any]:
            del question, evidence_pages, max_chars
            return {
                "answer": "The tribunal dismissed the claim with costs.",
                "confidence": 0.81,
            }

    _patch_pipeline_dependencies(
        monkeypatch,
        provider_class=EnvFileAwareProvider,
        inject_provider_env=False,
    )
    monkeypatch.delenv("CODEX_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CODEX_API_KEY", raising=False)
    config_path, env_path = _write_config(tmp_path, include_provider_token=True)

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    _write_questions(
        questions_path,
        [{"id": "q-free", "question": "Summarize the order.", "answer_type": "free_text"}],
    )
    _write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["The tribunal dismissed the claim with costs and ordered payment within 14 days."],
    )

    exit_code = _run_build_submission(
        config_path=config_path,
        env_path=env_path,
        questions_path=questions_path,
        documents_dir=documents_dir,
        output_dir=output_dir,
    )

    assert exit_code == 0
    assert EnvFileAwareProvider.seen_api_keys == ["test-token"]


def test_build_submission_prefers_process_env_provider_token_over_env_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ProcessEnvAwareProvider:
        seen_api_keys: list[str | None] = []

        def __init__(self, *, model: str = "gpt-5.4-mini", api_key: str | None = None, **_: Any) -> None:
            self.model = model
            self.api_key = api_key
            type(self).seen_api_keys.append(api_key)

        def generate(self, *, question: str, evidence_pages: list[dict[str, Any]], max_chars: int) -> dict[str, Any]:
            del question, evidence_pages, max_chars
            return {
                "answer": "The tribunal dismissed the claim with costs.",
                "confidence": 0.81,
            }

    _patch_pipeline_dependencies(
        monkeypatch,
        provider_class=ProcessEnvAwareProvider,
        inject_provider_env=False,
    )
    monkeypatch.setenv("CODEX_OAUTH_TOKEN", "process-token")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CODEX_API_KEY", raising=False)
    config_path, env_path = _write_config(tmp_path, include_provider_token=True)

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    _write_questions(
        questions_path,
        [{"id": "q-free", "question": "Summarize the order.", "answer_type": "free_text"}],
    )
    _write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["The tribunal dismissed the claim with costs and ordered payment within 14 days."],
    )

    exit_code = _run_build_submission(
        config_path=config_path,
        env_path=env_path,
        questions_path=questions_path,
        documents_dir=documents_dir,
        output_dir=output_dir,
    )

    assert exit_code == 0
    assert ProcessEnvAwareProvider.seen_api_keys == ["process-token"]


def test_build_submission_does_not_fallback_to_same_env_file_key_when_process_env_key_is_blank(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BlankProcessEnvProvider:
        seen_api_keys: list[str | None] = []

        def __init__(self, *, model: str = "gpt-5.4-mini", api_key: str | None = None, **_: Any) -> None:
            self.model = model
            self.api_key = api_key
            type(self).seen_api_keys.append(api_key)

        def generate(self, *, question: str, evidence_pages: list[dict[str, Any]], max_chars: int) -> dict[str, Any]:
            del question, evidence_pages, max_chars
            return {
                "answer": "The tribunal dismissed the claim with costs.",
                "confidence": 0.81,
            }

    _patch_pipeline_dependencies(
        monkeypatch,
        provider_class=BlankProcessEnvProvider,
        inject_provider_env=False,
    )
    monkeypatch.setenv("CODEX_OAUTH_TOKEN", "   ")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CODEX_API_KEY", raising=False)
    config_path, env_path = _write_config(tmp_path, include_provider_token=False)
    env_path.write_text(
        "\n".join(
            [
                "COMPETITION_API_KEY=test-key",
                "CODEX_OAUTH_TOKEN=env-file-codex-token",
                "OPENAI_API_KEY=env-file-openai-token",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    _write_questions(
        questions_path,
        [{"id": "q-free", "question": "Summarize the order.", "answer_type": "free_text"}],
    )
    _write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["The tribunal dismissed the claim with costs and ordered payment within 14 days."],
    )

    exit_code = _run_build_submission(
        config_path=config_path,
        env_path=env_path,
        questions_path=questions_path,
        documents_dir=documents_dir,
        output_dir=output_dir,
    )

    assert exit_code == 0
    assert BlankProcessEnvProvider.seen_api_keys == ["env-file-openai-token"]


def test_build_submission_supports_custom_provider_without_api_key_constructor_parameter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ModelOnlyProvider:
        seen_models: list[str] = []

        def __init__(self, *, model: str = "gpt-5.4-mini") -> None:
            self.model = model
            type(self).seen_models.append(model)

        def generate(self, *, question: str, evidence_pages: list[dict[str, Any]], max_chars: int) -> dict[str, Any]:
            del question, evidence_pages, max_chars
            return {
                "answer": "The tribunal dismissed the claim with costs.",
                "confidence": 0.81,
            }

    _patch_pipeline_dependencies(
        monkeypatch,
        provider_class=ModelOnlyProvider,
        inject_provider_env=False,
    )
    monkeypatch.setenv("CODEX_OAUTH_TOKEN", "process-token")
    config_path, env_path = _write_config(tmp_path, include_provider_token=True)

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    _write_questions(
        questions_path,
        [{"id": "q-free", "question": "Summarize the order.", "answer_type": "free_text"}],
    )
    _write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["The tribunal dismissed the claim with costs and ordered payment within 14 days."],
    )

    exit_code = _run_build_submission(
        config_path=config_path,
        env_path=env_path,
        questions_path=questions_path,
        documents_dir=documents_dir,
        output_dir=output_dir,
    )
    payload = load_submission_payload(output_dir / "submission.json")

    assert exit_code == 0
    assert payload["answers"][0]["answer"] == "The tribunal dismissed the claim with costs."
    assert payload["answers"][0]["telemetry"]["model_name"] == "gpt-5.4-mini"
    assert ModelOnlyProvider.seen_models == ["gpt-5.4-mini"]


def test_build_submission_does_not_require_provider_credentials_for_deterministic_only_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ExplodingProvider:
        def __init__(self, **_: Any) -> None:
            raise AssertionError("Provider should not be instantiated for deterministic-only runs.")

    _patch_pipeline_dependencies(
        monkeypatch,
        provider_class=ExplodingProvider,
        inject_provider_env=False,
    )
    monkeypatch.delenv("CODEX_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CODEX_API_KEY", raising=False)
    config_path, env_path = _write_config(tmp_path, include_provider_token=False)

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    _write_questions(
        questions_path,
        [{"id": "q1", "question": "Within how many days must payment be made?", "answer_type": "number"}],
    )
    _write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["Section 4 Notice. Payment must be made within 10 days after invoice."],
    )

    exit_code = _run_build_submission(
        config_path=config_path,
        env_path=env_path,
        questions_path=questions_path,
        documents_dir=documents_dir,
        output_dir=output_dir,
    )
    payload = load_submission_payload(output_dir / "submission.json")

    assert exit_code == 0
    assert payload["answers"][0]["answer"] == pytest.approx(10.0)


def test_build_submission_fails_fast_when_local_validation_detects_invalid_page_refs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_pipeline_dependencies(monkeypatch)
    config_path, env_path = _write_config(tmp_path)

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    _write_questions(
        questions_path,
        [{"id": "q1", "question": "Within how many days must payment be made?", "answer_type": "number"}],
    )
    _write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["Section 4 Notice. Payment must be made within 10 days after invoice."],
    )

    invalid_retrieval = RetrievalResult(
        question_id="q1",
        query="Within how many days must payment be made?",
        answer_type="number",
        candidate_count=1,
        reranked_count=1,
        evidence_chunks=[
            RetrievedChunk(
                chunk_id="c1",
                doc_id="alpha",
                page_span=[1],
                chunk_type="clause",
                text="Payment must be made within 10 days after invoice.",
                retrieval_score=0.99,
            )
        ],
        retrieved_chunk_pages=[PageReference(doc_id="alpha", page_numbers=[0])],
        is_unanswerable=False,
    )

    invalid_answer = AnswerResult(
        question_id="q1",
        answer=10,
        confidence=1.0,
        evidence_pages=[PageReference(doc_id="alpha", page_numbers=[0])],
    )

    monkeypatch.setattr("src.retrieval.service.RetrievalService.retrieve", lambda self, question: invalid_retrieval)
    monkeypatch.setattr("src.answering.service.AnsweringService.answer_question", lambda self, question: invalid_answer)

    with pytest.raises(SystemExit) as exc_info:
        _run_build_submission(
            config_path=config_path,
            env_path=env_path,
            questions_path=questions_path,
            documents_dir=documents_dir,
            output_dir=output_dir,
        )

    assert exc_info.value.code == 1
    assert not (output_dir / "submission.json").exists()


def test_build_submission_uses_elapsed_wall_clock_for_non_streaming_timing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_pipeline_dependencies(monkeypatch)
    config_path, env_path = _write_config(tmp_path)

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    _write_questions(
        questions_path,
        [{"id": "q1", "question": "Within how many days must payment be made?", "answer_type": "number"}],
    )
    _write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["Section 4 Notice. Payment must be made within 10 days after invoice."],
    )

    clock_values = [100.0, 100.25]

    def _fake_perf_counter() -> float:
        if clock_values:
            return clock_values.pop(0)
        return 100.25

    monkeypatch.setattr("src.submission.pipeline.time.perf_counter", _fake_perf_counter)

    exit_code = _run_build_submission(
        config_path=config_path,
        env_path=env_path,
        questions_path=questions_path,
        documents_dir=documents_dir,
        output_dir=output_dir,
    )
    payload = load_submission_payload(output_dir / "submission.json")
    timing = payload["answers"][0]["telemetry"]["timing"]

    assert exit_code == 0
    assert timing["total_time_ms"] == pytest.approx(250.0)
    assert timing["ttft_ms"] == pytest.approx(250.0)
    assert timing["tpot_ms"] == pytest.approx(0.0)


def test_build_submission_rebuilds_corpus_and_index_when_pdf_content_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_pipeline_dependencies(monkeypatch)
    config_path, env_path = _write_config(tmp_path)

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    first_output_dir = tmp_path / "artifacts-run-1"
    second_output_dir = tmp_path / "artifacts-run-2"

    _write_questions(
        questions_path,
        [{"id": "q1", "question": "Within how many days must payment be made?", "answer_type": "number"}],
    )
    document_path = documents_dir / "alpha.pdf"
    _write_pdf(
        document_path,
        page_texts=["Section 4 Notice. Payment must be made within 10 days after invoice."],
    )

    first_exit_code = _run_build_submission(
        config_path=config_path,
        env_path=env_path,
        questions_path=questions_path,
        documents_dir=documents_dir,
        output_dir=first_output_dir,
    )
    assert first_exit_code == 0

    _write_pdf(
        document_path,
        page_texts=["Section 4 Notice. Payment must be made within 20 days after invoice."],
    )

    parse_corpus_calls = 0
    build_indices_calls = 0
    original_parse_corpus = importlib.import_module("src.ingestion.service").CorpusParseService.parse_corpus
    original_build_indices = importlib.import_module("src.indexing.service").HybridIndexService.build_indices

    def _tracked_parse_corpus(self: Any, *args: Any, **kwargs: Any) -> Any:
        nonlocal parse_corpus_calls
        parse_corpus_calls += 1
        return original_parse_corpus(self, *args, **kwargs)

    def _tracked_build_indices(self: Any, *args: Any, **kwargs: Any) -> Any:
        nonlocal build_indices_calls
        build_indices_calls += 1
        return original_build_indices(self, *args, **kwargs)

    monkeypatch.setattr("src.ingestion.service.CorpusParseService.parse_corpus", _tracked_parse_corpus)
    monkeypatch.setattr("src.indexing.service.HybridIndexService.build_indices", _tracked_build_indices)

    second_exit_code = _run_build_submission(
        config_path=config_path,
        env_path=env_path,
        questions_path=questions_path,
        documents_dir=documents_dir,
        output_dir=second_output_dir,
    )

    assert second_exit_code == 0
    assert parse_corpus_calls >= 1
    assert build_indices_calls >= 1


def test_build_submission_sanitizes_question_id_before_writing_trace_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_pipeline_dependencies(monkeypatch, inject_provider_env=False)
    config_path, env_path = _write_config(tmp_path, include_provider_token=False)

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    _write_questions(
        questions_path,
        [{"id": "external/q1", "question": "Within how many days must payment be made?", "answer_type": "number"}],
    )
    _write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["Section 4 Notice. Payment must be made within 10 days after invoice."],
    )

    exit_code = _run_build_submission(
        config_path=config_path,
        env_path=env_path,
        questions_path=questions_path,
        documents_dir=documents_dir,
        output_dir=output_dir,
    )

    trace_manifest = load_submission_payload(output_dir / "trace_manifest.json")
    trace_record = trace_manifest["traces"][0]
    trace_relative_path = Path(trace_record["path"])

    assert exit_code == 0
    assert trace_record["question_id"] == "external/q1"
    assert len(trace_relative_path.parts) == 2
    assert trace_relative_path.parts[0] == "traces"
    assert "external" not in trace_relative_path.name or "/" not in trace_relative_path.name
    assert (output_dir / trace_relative_path).exists()


def test_code_archive_excludes_env_secret_files(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (project_root / ".env").write_text("COMPETITION_API_KEY=secret\n", encoding="utf-8")
    (project_root / ".env.local").write_text("CODEX_OAUTH_TOKEN=secret\n", encoding="utf-8")
    (project_root / "nested").mkdir(parents=True, exist_ok=True)
    (project_root / "nested" / ".env.production").write_text("OPENAI_API_KEY=secret\n", encoding="utf-8")

    archive_path = tmp_path / "code_archive.zip"
    packager = SubmissionPackager()
    packager.create_code_archive(output_path=archive_path, project_root=project_root)

    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())

    assert "main.py" in names
    assert ".env" not in names
    assert ".env.local" not in names
    assert "nested/.env.production" not in names


def test_code_archive_excludes_env_example_even_when_explicitly_included(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    src_dir = project_root / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (project_root / ".env.example").write_text("CODEX_OAUTH_TOKEN=template\n", encoding="utf-8")
    (project_root / ".env.production").write_text("CODEX_OAUTH_TOKEN=secret\n", encoding="utf-8")

    archive_path = tmp_path / "code_archive.zip"
    packager = SubmissionPackager()
    packager.create_code_archive(
        output_path=archive_path,
        project_root=project_root,
        include_paths={"src", ".env.example", ".env.production"},
    )

    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())

    assert "src/main.py" in names
    assert ".env.example" not in names
    assert ".env.production" not in names


def test_code_archive_exclusion_handles_paths_outside_project_root(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)
    external_file = tmp_path / "outside" / "python3.12"
    external_file.parent.mkdir(parents=True, exist_ok=True)
    external_file.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    assert _is_excluded(
        external_file.resolve(),
        root=project_root.resolve(),
        excluded_paths=set(),
    )


def test_code_archive_include_paths_keep_archive_under_limit_with_large_non_shipping_files(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    src_dir = project_root / "src"
    docs_dir = project_root / "docs"
    src_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "app.py").write_text("print('ok')\n", encoding="utf-8")

    large_non_shipping_file = docs_dir / "bundle.bin"
    with large_non_shipping_file.open("wb") as handle:
        handle.truncate((26 * 1024 * 1024) + 1)

    archive_path = tmp_path / "code_archive.zip"
    packager = SubmissionPackager()
    packager.create_code_archive(
        output_path=archive_path,
        project_root=project_root,
        include_paths={"src"},
    )

    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())

    assert "src/app.py" in names
    assert "docs/bundle.bin" not in names
    assert archive_path.stat().st_size <= 25 * 1024 * 1024


def test_submit_gate_honors_configured_unanswerable_retrieval_policy(tmp_path: Path) -> None:
    submit_gate_module = _load_module("src.submission.submit_gate", feature="W3D submit gate")
    questions_path = tmp_path / "questions.json"
    documents_dir = tmp_path / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)
    _write_questions(
        questions_path,
        [{"id": "q1", "question": "How many days?", "answer_type": "number"}],
    )
    _write_pdf(documents_dir / "alpha.pdf", page_texts=["Payment must be made within 10 days."])

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


def test_build_submission_propagates_unanswerable_policy_from_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_pipeline_dependencies(monkeypatch)
    config_path, env_path = _write_config(
        tmp_path,
        unanswerable_retrieval_policy=UnanswerableRetrievalPolicy.REQUIRE_NON_EMPTY.value,
    )

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    _write_questions(
        questions_path,
        [{"id": "q1", "question": "Within how many days must payment be made?", "answer_type": "number"}],
    )
    _write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["Section 4 Notice. Payment must be made within 10 days after invoice."],
    )

    unanswerable_retrieval = RetrievalResult(
        question_id="q1",
        query="Within how many days must payment be made?",
        answer_type="number",
        candidate_count=0,
        reranked_count=0,
        evidence_chunks=[],
        retrieved_chunk_pages=[],
        is_unanswerable=True,
    )
    unanswerable_answer = AnswerResult(
        question_id="q1",
        answer=None,
        confidence=0.0,
        evidence_pages=[],
    )

    monkeypatch.setattr(
        "src.retrieval.service.RetrievalService.retrieve",
        lambda self, question: unanswerable_retrieval,
    )
    monkeypatch.setattr(
        "src.answering.service.AnsweringService.answer_question",
        lambda self, question: unanswerable_answer,
    )

    with pytest.raises(SystemExit) as exc_info:
        _run_build_submission(
            config_path=config_path,
            env_path=env_path,
            questions_path=questions_path,
            documents_dir=documents_dir,
            output_dir=output_dir,
        )

    assert exc_info.value.code == 1
    assert not (output_dir / "submission.json").exists()
