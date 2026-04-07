"""End-to-end submission pipeline orchestration."""

from __future__ import annotations

import inspect
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import fitz
from qdrant_client import QdrantClient

import src.indexing.service as indexing_service
from src.answering.decomposition import (
    answer_with_decomposition,
    should_decompose,
)
from src.answering.page_attribution import PageAttributionConfig
from src.answering.service import (
    AnsweringService,
    AnswerResult,
    extract_query_metadata,
)
from src.common.config import AppConfig
from src.common.file_hash import sha256_for_file
from src.common.runtime_logging import get_logger, log_event, questions_debug_enabled
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
from src.retrieval.reranker import QwenReranker
from src.retrieval.service import RetrievalResult, RetrievalService
from src.submission.packager import SubmissionPackager, build_submission_payload
from src.submission.submit_gate import MAX_CODE_ARCHIVE_BYTES, SubmitGate
from src.submission.sync import PhasePaths
from src.submission.telemetry_packer import build_answer_telemetry

from src.submission.pipeline_utils import (
    _CachingRetriever,
    _LazyProvider,
    _architecture_summary,
    _assert_required_gpu_runtime,
    _close_quietly,
    _config_aligned_to_documents_dir,
    _corpus_artifacts_complete,
    _elapsed_milliseconds,
    _estimate_input_tokens,
    _estimate_output_tokens,
    _index_artifacts_complete,
    _project_root,
    _supports_api_key_argument,
    _synthetic_retrieval_from_decomposition,
    _validate_locally_before_packaging,
    _write_trace_artifacts,
    format_build_submission_result,
)

FREE_TEXT_MODEL = "gpt-5.4-mini"
DETERMINISTIC_MODEL_NAME = "deterministic-extractor"
LOGGER = get_logger("submission.pipeline")
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
        env_file: Path | None = None,
        provider_class: type = CodexFreeTextProvider,
        max_code_archive_bytes: int = MAX_CODE_ARCHIVE_BYTES,
        provider_api_key: str | None = None,
        clock: Any | None = None,
    ) -> None:
        """Execute `__init__`.

        Args:
            config: Input parameter.
            env_file: Input parameter.
            provider_class: Input parameter.
            max_code_archive_bytes: Input parameter.
            provider_api_key: Input parameter.
            clock: Input parameter.

        Returns:
            None: This initializer does not return a value.
        """
        self.config = config
        self.env_file = env_file or Path(".env")
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
        """Build submission.

        Args:
            questions_path: Input parameter.
            documents_dir: Input parameter.
            output_dir: Input parameter.

        Returns:
            Any: The computed result of the function.
        """
        resolved_questions_path = Path(questions_path)
        resolved_documents_dir = Path(documents_dir)
        resolved_output_dir = Path(output_dir)
        log_event(
            LOGGER,
            logging.INFO,
            "build_submission.start",
            "Starting submission build.",
            stage="submission",
            questions_path=resolved_questions_path,
            documents_dir=resolved_documents_dir,
            output_dir=resolved_output_dir,
        )

        if not resolved_questions_path.exists():
            raise ValueError(f"Questions file does not exist: {resolved_questions_path}")
        if not resolved_documents_dir.exists():
            raise ValueError(f"Documents directory does not exist: {resolved_documents_dir}")

        runtime_config = _config_aligned_to_documents_dir(self.config, resolved_documents_dir)
        _assert_required_gpu_runtime(runtime_config)
        phase_paths = PhasePaths.from_config(runtime_config)
        if phase_paths.documents_extract_dir.resolve() != resolved_documents_dir.resolve():
            raise ValueError(
                "build-submission expects --documents-dir to match the phase-local documents directory "
                f"({phase_paths.documents_extract_dir})."
            )

        corpus_started = time.perf_counter()
        reused_corpus = self._ensure_corpus(runtime_config, resolved_documents_dir)
        corpus_ms = round((time.perf_counter() - corpus_started) * 1000, 1)
        log_event(
            LOGGER,
            logging.INFO,
            "build_submission.stage.corpus",
            "Corpus stage completed.",
            stage="submission",
            reused=reused_corpus,
            duration_ms=corpus_ms,
        )

        index_started = time.perf_counter()
        reused_index = self._ensure_index(runtime_config)
        index_ms = round((time.perf_counter() - index_started) * 1000, 1)
        log_event(
            LOGGER,
            logging.INFO,
            "build_submission.stage.index",
            "Index stage completed.",
            stage="submission",
            reused=reused_index,
            duration_ms=index_ms,
        )

        questions = load_question_records(resolved_questions_path)
        log_event(
            LOGGER,
            logging.INFO,
            "build_submission.qa.start",
            "Starting QA pipeline.",
            stage="submission",
            question_count=len(questions),
            reused_corpus=reused_corpus,
            reused_index=reused_index,
        )
        qa_started = time.perf_counter()
        answers, traces = self._run_qa_pipeline(runtime_config, questions)
        qa_ms = round((time.perf_counter() - qa_started) * 1000, 1)
        log_event(
            LOGGER,
            logging.INFO,
            "build_submission.stage.qa",
            "QA pipeline completed.",
            stage="submission",
            question_count=len(questions),
            answer_count=len(answers),
            duration_ms=qa_ms,
        )

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

        result = BuildSubmissionResult(
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
        log_event(
            LOGGER,
            logging.INFO,
            "build_submission.complete",
            "Submission build completed.",
            stage="submission",
            answer_count=result.answer_count,
            submission_path=result.submission_path,
            code_archive_path=result.code_archive_path,
            trace_manifest_path=result.trace_manifest_path,
            reused_corpus=result.reused_corpus,
            reused_index=result.reused_index,
        )
        return result

    def _ensure_corpus(self, config: AppConfig, documents_dir: Path) -> bool:
        """Execute `_ensure_corpus`.

        Args:
            config: Input parameter.
            documents_dir: Input parameter.

        Returns:
            Any: The computed result of the function.
        """
        corpus_paths = CorpusPaths.from_config(config)
        if _corpus_artifacts_complete(corpus_paths=corpus_paths, documents_dir=documents_dir):
            log_event(
                LOGGER,
                logging.INFO,
                "build_submission.corpus.reuse",
                "Reused existing corpus artifacts.",
                stage="submission",
                corpus_manifest_path=corpus_paths.corpus_manifest_path,
            )
            return True

        service = CorpusParseService(config, env_file=self.env_file)
        # Force overwrite when our integrity check fails to avoid parse-corpus internal "skip" cache reuse.
        service.parse_corpus(dry_run=False, overwrite=True)
        log_event(
            LOGGER,
            logging.INFO,
            "build_submission.corpus.rebuild",
            "Rebuilt corpus artifacts for submission build.",
            stage="submission",
            corpus_manifest_path=corpus_paths.corpus_manifest_path,
        )
        return False

    def _ensure_index(self, config: AppConfig) -> bool:
        """Execute `_ensure_index`.

        Args:
            config: Input parameter.

        Returns:
            Any: The computed result of the function.
        """
        index_paths = IndexPaths.from_config(config)
        if _index_artifacts_complete(index_paths=index_paths):
            log_event(
                LOGGER,
                logging.INFO,
                "build_submission.index.reuse",
                "Reused existing index artifacts.",
                stage="submission",
                index_manifest_path=index_paths.manifest_path,
            )
            return True

        service = HybridIndexService(config)
        # Force overwrite when integrity checks fail to prevent stale sparse-state reuse.
        service.build_indices(dry_run=False, overwrite=True)
        if not _index_artifacts_complete(index_paths=index_paths):
            raise RuntimeError(
                "Index rebuild completed but required artifacts are still incomplete. "
                "Refusing to continue with potentially dense-only or partial index state."
            )
        log_event(
            LOGGER,
            logging.INFO,
            "build_submission.index.rebuild",
            "Rebuilt index artifacts for submission build.",
            stage="submission",
            index_manifest_path=index_paths.manifest_path,
        )
        return False

    def _run_qa_pipeline(
        self,
        config: AppConfig,
        questions: list[QuestionRecord],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Run qa pipeline.

        Args:
            config: Input parameter.
            questions: Input parameter.

        Returns:
            Any: The computed result of the function.
        """
        index_paths = IndexPaths.from_config(config)
        dense_embedder = indexing_service.build_query_embedder(config)
        backend = QdrantHybridSearchBackend(
            index_dir=index_paths.index_dir,
            dense_embedder=dense_embedder,
            enable_sparse_compat=True,
        )

        provider_model = self.free_text_model
        provider = _LazyProvider(
            factory=self._build_provider,
            model=provider_model,
            supports_structured=hasattr(self.provider_class, "generate_structured"),
        )
        retrieval_settings = config.retrieval

        retrieval_service = RetrievalService(
            hybrid_search=RRFHybridSearch(backend=backend),
            reranker=QwenReranker(),
            candidate_budget=retrieval_settings.candidate_budget,
            rerank_budget=retrieval_settings.rerank_budget,
            default_evidence_budget=retrieval_settings.default_evidence_budget,
            evidence_budget_by_answer_type=dict(retrieval_settings.evidence_budget_by_answer_type),
            question_class_budgets=dict(retrieval_settings.question_class_budgets),
            min_rerank_score=retrieval_settings.min_rerank_score,
            parent_page_expansion_enabled=retrieval_settings.parent_page_expansion_enabled,
            parent_page_expansion_limit=retrieval_settings.parent_page_expansion_limit,
            query_expansion_enabled=retrieval_settings.query_expansion_enabled,
            query_expansion_max_queries=retrieval_settings.query_expansion_max_queries,
            query_expansion_case_only=retrieval_settings.query_expansion_case_only,
        )
        retriever = _CachingRetriever(retrieval_service)
        answering_service = AnsweringService(
            retriever=retriever,
            provider=provider,
            reasoning_effort_by_type=config.answering.reasoning_effort_by_type,
            confidence_threshold_by_type=config.answering.confidence_threshold_by_type,
            page_attribution_config=PageAttributionConfig(**config.page_attribution.model_dump()),
        )

        answers: list[dict[str, Any]] = []
        traces: list[dict[str, Any]] = []
        total_questions = len(questions)

        try:
            for index, question in enumerate(questions, start=1):
                question_trace_id = uuid4().hex
                question_started_at = self._clock()

                answer_result = self._answer_question(
                    question=question,
                    answering_service=answering_service,
                    decomposition_enabled=config.decomposition.enabled,
                    max_subquestions=config.decomposition.max_subquestions,
                )
                total_time_ms = _elapsed_milliseconds(
                    started_at=question_started_at,
                    ended_at=self._clock(),
                )

                if answer_result.model_name == "decomposition_w4e":
                    retrieval_result = _synthetic_retrieval_from_decomposition(question, answer_result)
                    retriever.discard_latest()
                else:
                    retrieval_result = retriever.consume_latest(question)
                default_model_name = (
                    provider_model
                    if question.answer_type == AnswerType.FREE_TEXT.value
                    else DETERMINISTIC_MODEL_NAME
                )
                model_name = answer_result.model_name or default_model_name
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
                if questions_debug_enabled():
                    log_event(
                        LOGGER,
                        logging.DEBUG,
                        "build_submission.question.complete",
                        "Question processed in QA pipeline.",
                        stage="submission",
                        question_id=question.id,
                        answer_type=question.answer_type,
                        candidate_count=retrieval_result.candidate_count,
                        reranked_count=retrieval_result.reranked_count,
                        evidence_chunk_count=len(retrieval_result.evidence_chunks),
                        duration_ms=total_time_ms,
                    )
                if index % 10 == 0 or index == total_questions:
                    log_event(
                        LOGGER,
                        logging.INFO,
                        "build_submission.qa.progress",
                        "QA pipeline progress updated.",
                        stage="submission",
                        processed_question_count=index,
                        total_question_count=total_questions,
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
        decomposition_enabled: bool = False,
        max_subquestions: int = 4,
    ) -> AnswerResult:
        """Execute `_answer_question`.

        Args:
            question: Input parameter.
            answering_service: Input parameter.
            decomposition_enabled: Input parameter.
            max_subquestions: Input parameter.

        Returns:
            Any: The computed result of the function.
        """
        if decomposition_enabled:
            query_metadata = extract_query_metadata(question.question)
            if should_decompose(question, query_metadata, enabled=True):
                return answer_with_decomposition(
                    question=question,
                    query_metadata=query_metadata,
                    answering_service=answering_service,
                    max_subquestions=max_subquestions,
                )
        return answering_service.answer_question(question)

    def _build_provider(self, model: str) -> Any:
        """Build provider.

        Args:
            model: Input parameter.

        Returns:
            Any: The computed result of the function.
        """
        provider_kwargs: dict[str, Any] = {"model": model}
        if self.provider_api_key and _supports_api_key_argument(self.provider_class):
            provider_kwargs["api_key"] = self.provider_api_key
        return self.provider_class(**provider_kwargs)
