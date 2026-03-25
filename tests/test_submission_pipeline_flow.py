from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

from src.answering.service import AnswerResult
from src.common.config import AppConfig
from src.evaluation.contracts import PageReference, UnanswerableRetrievalPolicy, load_submission_payload
from src.retrieval.service import RetrievalResult, RetrievedChunk
from src.submission import pipeline as submission_pipeline
from tests.support.config import latest_runtime_log, write_submission_test_config
from tests.support.documents import write_pdf, write_questions
from tests.support.submission import (
    OfflineCodexProvider,
    patch_pipeline_dependencies,
    run_build_submission,
    validate_payload_against_local_rules,
)

pytestmark = pytest.mark.integration


@pytest.mark.slow
def test_build_submission_runs_real_w3abc_flow_and_writes_locally_valid_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_pipeline_dependencies(monkeypatch)
    config_path, env_path = write_submission_test_config(tmp_path)

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    write_questions(
        questions_path,
        [{"id": "q1", "question": "Within how many days must payment be made?", "answer_type": "number"}],
    )
    write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["Section 4 Notice. Payment must be made within 10 days after invoice."],
    )

    exit_code = run_build_submission(
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

    report = validate_payload_against_local_rules(
        questions_path=questions_path,
        documents_dir=documents_dir,
        submission_path=submission_path,
    )
    assert report.valid is True


@pytest.mark.slow
def test_build_submission_uses_provider_model_for_schema_first_typed_answers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StructuredNumberProvider:
        seen_models: list[str] = []
        structured_calls: list[dict[str, Any]] = []

        def __init__(self, *, model: str = "gpt-5.4-mini", api_key: str | None = None, **_: Any) -> None:
            del api_key
            self.model = model
            type(self).seen_models.append(model)

        def generate(self, **_: Any) -> dict[str, Any]:
            raise AssertionError(
                "TASK-W4B typed answering must use schema-bound structured generation, not free-text generation."
            )

        def generate_structured(
            self,
            *,
            question: str,
            answer_type: str,
            evidence_pages: list[dict[str, Any]],
            answer_schema: type[Any],
            reasoning_effort: str,
        ) -> dict[str, Any]:
            type(self).structured_calls.append(
                {
                    "question": question,
                    "answer_type": answer_type,
                    "evidence_pages": list(evidence_pages),
                    "answer_schema": answer_schema,
                    "reasoning_effort": reasoning_effort,
                }
            )
            return {
                "is_answerable": True,
                "final_answer": 10,
                "relevant_pages": [1],
                "reasoning_summary": "The payment deadline is stated directly in the retrieved clause.",
                "confidence": 0.88,
            }

    patch_pipeline_dependencies(monkeypatch, provider_class=StructuredNumberProvider)
    config_path, env_path = write_submission_test_config(tmp_path)

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    write_questions(
        questions_path,
        [{"id": "q1", "question": "Within how many days must payment be made?", "answer_type": "number"}],
    )
    write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["Section 4 Notice. Payment must be made within 10 days after invoice."],
    )

    exit_code = run_build_submission(
        config_path=config_path,
        env_path=env_path,
        questions_path=questions_path,
        documents_dir=documents_dir,
        output_dir=output_dir,
    )
    payload = load_submission_payload(output_dir / "submission.json")

    assert exit_code == 0
    assert payload["answers"][0]["answer"] == pytest.approx(10)
    assert payload["answers"][0]["telemetry"]["model_name"] == "gpt-5.4-mini"
    assert StructuredNumberProvider.seen_models == ["gpt-5.4-mini"]
    assert len(StructuredNumberProvider.structured_calls) == 1
    assert StructuredNumberProvider.structured_calls[0]["answer_type"] == "number"
    assert StructuredNumberProvider.structured_calls[0]["reasoning_effort"] == "medium"


def test_index_artifacts_complete_requires_sparse_state_for_reuse(tmp_path: Path) -> None:
    config = AppConfig.model_validate({"storage": {"root_dir": str(tmp_path)}})
    index_paths = submission_pipeline.IndexPaths.from_config(config)
    index_paths.qdrant_dir.mkdir(parents=True, exist_ok=True)
    (index_paths.qdrant_dir / "collection.bin").write_text("ok", encoding="utf-8")
    index_paths.corpus_path.parent.mkdir(parents=True, exist_ok=True)
    index_paths.corpus_path.write_text("{}", encoding="utf-8")
    index_paths.page_map_path.write_text("{}", encoding="utf-8")
    index_paths.corpus_manifest_path.write_text("{}", encoding="utf-8")
    index_paths.page_parent_map_path.write_text(json.dumps({"c1": [1]}), encoding="utf-8")
    index_paths.sparse_encoder_state_path.write_text(json.dumps({"term_index": {"fee": 1}}), encoding="utf-8")

    source_artifacts = submission_pipeline._index_source_artifacts(index_paths)
    assert source_artifacts is not None
    index_paths.manifest_path.write_text(
        json.dumps(
            {
                "chunk_count": 1,
                "source_artifacts": source_artifacts,
                "sparse_encoder_state": {
                    "path": index_paths.sparse_encoder_state_path.name,
                    "sha256": submission_pipeline._sha256_for_file(index_paths.sparse_encoder_state_path),
                },
            }
        ),
        encoding="utf-8",
    )

    class StubQdrantClient:
        def __init__(self, *, path: str) -> None:
            self.path = path

        def get_collections(self) -> Any:
            return type("Collections", (), {"collections": [type("Collection", (), {"name": "demo"})()]})()

        def get_collection(self, _name: str) -> Any:
            return type("CollectionInfo", (), {"points_count": 1})()

        def close(self) -> None:
            return None

    original_client = submission_pipeline.QdrantClient
    submission_pipeline.QdrantClient = StubQdrantClient
    try:
        assert submission_pipeline._index_artifacts_complete(index_paths=index_paths) is True
    finally:
        submission_pipeline.QdrantClient = original_client

    index_paths.sparse_encoder_state_path.unlink()

    assert submission_pipeline._index_artifacts_complete(index_paths=index_paths) is False


def test_build_submission_force_rebuilds_sparse_state_when_index_reuse_is_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = AppConfig.model_validate({"storage": {"root_dir": str(tmp_path)}})
    index_paths = submission_pipeline.IndexPaths.from_config(config)
    index_paths.qdrant_dir.mkdir(parents=True, exist_ok=True)
    (index_paths.qdrant_dir / "collection.bin").write_text("ok", encoding="utf-8")
    index_paths.corpus_path.parent.mkdir(parents=True, exist_ok=True)
    index_paths.corpus_path.write_text("{}", encoding="utf-8")
    index_paths.page_map_path.write_text("{}", encoding="utf-8")
    index_paths.corpus_manifest_path.write_text("{}", encoding="utf-8")
    index_paths.page_parent_map_path.write_text(json.dumps({"c1": [1]}), encoding="utf-8")
    index_paths.sparse_encoder_state_path.write_text(json.dumps({"term_index": {"fee": 1}}), encoding="utf-8")

    source_artifacts = submission_pipeline._index_source_artifacts(index_paths)
    assert source_artifacts is not None
    index_paths.manifest_path.write_text(
        json.dumps(
            {
                "chunk_count": 1,
                "source_artifacts": source_artifacts,
                "sparse_encoder_state": {
                    "path": index_paths.sparse_encoder_state_path.name,
                    "sha256": submission_pipeline._sha256_for_file(index_paths.sparse_encoder_state_path),
                },
            }
        ),
        encoding="utf-8",
    )
    index_paths.sparse_encoder_state_path.unlink()

    class StubQdrantClient:
        def __init__(self, *, path: str) -> None:
            self.path = path

        def get_collections(self) -> Any:
            return type("Collections", (), {"collections": [type("Collection", (), {"name": "demo"})()]})()

        def get_collection(self, _name: str) -> Any:
            return type("CollectionInfo", (), {"points_count": 1})()

        def close(self) -> None:
            return None

    build_calls: list[dict[str, Any]] = []

    class StubHybridIndexService:
        def __init__(self, config: AppConfig) -> None:
            self.config = config

        def build_indices(self, *, dry_run: bool, overwrite: bool) -> None:
            build_calls.append({"dry_run": dry_run, "overwrite": overwrite})
            rebuilt_paths = submission_pipeline.IndexPaths.from_config(self.config)
            rebuilt_paths.qdrant_dir.mkdir(parents=True, exist_ok=True)
            (rebuilt_paths.qdrant_dir / "collection.bin").write_text("ok", encoding="utf-8")
            rebuilt_paths.page_parent_map_path.write_text(json.dumps({"c1": [1]}), encoding="utf-8")
            if overwrite:
                rebuilt_paths.sparse_encoder_state_path.write_text(
                    json.dumps({"term_index": {"fee": 1}}),
                    encoding="utf-8",
                )
                rebuilt_source_artifacts = submission_pipeline._index_source_artifacts(rebuilt_paths)
                assert rebuilt_source_artifacts is not None
                rebuilt_paths.manifest_path.write_text(
                    json.dumps(
                        {
                            "chunk_count": 1,
                            "source_artifacts": rebuilt_source_artifacts,
                            "sparse_encoder_state": {
                                "path": rebuilt_paths.sparse_encoder_state_path.name,
                                "sha256": submission_pipeline._sha256_for_file(
                                    rebuilt_paths.sparse_encoder_state_path
                                ),
                            },
                        }
                    ),
                    encoding="utf-8",
                )

    monkeypatch.setattr(submission_pipeline, "QdrantClient", StubQdrantClient)
    monkeypatch.setattr(submission_pipeline, "HybridIndexService", StubHybridIndexService)

    service = submission_pipeline.BuildSubmissionService(config)

    assert service._ensure_index(config) is False
    assert build_calls == [{"dry_run": False, "overwrite": True}]
    assert submission_pipeline._index_artifacts_complete(index_paths=index_paths) is True


def test_build_submission_gpu_guard_fails_fast_when_required_runtime_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = AppConfig.model_validate({"runtime": {"require_gpu": True}, "ingestion": {"ocr_device": "gpu:0"}})

    monkeypatch.setitem(
        sys.modules,
        "torch",
        type("TorchStub", (), {"cuda": type("Cuda", (), {"is_available": staticmethod(lambda: False)})})(),
    )
    monkeypatch.setitem(
        sys.modules,
        "paddle",
        type(
            "PaddleStub",
            (),
            {
                "device": type(
                    "Device",
                    (),
                    {
                        "is_compiled_with_cuda": staticmethod(lambda: False),
                        "cuda": type("Cuda", (), {"device_count": staticmethod(lambda: 0)}),
                    },
                )()
            },
        )(),
    )

    with pytest.raises(RuntimeError, match="GPU runtime contract"):
        submission_pipeline._assert_required_gpu_runtime(config)


@pytest.mark.slow
def test_build_submission_reuses_persisted_w3a_artifacts_on_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_pipeline_dependencies(monkeypatch)
    config_path, env_path = write_submission_test_config(tmp_path)

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    first_output_dir = tmp_path / "artifacts-run-1"
    second_output_dir = tmp_path / "artifacts-run-2"

    write_questions(
        questions_path,
        [{"id": "q1", "question": "Within how many days must payment be made?", "answer_type": "number"}],
    )
    write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["Section 4 Notice. Payment must be made within 10 days after invoice."],
    )

    first_exit_code = run_build_submission(
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

    second_exit_code = run_build_submission(
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


def test_build_submission_fails_when_gpt_5_4_mini_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingProvider:
        def __init__(self, *, model: str = "gpt-5.4-mini", **_: Any) -> None:
            self.model = model

        def generate(self, *, question: str, evidence_pages: list[dict[str, Any]], max_chars: int) -> dict[str, Any]:
            del question, evidence_pages, max_chars
            request = httpx.Request("POST", "https://api.openai.com/v1/responses")
            response = httpx.Response(
                400,
                request=request,
                json={"error": {"message": "The model `gpt-5.4-mini` does not exist."}},
            )
            raise httpx.HTTPStatusError("unknown model", request=request, response=response)

    patch_pipeline_dependencies(monkeypatch, provider_class=FailingProvider)
    config_path, env_path = write_submission_test_config(tmp_path)

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    write_questions(
        questions_path,
        [{"id": "q-free", "question": "Summarize the order.", "answer_type": "free_text"}],
    )
    write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["The tribunal dismissed the claim with costs and ordered payment within 14 days."],
    )

    with pytest.raises(SystemExit) as exc_info:
        run_build_submission(
            config_path=config_path,
            env_path=env_path,
            questions_path=questions_path,
            documents_dir=documents_dir,
            output_dir=output_dir,
        )
    assert exc_info.value.code == 1
    assert not (output_dir / "submission.json").exists()


@pytest.mark.slow
def test_build_submission_returns_canonical_unanswerable_for_grounding_validation_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UngroundedProvider:
        def __init__(self, *, model: str = "gpt-5.4-mini", **_: Any) -> None:
            self.model = model

        def generate(self, *, question: str, evidence_pages: list[dict[str, Any]], max_chars: int) -> dict[str, Any]:
            del question, evidence_pages, max_chars
            return {"answer": "The tribunal granted the claim.", "confidence": 0.81}

    patch_pipeline_dependencies(monkeypatch, provider_class=UngroundedProvider)
    config_path, env_path = write_submission_test_config(tmp_path)

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    write_questions(
        questions_path,
        [{"id": "q-free", "question": "Summarize the order.", "answer_type": "free_text"}],
    )
    write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["The tribunal dismissed the claim with costs and ordered payment within 14 days."],
    )

    exit_code = run_build_submission(
        config_path=config_path,
        env_path=env_path,
        questions_path=questions_path,
        documents_dir=documents_dir,
        output_dir=output_dir,
    )
    payload = load_submission_payload(output_dir / "submission.json")

    assert exit_code == 0
    assert payload["answers"][0]["answer"] == (
        "There is no information on this question in the provided documents."
    )


def test_build_submission_does_not_mask_generic_free_text_value_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenProvider:
        def __init__(self, *, model: str = "gpt-5.4-mini", **_: Any) -> None:
            self.model = model

        def generate(self, *, question: str, evidence_pages: list[dict[str, Any]], max_chars: int) -> dict[str, Any]:
            del question, evidence_pages, max_chars
            raise ValueError("missing credentials")

    patch_pipeline_dependencies(monkeypatch, provider_class=BrokenProvider)
    config_path, env_path = write_submission_test_config(tmp_path)

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    write_questions(
        questions_path,
        [{"id": "q-free", "question": "Summarize the order.", "answer_type": "free_text"}],
    )
    write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["The tribunal dismissed the claim with costs and ordered payment within 14 days."],
    )

    with pytest.raises(SystemExit) as exc_info:
        run_build_submission(
            config_path=config_path,
            env_path=env_path,
            questions_path=questions_path,
            documents_dir=documents_dir,
            output_dir=output_dir,
        )

    assert exc_info.value.code == 1
    assert not (output_dir / "submission.json").exists()


@pytest.mark.parametrize(
    ("process_token", "include_provider_token", "env_lines", "expected_api_key"),
    [
        (None, True, None, "test-token"),
        ("process-token", True, None, "process-token"),
        (
            "   ",
            False,
            [
                "CODEX_OAUTH_TOKEN=env-file-codex-token",
                "OPENAI_API_KEY=env-file-openai-token",
            ],
            "env-file-openai-token",
        ),
    ],
    ids=["env-file-only", "process-overrides-env-file", "blank-process-falls-back-to-openai"],
)
def test_build_submission_resolves_provider_token_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    process_token: str | None,
    include_provider_token: bool,
    env_lines: list[str] | None,
    expected_api_key: str,
) -> None:
    class ApiKeyAwareProvider:
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

    patch_pipelineDependencies = patch_pipeline_dependencies
    patch_pipelineDependencies(
        monkeypatch,
        provider_class=ApiKeyAwareProvider,
        inject_provider_env=False,
    )
    for env_var in ("CODEX_OAUTH_TOKEN", "OPENAI_API_KEY", "CODEX_API_KEY"):
        monkeypatch.delenv(env_var, raising=False)
    if process_token is not None:
        monkeypatch.setenv("CODEX_OAUTH_TOKEN", process_token)

    config_path, env_path = write_submission_test_config(
        tmp_path,
        include_provider_token=include_provider_token,
    )
    if env_lines is not None:
        env_path.write_text("\n".join(["COMPETITION_API_KEY=test-key", *env_lines]) + "\n", encoding="utf-8")

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    write_questions(
        questions_path,
        [{"id": "q-free", "question": "Summarize the order.", "answer_type": "free_text"}],
    )
    write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["The tribunal dismissed the claim with costs and ordered payment within 14 days."],
    )

    exit_code = run_build_submission(
        config_path=config_path,
        env_path=env_path,
        questions_path=questions_path,
        documents_dir=documents_dir,
        output_dir=output_dir,
    )

    assert exit_code == 0
    assert ApiKeyAwareProvider.seen_api_keys == [expected_api_key]


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

    patch_pipeline_dependencies(
        monkeypatch,
        provider_class=ModelOnlyProvider,
        inject_provider_env=False,
    )
    monkeypatch.setenv("CODEX_OAUTH_TOKEN", "process-token")
    config_path, env_path = write_submission_test_config(tmp_path, include_provider_token=True)

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    write_questions(
        questions_path,
        [{"id": "q-free", "question": "Summarize the order.", "answer_type": "free_text"}],
    )
    write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["The tribunal dismissed the claim with costs and ordered payment within 14 days."],
    )

    exit_code = run_build_submission(
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


@pytest.mark.slow
def test_build_submission_uses_structured_default_provider_for_typed_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_pipeline_dependencies(
        monkeypatch,
        inject_provider_env=False,
    )
    monkeypatch.delenv("CODEX_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CODEX_API_KEY", raising=False)
    config_path, env_path = write_submission_test_config(tmp_path, include_provider_token=False)

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    write_questions(
        questions_path,
        [{"id": "q1", "question": "Within how many days must payment be made?", "answer_type": "number"}],
    )
    write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["Section 4 Notice. Payment must be made within 10 days after invoice."],
    )

    exit_code = run_build_submission(
        config_path=config_path,
        env_path=env_path,
        questions_path=questions_path,
        documents_dir=documents_dir,
        output_dir=output_dir,
    )
    payload = load_submission_payload(output_dir / "submission.json")

    assert exit_code == 0
    assert payload["answers"][0]["answer"] == pytest.approx(10.0)
    assert payload["answers"][0]["telemetry"]["model_name"] == "gpt-5.4-mini"
    assert OfflineCodexProvider.seen_models == ["gpt-5.4-mini"]
    assert len(OfflineCodexProvider.structured_calls) == 1
    assert OfflineCodexProvider.structured_calls[0]["answer_type"] == "number"


def test_build_submission_fails_fast_when_local_validation_detects_invalid_page_refs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_pipeline_dependencies(monkeypatch)
    config_path, env_path = write_submission_test_config(tmp_path)

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    write_questions(
        questions_path,
        [{"id": "q1", "question": "Within how many days must payment be made?", "answer_type": "number"}],
    )
    write_pdf(
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

    monkeypatch.setattr(
        "src.retrieval.service.RetrievalService.retrieve",
        lambda self, question, query_metadata=None: invalid_retrieval,
    )
    monkeypatch.setattr("src.answering.service.AnsweringService.answer_question", lambda self, question: invalid_answer)

    with pytest.raises(SystemExit) as exc_info:
        run_build_submission(
            config_path=config_path,
            env_path=env_path,
            questions_path=questions_path,
            documents_dir=documents_dir,
            output_dir=output_dir,
        )

    assert exc_info.value.code == 1
    assert not (output_dir / "submission.json").exists()


@pytest.mark.slow
def test_build_submission_uses_elapsed_wall_clock_for_non_streaming_timing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_pipeline_dependencies(monkeypatch)
    config_path, env_path = write_submission_test_config(tmp_path)

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    write_questions(
        questions_path,
        [{"id": "q1", "question": "Within how many days must payment be made?", "answer_type": "number"}],
    )
    write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["Section 4 Notice. Payment must be made within 10 days after invoice."],
    )

    clock_values = [100.0, 100.25]

    def _fake_perf_counter() -> float:
        if clock_values:
            return clock_values.pop(0)
        return 100.25

    pipeline_module = importlib.import_module("src.submission.pipeline")
    original_init = pipeline_module.BuildSubmissionService.__init__

    def _init_with_fake_clock(self: Any, *args: Any, **kwargs: Any) -> None:
        kwargs["clock"] = _fake_perf_counter
        original_init(self, *args, **kwargs)

    monkeypatch.setattr("src.submission.pipeline.BuildSubmissionService.__init__", _init_with_fake_clock)

    exit_code = run_build_submission(
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


@pytest.mark.slow
def test_build_submission_rebuilds_corpus_and_index_when_pdf_content_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_pipeline_dependencies(monkeypatch)
    config_path, env_path = write_submission_test_config(tmp_path)

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    first_output_dir = tmp_path / "artifacts-run-1"
    second_output_dir = tmp_path / "artifacts-run-2"

    write_questions(
        questions_path,
        [{"id": "q1", "question": "Within how many days must payment be made?", "answer_type": "number"}],
    )
    document_path = documents_dir / "alpha.pdf"
    write_pdf(
        document_path,
        page_texts=["Section 4 Notice. Payment must be made within 10 days after invoice."],
    )

    first_exit_code = run_build_submission(
        config_path=config_path,
        env_path=env_path,
        questions_path=questions_path,
        documents_dir=documents_dir,
        output_dir=first_output_dir,
    )
    assert first_exit_code == 0

    write_pdf(
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

    second_exit_code = run_build_submission(
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
    patch_pipeline_dependencies(monkeypatch, inject_provider_env=False)
    config_path, env_path = write_submission_test_config(tmp_path, include_provider_token=False)

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    write_questions(
        questions_path,
        [{"id": "external/q1", "question": "Within how many days must payment be made?", "answer_type": "number"}],
    )
    write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["Section 4 Notice. Payment must be made within 10 days after invoice."],
    )

    exit_code = run_build_submission(
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


@pytest.mark.slow
def test_build_submission_emits_question_debug_runtime_logs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_pipeline_dependencies(monkeypatch, inject_provider_env=False)
    config_path, env_path = write_submission_test_config(
        tmp_path,
        include_provider_token=False,
        debug_questions=True,
    )

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    write_questions(
        questions_path,
        [{"id": "q1", "question": "Within how many days must payment be made?", "answer_type": "number"}],
    )
    write_pdf(
        documents_dir / "alpha.pdf",
        page_texts=["Section 4 Notice. Payment must be made within 10 days after invoice."],
    )

    exit_code = run_build_submission(
        config_path=config_path,
        env_path=env_path,
        questions_path=questions_path,
        documents_dir=documents_dir,
        output_dir=output_dir,
    )
    payloads = [
        json.loads(line)
        for line in latest_runtime_log(tmp_path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    events = {payload["event"] for payload in payloads}

    assert exit_code == 0
    assert "build_submission.question.complete" in events
    assert "answer.complete" in events


def test_build_submission_propagates_unanswerable_policy_from_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_pipeline_dependencies(monkeypatch)
    config_path, env_path = write_submission_test_config(
        tmp_path,
        unanswerable_retrieval_policy=UnanswerableRetrievalPolicy.REQUIRE_NON_EMPTY.value,
    )

    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    output_dir = tmp_path / "artifacts"

    write_questions(
        questions_path,
        [{"id": "q1", "question": "Within how many days must payment be made?", "answer_type": "number"}],
    )
    write_pdf(
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
        lambda self, question, query_metadata=None: unanswerable_retrieval,
    )
    monkeypatch.setattr(
        "src.answering.service.AnsweringService.answer_question",
        lambda self, question: unanswerable_answer,
    )

    with pytest.raises(SystemExit) as exc_info:
        run_build_submission(
            config_path=config_path,
            env_path=env_path,
            questions_path=questions_path,
            documents_dir=documents_dir,
            output_dir=output_dir,
        )

    assert exc_info.value.code == 1
    assert not (output_dir / "submission.json").exists()
