"""End-to-end submission pipeline orchestration."""

from __future__ import annotations

import inspect
import json
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

import fitz

import src.indexing.service as indexing_service
from src.answering.service import (
    CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER,
    AnsweringService,
    AnswerResult,
    FreeTextGroundingValidationError,
)
from src.common.config import AppConfig
from src.common.schemas import CorpusParseManifest, ParseStatus, Phase, QuestionRecord
from src.evaluation.contracts import (
    AnswerType,
    UnanswerableRetrievalPolicy,
    load_question_records,
    question_types_from_questions,
)
from src.evaluation.validator import (
    SubmissionValidationReport,
    SubmissionValidator,
    ValidationPolicy,
    build_corpus_registry,
)
from src.indexing.service import HybridIndexService, IndexPaths
from src.ingestion.service import CorpusParseService, CorpusPaths
from src.providers.codex_provider import CodexFreeTextProvider
from src.retrieval.hybrid_search import QdrantHybridSearchBackend, RRFHybridSearch
from src.retrieval.reranker import LexicalFallbackReranker, QwenReranker
from src.retrieval.service import RetrievalResult, RetrievalService
from src.submission.packager import SubmissionPackager, build_submission_payload
from src.submission.submit_gate import MAX_CODE_ARCHIVE_BYTES, SubmitGate
from src.submission.sync import PhasePaths
from src.submission.telemetry_packer import build_answer_telemetry

FREE_TEXT_MODEL = "gpt-5.4-mini"
DETERMINISTIC_MODEL_NAME = "deterministic-extractor"
CODE_ARCHIVE_INCLUDE_PATHS = (
    "src",
    "configs",
    "scripts",
    "tools",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
)


@dataclass(slots=True)
class BuildSubmissionResult:
    """Summary for a build-submission pipeline run."""

    command: str
    phase: str
    output_dir: Path
    submission_path: Path
    code_archive_path: Path
    trace_manifest_path: Path
    answer_count: int
    reused_corpus: bool
    reused_index: bool


class BuildSubmissionService:
    """Coordinate W3A/W3B/W3C components into a validated submission bundle."""

    def __init__(
        self,
        config: AppConfig,
        *,
        provider_class: type = CodexFreeTextProvider,
        max_code_archive_bytes: int = MAX_CODE_ARCHIVE_BYTES,
        provider_api_key: str | None = None,
        clock: Any | None = None,
    ) -> None:
        self.config = config
        self.provider_class = provider_class
        self.free_text_model = FREE_TEXT_MODEL
        self.provider_api_key = provider_api_key
        self.unanswerable_retrieval_policy = UnanswerableRetrievalPolicy(
            config.evaluation.unanswerable_retrieval_policy
        )
        self.submit_gate = SubmitGate(
            max_code_archive_bytes=max_code_archive_bytes,
            unanswerable_retrieval_policy=self.unanswerable_retrieval_policy,
        )
        self.packager = SubmissionPackager(max_code_archive_bytes=max_code_archive_bytes)
        self._clock = clock or time.perf_counter

    def build_submission(
        self,
        *,
        questions_path: str | Path,
        documents_dir: str | Path,
        output_dir: str | Path,
    ) -> BuildSubmissionResult:
        resolved_questions_path = Path(questions_path)
        resolved_documents_dir = Path(documents_dir)
        resolved_output_dir = Path(output_dir)

        if not resolved_questions_path.exists():
            raise ValueError(f"Questions file does not exist: {resolved_questions_path}")
        if not resolved_documents_dir.exists():
            raise ValueError(f"Documents directory does not exist: {resolved_documents_dir}")

        runtime_config = _config_aligned_to_documents_dir(self.config, resolved_documents_dir)
        phase_paths = PhasePaths.from_config(runtime_config)
        if phase_paths.documents_extract_dir.resolve() != resolved_documents_dir.resolve():
            raise ValueError(
                "build-submission expects --documents-dir to match the phase-local documents directory "
                f"({phase_paths.documents_extract_dir})."
            )

        reused_corpus = self._ensure_corpus(runtime_config, resolved_documents_dir)
        reused_index = self._ensure_index(runtime_config)

        questions = load_question_records(resolved_questions_path)
        answers, traces = self._run_qa_pipeline(runtime_config, questions)

        submission_payload = build_submission_payload(
            architecture_summary=_architecture_summary(),
            answers=answers,
        )
        _validate_locally_before_packaging(
            submission_payload=submission_payload,
            questions_path=resolved_questions_path,
            documents_dir=resolved_documents_dir,
            unanswerable_retrieval_policy=self.unanswerable_retrieval_policy,
        )

        resolved_output_dir.mkdir(parents=True, exist_ok=True)
        submission_path = self.packager.write_submission_payload(
            submission_payload=submission_payload,
            output_dir=resolved_output_dir,
        )
        trace_manifest_path = _write_trace_artifacts(
            output_dir=resolved_output_dir,
            phase=runtime_config.phase.value,
            traces=traces,
        )
        code_archive_path = self.packager.create_code_archive(
            output_path=resolved_output_dir / "code_archive.zip",
            project_root=_project_root(),
            excluded_paths={resolved_output_dir.resolve()},
            include_paths=CODE_ARCHIVE_INCLUDE_PATHS,
        )

        self.submit_gate.validate(
            submission_payload=submission_payload,
            questions_path=resolved_questions_path,
            documents_dir=resolved_documents_dir,
            code_archive_path=code_archive_path,
        )

        return BuildSubmissionResult(
            command="build-submission",
            phase=runtime_config.phase.value,
            output_dir=resolved_output_dir,
            submission_path=submission_path,
            code_archive_path=code_archive_path,
            trace_manifest_path=trace_manifest_path,
            answer_count=len(answers),
            reused_corpus=reused_corpus,
            reused_index=reused_index,
        )

    def _ensure_corpus(self, config: AppConfig, documents_dir: Path) -> bool:
        corpus_paths = CorpusPaths.from_config(config)
        if _corpus_artifacts_complete(corpus_paths=corpus_paths, documents_dir=documents_dir):
            return True

        service = CorpusParseService(config)
        # Force overwrite when our integrity check fails to avoid parse-corpus internal "skip" cache reuse.
        service.parse_corpus(dry_run=False, overwrite=True)
        return False

    def _ensure_index(self, config: AppConfig) -> bool:
        index_paths = IndexPaths.from_config(config)
        if _index_artifacts_complete(index_paths=index_paths):
            return True

        service = HybridIndexService(config)
        service.build_indices(dry_run=False, overwrite=False)
        return False

    def _run_qa_pipeline(
        self,
        config: AppConfig,
        questions: list[QuestionRecord],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        index_paths = IndexPaths.from_config(config)
        dense_embedder = indexing_service.build_query_embedder(config)
        backend = QdrantHybridSearchBackend(
            index_dir=index_paths.index_dir,
            dense_embedder=dense_embedder,
            enable_sparse_compat=True,
        )

        provider_model = self.free_text_model
        provider = _LazyProvider(factory=self._build_provider, model=provider_model)

        retrieval_service = RetrievalService(
            hybrid_search=RRFHybridSearch(backend=backend),
            reranker=QwenReranker(fallback_reranker=LexicalFallbackReranker()),
        )
        retriever = _CachingRetriever(retrieval_service)
        answering_service = AnsweringService(retriever=retriever, provider=provider)

        answers: list[dict[str, Any]] = []
        traces: list[dict[str, Any]] = []

        try:
            for question in questions:
                question_trace_id = uuid4().hex
                question_started_at = self._clock()

                answer_result = self._answer_question(
                    question=question,
                    answering_service=answering_service,
                )
                total_time_ms = _elapsed_milliseconds(
                    started_at=question_started_at,
                    ended_at=self._clock(),
                )

                retrieval_result = retriever.consume_latest(question)
                model_name = (
                    provider_model
                    if question.answer_type == AnswerType.FREE_TEXT.value
                    else DETERMINISTIC_MODEL_NAME
                )
                input_tokens = _estimate_input_tokens(question=question, retrieval_result=retrieval_result)
                output_tokens = _estimate_output_tokens(answer_result)

                telemetry = build_answer_telemetry(
                    retrieval_result=retrieval_result,
                    answer_result=answer_result,
                    model_name=model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_time_ms=total_time_ms,
                    ttft_ms=total_time_ms,
                    tpot_ms=0.0,
                )

                answers.append(
                    {
                        "question_id": question.id,
                        "answer": answer_result.answer,
                        "telemetry": telemetry,
                    }
                )
                traces.append(
                    {
                        "trace_id": question_trace_id,
                        "question_id": question.id,
                        "answer_type": question.answer_type,
                        "model_name": model_name,
                        "candidate_count": retrieval_result.candidate_count,
                        "reranked_count": retrieval_result.reranked_count,
                        "evidence_chunk_count": len(retrieval_result.evidence_chunks),
                        "retrieved_chunk_pages": [
                            {
                                "doc_id": str(reference["doc_id"]),
                                "page_numbers": [int(page_number) for page_number in reference["page_numbers"]],
                            }
                            for reference in telemetry["retrieval"]["retrieved_chunk_pages"]
                        ],
                    }
                )
        finally:
            _close_quietly(provider)
            _close_quietly(backend)

        return answers, traces

    def _answer_question(
        self,
        *,
        question: QuestionRecord,
        answering_service: AnsweringService,
    ) -> AnswerResult:
        try:
            return answering_service.answer_question(question)
        except FreeTextGroundingValidationError:
            return AnswerResult(
                question_id=question.id,
                answer=CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER
                if question.answer_type == AnswerType.FREE_TEXT.value
                else None,
                confidence=0.0,
                evidence_pages=[],
            )

    def _build_provider(self, model: str) -> Any:
        provider_kwargs: dict[str, Any] = {"model": model}
        if self.provider_api_key and _supports_api_key_argument(self.provider_class):
            provider_kwargs["api_key"] = self.provider_api_key
        return self.provider_class(**provider_kwargs)


def format_build_submission_result(result: BuildSubmissionResult) -> str:
    """Render a user-facing summary for build-submission."""

    lines = [
        f"command: {result.command}",
        f"phase: {result.phase}",
        f"answers: {result.answer_count}",
        f"reused_corpus: {str(result.reused_corpus).lower()}",
        f"reused_index: {str(result.reused_index).lower()}",
        f"output_dir: {result.output_dir}",
        f"submission_path: {result.submission_path}",
        f"code_archive_path: {result.code_archive_path}",
        f"trace_manifest_path: {result.trace_manifest_path}",
    ]
    return "\n".join(lines)


@dataclass(slots=True)
class _CachingRetriever:
    delegate: RetrievalService
    _latest_question_id: str | None = field(default=None, init=False)
    _latest_result: RetrievalResult | None = field(default=None, init=False)

    def retrieve(self, question: QuestionRecord) -> RetrievalResult:
        result = self.delegate.retrieve(question)
        self._latest_question_id = question.id
        self._latest_result = result
        return result

    def consume_latest(self, question: QuestionRecord) -> RetrievalResult:
        if self._latest_question_id == question.id and self._latest_result is not None:
            result = self._latest_result
            self._latest_question_id = None
            self._latest_result = None
            return result
        return self.delegate.retrieve(question)


@dataclass(slots=True)
class _LazyProvider:
    factory: Any
    model: str
    _delegate: Any | None = field(default=None, init=False, repr=False)

    def generate(self, **kwargs: Any) -> Any:
        return self._provider().generate(**kwargs)

    def close(self) -> None:
        if self._delegate is None:
            return
        _close_quietly(self._delegate)
        self._delegate = None

    def _provider(self) -> Any:
        if self._delegate is None:
            self._delegate = self.factory(self.model)
        return self._delegate


def _validate_locally_before_packaging(
    *,
    submission_payload: dict[str, Any],
    questions_path: Path,
    documents_dir: Path,
    unanswerable_retrieval_policy: UnanswerableRetrievalPolicy,
) -> SubmissionValidationReport:
    validator = SubmissionValidator(
        question_types=question_types_from_questions(load_question_records(questions_path)),
        corpus_registry=build_corpus_registry(documents_dir),
        policy=ValidationPolicy(
            unanswerable_retrieval_policy=unanswerable_retrieval_policy,
            require_full_question_coverage=True,
            emit_ambiguity_warning=True,
        ),
    )
    report = validator.validate(submission_payload)
    if report.valid:
        return report

    first_error_message = _first_validation_error_message(report)
    if first_error_message is None:
        raise ValueError("Local validation failed before packaging.")
    raise ValueError(f"Local validation failed before packaging: {first_error_message}")


def _first_validation_error_message(report: SubmissionValidationReport) -> str | None:
    for issue in report.issues:
        if issue.severity == "error":
            return issue.message
    for answer_report in report.answers:
        for issue in answer_report.issues:
            if issue.severity == "error":
                return issue.message
    return None


def _estimate_input_tokens(*, question: QuestionRecord, retrieval_result: RetrievalResult) -> int:
    total = _estimate_tokens_from_text(question.question)
    for chunk in retrieval_result.evidence_chunks:
        total += _estimate_tokens_from_text(chunk.text)
    return total


def _estimate_output_tokens(answer_result: AnswerResult) -> int:
    if answer_result.answer is None:
        return 0
    return _estimate_tokens_from_text(str(answer_result.answer))


def _estimate_tokens_from_text(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+", text))


def _elapsed_milliseconds(*, started_at: float, ended_at: float) -> float:
    return max((float(ended_at) - float(started_at)) * 1000.0, 0.0)


def _corpus_artifacts_complete(*, corpus_paths: CorpusPaths, documents_dir: Path) -> bool:
    required_paths = [
        corpus_paths.corpus_path,
        corpus_paths.page_map_path,
        corpus_paths.corpus_manifest_path,
        corpus_paths.debug_dir,
    ]
    if any(not path.exists() for path in required_paths):
        return False

    try:
        manifest = CorpusParseManifest.model_validate_json(
            corpus_paths.corpus_manifest_path.read_text(encoding="utf-8")
        )
    except Exception:
        return False

    current_pdf_paths = sorted(path for path in documents_dir.rglob("*.pdf") if path.is_file())
    current_doc_ids = {path.stem for path in current_pdf_paths}
    manifest_doc_ids = {record.doc_id for record in manifest.records}
    if manifest_doc_ids != current_doc_ids:
        return False

    manifest_by_doc_id = {record.doc_id: record for record in manifest.records}
    for pdf_path in current_pdf_paths:
        doc_id = pdf_path.stem
        manifest_record = manifest_by_doc_id.get(doc_id)
        if manifest_record is None:
            return False

        if manifest_record.sha256 != _sha256_for_file(pdf_path):
            return False

        if manifest_record.parse_status is ParseStatus.FAILED:
            continue

        try:
            with fitz.open(pdf_path) as document:
                page_count = int(document.page_count)
        except Exception:
            return False
        if int(manifest_record.page_count) != page_count:
            return False

    required_debug_docs = {
        record.doc_id
        for record in manifest.records
        if record.parse_status is not ParseStatus.FAILED and record.doc_id in current_doc_ids
    }
    return all((corpus_paths.debug_dir / f"{doc_id}.md").exists() for doc_id in required_debug_docs)


def _index_artifacts_complete(*, index_paths: IndexPaths) -> bool:
    required_paths = [
        index_paths.qdrant_dir,
        index_paths.page_parent_map_path,
        index_paths.manifest_path,
    ]
    if any(not path.exists() for path in required_paths):
        return False

    if not any(index_paths.qdrant_dir.iterdir()):
        return False

    try:
        manifest_payload = json.loads(index_paths.manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest_payload, dict):
            return False

        expected_source = _index_source_artifacts(index_paths)
        if expected_source is None:
            return False
        if manifest_payload.get("source_artifacts") != expected_source:
            return False

        chunk_count = manifest_payload.get("chunk_count")
        if not isinstance(chunk_count, int) or chunk_count <= 0:
            return False

        page_parent_map_payload = json.loads(index_paths.page_parent_map_path.read_text(encoding="utf-8"))
        if not isinstance(page_parent_map_payload, dict):
            return False
        if len(page_parent_map_payload) != chunk_count:
            return False
    except Exception:
        return False

    return True


def _index_source_artifacts(index_paths: IndexPaths) -> dict[str, Any] | None:
    source_paths = [
        index_paths.corpus_path,
        index_paths.page_map_path,
        index_paths.corpus_manifest_path,
    ]
    if any(not path.exists() for path in source_paths):
        return None

    return {
        "corpus_path": str(index_paths.corpus_path),
        "corpus_sha256": _sha256_for_file(index_paths.corpus_path),
        "page_map_path": str(index_paths.page_map_path),
        "page_map_sha256": _sha256_for_file(index_paths.page_map_path),
        "corpus_manifest_path": str(index_paths.corpus_manifest_path),
        "corpus_manifest_sha256": _sha256_for_file(index_paths.corpus_manifest_path),
    }


def _sha256_for_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _config_aligned_to_documents_dir(config: AppConfig, documents_dir: Path) -> AppConfig:
    resolved_documents_dir = documents_dir.resolve()
    extracted_name = config.storage.extracted_documents_dirname
    documents_name = config.storage.documents_dirname

    if resolved_documents_dir.name != extracted_name:
        return config
    if resolved_documents_dir.parent.name != documents_name:
        return config

    phase_name = resolved_documents_dir.parent.parent.name
    try:
        phase = Phase(phase_name)
    except ValueError:
        return config

    root_dir = resolved_documents_dir.parent.parent.parent
    return config.model_copy(
        update={
            "phase": phase,
            "storage": config.storage.model_copy(update={"root_dir": root_dir}),
        }
    )


def _write_trace_artifacts(*, output_dir: Path, phase: str, traces: list[dict[str, Any]]) -> Path:
    trace_dir = output_dir / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)

    trace_files: list[dict[str, str]] = []
    for entry in traces:
        question_id = str(entry["question_id"])
        trace_path = trace_dir / _trace_filename(question_id)
        with trace_path.open("w", encoding="utf-8") as handle:
            json.dump(entry, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        trace_files.append(
            {
                "question_id": question_id,
                "trace_id": str(entry["trace_id"]),
                "path": str(trace_path.relative_to(output_dir)),
            }
        )

    manifest_path = output_dir / "trace_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "run_trace_id": uuid4().hex,
                "phase": phase,
                "generated_at": datetime.now(tz=UTC).isoformat(),
                "trace_count": len(trace_files),
                "traces": trace_files,
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )
        handle.write("\n")
    return manifest_path


def _trace_filename(question_id: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", question_id).strip("._")
    if not normalized:
        normalized = "question"
    safe_prefix = normalized[:48]
    digest = sha256(question_id.encode("utf-8")).hexdigest()[:12]
    return f"{safe_prefix}__{digest}.json"


def _architecture_summary() -> str:
    summary = (
        "Pipeline builds/reuses phase-local corpus and hybrid index artifacts, runs hybrid retrieval with reranking, "
        "routes questions through deterministic and free-text answering, packs telemetry, validates locally, and "
        "ships submission plus code archive."
    )
    return summary[:500]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _supports_api_key_argument(provider_class: type[Any]) -> bool:
    try:
        signature = inspect.signature(provider_class)
    except (TypeError, ValueError):
        return False

    for parameter in signature.parameters.values():
        if parameter.kind is inspect.Parameter.VAR_KEYWORD:
            return True
        if parameter.name == "api_key":
            return True
    return False


def _close_quietly(resource: Any) -> None:
    close = getattr(resource, "close", None)
    if callable(close):
        close()
