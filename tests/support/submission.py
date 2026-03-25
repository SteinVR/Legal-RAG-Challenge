from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import pytest

from src.answering.service import AnswerResult
from src.common.schemas import QuestionRecord
from src.evaluation.contracts import (
    UnanswerableRetrievalPolicy,
    load_question_records,
    load_submission_payload,
    question_types_from_questions,
)
from src.evaluation.validator import SubmissionValidator, ValidationPolicy, build_corpus_registry
from src.main import build_parser, main
from src.retrieval.service import RetrievalResult
from tests.support.imports import load_module


class StubDenseEmbedder:
    def encode(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for index, text in enumerate(texts, start=1):
            token_count = max(len(text.split()), 1)
            vectors.append([float(token_count), float(len(text)), float(index)])
        return vectors


class OfflineCodexProvider:
    seen_models: list[str] = []
    generate_calls: list[dict[str, Any]] = []
    structured_calls: list[dict[str, Any]] = []

    def __init__(self, *, model: str = "gpt-5.4-mini", api_key: str | None = None, **_: Any) -> None:
        del api_key
        self.model = model
        type(self).seen_models.append(model)

    @classmethod
    def reset(cls) -> None:
        cls.seen_models = []
        cls.generate_calls = []
        cls.structured_calls = []

    def generate(self, *, question: str, evidence_pages: list[dict[str, Any]], max_chars: int) -> dict[str, Any]:
        del question
        type(self).generate_calls.append(
            {
                "evidence_pages": list(evidence_pages),
                "max_chars": max_chars,
            }
        )
        evidence_text = " ".join(str(page.get("text") or "") for page in evidence_pages).strip()
        summary = evidence_text.split(" and ")[0].strip().rstrip(".")
        if not summary:
            summary = "There is no information on this question in the provided documents."
        return {
            "answer": summary[:max_chars] + ("" if summary.endswith(".") else "."),
            "confidence": 0.82,
        }

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

        evidence_text = " ".join(str(page.get("text") or "") for page in evidence_pages)
        relevant_pages = sorted(
            {
                int(page_number)
                for page in evidence_pages
                for page_number in page.get("page_numbers", [page.get("page_number")])
                if page_number is not None
            }
        )

        if answer_type == "number":
            number_match = re.search(r"\b(\d+(?:\.\d+)?)\s+days?\b", evidence_text, flags=re.IGNORECASE)
            if number_match is None:
                number_match = re.search(r"AED\s*([\d,]+(?:\.\d+)?)", evidence_text, flags=re.IGNORECASE)
            if number_match is None:
                return {
                    "is_answerable": False,
                    "final_answer": None,
                    "relevant_pages": [],
                    "reasoning_summary": "The retrieved evidence does not contain a grounded numeric answer.",
                    "confidence": 0.0,
                }
            return {
                "is_answerable": True,
                "final_answer": float(number_match.group(1).replace(",", "")),
                "relevant_pages": relevant_pages,
                "reasoning_summary": "The retrieved evidence states the number directly.",
                "confidence": 0.88,
            }

        if answer_type == "free_text":
            return {
                "is_answerable": True,
                "final_answer": self.generate(
                    question=question,
                    evidence_pages=evidence_pages,
                    max_chars=280,
                )["answer"],
                "relevant_pages": relevant_pages,
                "reasoning_summary": "The retrieved evidence supports the summary directly.",
                "confidence": 0.82,
            }

        return answer_schema.model_validate(
            {
                "is_answerable": False,
                "final_answer": (
                    None
                    if answer_type != "free_text"
                    else "There is no information on this question in the provided documents."
                ),
                "relevant_pages": [],
                "reasoning_summary": "The offline provider stub only covers test-local numeric and summary flows.",
                "confidence": 0.0,
            }
        ).model_dump()


def subparsers(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices
    raise AssertionError("Expected the CLI parser to expose subcommands.")


def build_submission_parser() -> tuple[str, argparse.ArgumentParser]:
    choices = subparsers(build_parser())
    for command_name in ("build-submission", "run-pipeline"):
        parser = choices.get(command_name)
        if parser is not None:
            return command_name, parser
    pytest.fail(
        "W3D orchestration CLI missing: expected one of `build-submission` or `run-pipeline` in `src.main`."
    )


def build_answer_telemetry(
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
    module = load_module("src.submission.telemetry_packer", feature="W3D telemetry packer")

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


def validate_submission_bundle(
    *,
    submission_payload: dict[str, Any],
    questions_path: Path,
    documents_dir: Path,
    code_archive_path: Path,
) -> Any:
    module = load_module("src.submission.submit_gate", feature="W3D submit gate")

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


def validate_payload_against_local_rules(*, questions_path: Path, documents_dir: Path, submission_path: Path) -> Any:
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


def run_build_submission(
    *,
    config_path: Path,
    env_path: Path,
    questions_path: Path,
    documents_dir: Path,
    output_dir: Path,
    extra_args: list[str] | None = None,
) -> int:
    command_name, _parser = build_submission_parser()
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


def simple_qwen_rerank(
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


def patch_pipeline_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    provider_class: type[Any] | None = None,
    inject_provider_env: bool = True,
) -> None:
    monkeypatch.setattr("src.ingestion.service.build_ocr_engine", lambda _settings: None)
    monkeypatch.setattr("src.ingestion.pdf_parser.build_ocr_engine", lambda _settings: None)
    monkeypatch.setattr("src.indexing.service.build_dense_embedder", lambda _settings: StubDenseEmbedder())
    monkeypatch.setattr("src.indexing.service.build_query_embedder", lambda _settings: StubDenseEmbedder())
    monkeypatch.setattr("src.retrieval.reranker.QwenReranker.rerank", simple_qwen_rerank)
    if inject_provider_env:
        monkeypatch.setenv("CODEX_OAUTH_TOKEN", "test-token")

    if provider_class is None:
        provider_class = OfflineCodexProvider

    if provider_class is OfflineCodexProvider:
        OfflineCodexProvider.reset()

    monkeypatch.setattr("src.providers.codex_provider.CodexFreeTextProvider", provider_class)
    monkeypatch.setattr("src.providers.CodexFreeTextProvider", provider_class, raising=False)
    monkeypatch.setattr("src.main.CodexFreeTextProvider", provider_class, raising=False)
