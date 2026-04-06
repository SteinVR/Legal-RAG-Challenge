#!/usr/bin/env python3
"""Run retrieval-only grounding benchmark for autoresearch loops.

This runner evaluates grounding on benchmark references without invoking
OpenAI/API answering paths. It is designed for fast keep/discard loops where
the primary objective is `grounding_mean`.
"""

from __future__ import annotations

import argparse
import re
import time
from dataclasses import dataclass, replace
from pathlib import Path

from src.answering.page_attribution import (
    PageAttributionConfig,
    candidate_pages_from_chunks,
    group_page_reference_pairs,
    prune_candidate_pages,
)
from src.answering.service_types import extract_query_metadata
from src.common.config import DEFAULT_CONFIG_PATH, AppConfig, load_app_config
from src.common.schemas import QuestionRecord
from src.evaluation.contracts import (
    PageReference,
    ReferenceAnswerRecord,
    flatten_page_references,
    load_question_records,
    load_reference_records,
)
from src.evaluation.scorer import score_grounding
from src.indexing.service import IndexPaths, build_query_embedder
from src.retrieval.hybrid_search import QdrantHybridSearchBackend, RRFHybridSearch
from src.retrieval.reranker import QwenReranker
from src.retrieval.service import RetrievalResult, RetrievalService

_TITLE_PAGE_QUERY_PATTERN = re.compile(r"\b(?:title|cover)\s+page\b", re.IGNORECASE)
_EXPLICIT_PAGE_NUMBER_PATTERN = re.compile(r"\bpage\s+(?P<page>\d{1,3})\b", re.IGNORECASE)
_EXPLICIT_PAGE_PHRASES: dict[str, int] = {
    "first page": 1,
    "second page": 2,
    "third page": 3,
    "fourth page": 4,
    "fifth page": 5,
    "title page": 1,
    "cover page": 1,
}


@dataclass(slots=True, frozen=True)
class GroundingRunMetrics:
    """Aggregated metrics produced by one grounding run."""

    question_count: int
    grounding_mean: float
    grounding_zero_count: int
    runtime_sec: float


def _build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for the grounding autoresearch runner."""

    parser = argparse.ArgumentParser(description="Retrieval-only grounding benchmark runner.")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the app config YAML.",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to environment file used by config loader.",
    )
    parser.add_argument(
        "--phase",
        choices=("warmup", "final"),
        default=None,
        help="Optional phase override.",
    )
    parser.add_argument(
        "--questions-path",
        required=True,
        help="Path to questions JSON (phase-local questions.json).",
    )
    parser.add_argument(
        "--benchmark-path",
        required=True,
        help="Path to benchmark JSON with references/gold_retrieval.",
    )
    return parser


def _assert_file_exists(*, path: Path, description: str) -> None:
    """Validate required input file presence."""

    if not path.exists():
        raise FileNotFoundError(f"{description} is required: {path}")


def _assert_index_artifacts_ready(index_paths: IndexPaths) -> None:
    """Validate minimal retrieval index artifacts before benchmark run."""

    required = [
        index_paths.qdrant_dir,
        index_paths.manifest_path,
        index_paths.page_parent_map_path,
        index_paths.sparse_encoder_state_path,
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Index artifacts are incomplete. Run build-indices first. Missing: "
            + ", ".join(str(path) for path in missing)
        )


def _effective_page_attribution_config(
    *,
    base_config: PageAttributionConfig,
    question_text: str,
) -> PageAttributionConfig:
    """Apply title-page exception so title-page queries are not over-suppressed."""

    if not base_config.suppress_title_pages:
        return base_config
    if not _TITLE_PAGE_QUERY_PATTERN.search(question_text):
        return base_config
    return replace(base_config, suppress_title_pages=False)


def _predict_page_references(
    *,
    question: QuestionRecord,
    retrieval_result: RetrievalResult,
    base_config: PageAttributionConfig,
) -> list[PageReference]:
    """Compute predicted page references via retrieval + Pass A page attribution."""

    if not retrieval_result.evidence_chunks:
        return []

    candidate_pages = candidate_pages_from_chunks(retrieval_result.evidence_chunks)
    effective_config = _effective_page_attribution_config(
        base_config=base_config,
        question_text=question.question,
    )
    pass_a_result = prune_candidate_pages(candidate_pages, config=effective_config)
    selected_pairs = {
        (page.doc_id, int(page.page_number))
        for page in pass_a_result.selected_pages
        if int(page.page_number) > 0
    }
    selected_pairs = _filter_pairs_by_explicit_page_hints(
        selected_pairs=selected_pairs,
        question_text=question.question,
    )
    if selected_pairs:
        return group_page_reference_pairs(selected_pairs)

    fallback_pairs = flatten_page_references(retrieval_result.retrieved_chunk_pages)
    fallback_pairs = _filter_pairs_by_explicit_page_hints(
        selected_pairs=fallback_pairs,
        question_text=question.question,
    )
    return group_page_reference_pairs(fallback_pairs)


def _filter_pairs_by_explicit_page_hints(
    *,
    selected_pairs: set[tuple[str, int]],
    question_text: str,
) -> set[tuple[str, int]]:
    """Narrow predicted pages when the question explicitly names target page numbers.

    The filter is conservative: when explicit hints exist but none of the predicted
    pairs match, it preserves the original predictions to avoid introducing empty
    retrieval outputs.
    """

    if not selected_pairs:
        return selected_pairs

    explicit_pages = _extract_explicit_page_hints(question_text)
    if not explicit_pages:
        return selected_pairs

    filtered_pairs = {(doc_id, page_number) for doc_id, page_number in selected_pairs if page_number in explicit_pages}
    return filtered_pairs or selected_pairs


def _extract_explicit_page_hints(question_text: str) -> set[int]:
    """Extract explicit target page hints from question text."""

    explicit_pages = {int(match.group("page")) for match in _EXPLICIT_PAGE_NUMBER_PATTERN.finditer(question_text)}
    lowered_question = question_text.casefold()
    for phrase, page_number in _EXPLICIT_PAGE_PHRASES.items():
        if phrase in lowered_question:
            explicit_pages.add(page_number)
    return {page_number for page_number in explicit_pages if page_number > 0}


def _assert_gpu_runtime_contract(config: AppConfig) -> tuple[object, QwenReranker]:
    """Hard-fail when retrieval models are not available on CUDA."""

    try:
        import torch
    except Exception as exc:  # pragma: no cover - import failure is environment-specific
        raise RuntimeError(f"GPU runtime contract failed: torch unavailable: {exc}") from exc

    if not torch.cuda.is_available():
        raise RuntimeError("GPU runtime contract failed: torch.cuda.is_available() is False.")

    query_embedder = build_query_embedder(config)
    vectors = query_embedder.encode(["autoresearch grounding gpu preflight"])
    if not vectors or not vectors[0]:
        raise RuntimeError("GPU runtime contract failed: query embedder returned empty vectors.")

    embedder_model = query_embedder._load_model()  # type: ignore[attr-defined]
    embedder_device = str(getattr(embedder_model, "device", "")).lower()
    if not embedder_device.startswith("cuda"):
        raise RuntimeError(
            f"GPU runtime contract failed: query embedder is not on CUDA (device={embedder_device!r})."
        )

    reranker = QwenReranker()
    scores = reranker.backend.score(
        "autoresearch grounding gpu preflight",
        ["This probe checks local reranker CUDA availability."],
    )
    if not scores or len(scores) != 1:
        raise RuntimeError("GPU runtime contract failed: reranker preflight returned invalid scores.")
    reranker_device = str(getattr(reranker.backend, "_runtime_device", "")).lower()
    if not reranker_device.startswith("cuda"):
        raise RuntimeError(
            f"GPU runtime contract failed: reranker is not on CUDA (device={reranker_device!r})."
        )

    return query_embedder, reranker


def _build_retrieval_service(
    *,
    config: AppConfig,
    query_embedder: object,
    reranker: QwenReranker,
    index_paths: IndexPaths,
) -> tuple[QdrantHybridSearchBackend, RetrievalService]:
    """Construct retrieval stack equivalent to submission pipeline retrieval path."""

    backend = QdrantHybridSearchBackend(
        index_dir=index_paths.index_dir,
        dense_embedder=query_embedder,
        enable_sparse_compat=True,
    )
    retrieval_settings = config.retrieval
    retrieval_service = RetrievalService(
        hybrid_search=RRFHybridSearch(backend=backend),
        reranker=reranker,
        candidate_budget=retrieval_settings.candidate_budget,
        rerank_budget=retrieval_settings.rerank_budget,
        default_evidence_budget=retrieval_settings.default_evidence_budget,
        evidence_budget_by_answer_type=dict(retrieval_settings.evidence_budget_by_answer_type),
        question_class_budgets=dict(retrieval_settings.question_class_budgets),
        min_rerank_score=retrieval_settings.min_rerank_score,
        parent_page_expansion_enabled=retrieval_settings.parent_page_expansion_enabled,
        parent_page_expansion_limit=retrieval_settings.parent_page_expansion_limit,
    )
    return backend, retrieval_service


def _run_grounding_benchmark(
    *,
    questions: list[QuestionRecord],
    references: list[ReferenceAnswerRecord],
    retrieval_service: RetrievalService,
    page_attribution_config: PageAttributionConfig,
) -> GroundingRunMetrics:
    """Execute retrieval-only grounding evaluation over all benchmark questions."""

    reference_by_question_id = {reference.question_id: reference for reference in references}
    missing_reference_ids = [question.id for question in questions if question.id not in reference_by_question_id]
    if missing_reference_ids:
        raise ValueError(
            "Questions are missing in benchmark references: "
            + ", ".join(sorted(missing_reference_ids)[:5])
            + (" ..." if len(missing_reference_ids) > 5 else "")
        )

    grounding_scores: list[float] = []
    for question in questions:
        reference = reference_by_question_id[question.id]
        query_metadata = extract_query_metadata(question.question)
        retrieval_result = retrieval_service.retrieve(question, query_metadata=query_metadata)
        predicted_references = _predict_page_references(
            question=question,
            retrieval_result=retrieval_result,
            base_config=page_attribution_config,
        )
        grounding = score_grounding(
            predicted_pairs=flatten_page_references(predicted_references),
            gold_pairs=flatten_page_references(reference.gold_retrieval),
        )
        grounding_scores.append(grounding)

    if not grounding_scores:
        raise RuntimeError("Grounding benchmark produced no scores.")

    zero_count = sum(1 for score in grounding_scores if score == 0.0)
    return GroundingRunMetrics(
        question_count=len(grounding_scores),
        grounding_mean=sum(grounding_scores) / len(grounding_scores),
        grounding_zero_count=zero_count,
        runtime_sec=0.0,
    )


def _print_summary(metrics: GroundingRunMetrics) -> None:
    """Print human-readable summary and greppable metric line."""

    print(f"questions={metrics.question_count}")
    print(f"grounding_mean={metrics.grounding_mean:.12f}")
    print(f"grounding_zero_count={metrics.grounding_zero_count}")
    print(f"runtime_sec={metrics.runtime_sec:.3f}")
    print(
        "AUTORESEARCH_METRIC "
        f"grounding_mean={metrics.grounding_mean:.12f} "
        f"grounding_zero_count={metrics.grounding_zero_count} "
        f"runtime_sec={metrics.runtime_sec:.3f} "
        f"question_count={metrics.question_count}"
    )


def main() -> int:
    """Run retrieval-only grounding benchmark and print parseable metrics."""

    args = _build_parser().parse_args()
    started_at = time.perf_counter()

    config = load_app_config(
        Path(args.config),
        env_file=Path(args.env_file),
        phase_override=args.phase,
    )
    questions_path = Path(args.questions_path)
    benchmark_path = Path(args.benchmark_path)
    _assert_file_exists(path=questions_path, description="Questions file")
    _assert_file_exists(path=benchmark_path, description="Benchmark file")

    index_paths = IndexPaths.from_config(config)
    _assert_index_artifacts_ready(index_paths)

    questions = load_question_records(questions_path)
    references = load_reference_records(benchmark_path)
    query_embedder, reranker = _assert_gpu_runtime_contract(config)
    page_attribution_config = PageAttributionConfig(**config.page_attribution.model_dump())
    backend, retrieval_service = _build_retrieval_service(
        config=config,
        query_embedder=query_embedder,
        reranker=reranker,
        index_paths=index_paths,
    )
    try:
        raw_metrics = _run_grounding_benchmark(
            questions=questions,
            references=references,
            retrieval_service=retrieval_service,
            page_attribution_config=page_attribution_config,
        )
    finally:
        backend.close()

    metrics = GroundingRunMetrics(
        question_count=raw_metrics.question_count,
        grounding_mean=raw_metrics.grounding_mean,
        grounding_zero_count=raw_metrics.grounding_zero_count,
        runtime_sec=time.perf_counter() - started_at,
    )
    _print_summary(metrics)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
