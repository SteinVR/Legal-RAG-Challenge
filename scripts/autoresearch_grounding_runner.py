#!/usr/bin/env python3
"""Run retrieval-only grounding benchmark for autoresearch loops.

This runner evaluates grounding on benchmark references without invoking
OpenAI/API answering paths. It is designed for fast keep/discard loops where
the primary objective is `grounding_mean`.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path

from src.answering.page_attribution import (
    PageAttributionConfig,
    group_page_reference_pairs,
)
from src.answering.service_helpers import (
    _coerce_retrieval_payload,
    _effective_page_attribution_config,
    _pass_a_pages_from_retrieval_payload,
)
from src.answering.service_types import extract_query_metadata
from src.common.config import DEFAULT_CONFIG_PATH, AppConfig, load_app_config
from src.common.schemas import Phase, QuestionRecord
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


@dataclass(slots=True, frozen=True)
class GroundingRunMetrics:
    """Aggregated metrics produced by one grounding run."""

    question_count: int
    grounding_mean: float
    grounding_zero_count: int
    raw_grounding_mean: float
    raw_precision_mean: float
    raw_recall_mean: float
    raw_zero_recall_count: int
    pass_a_precision_mean: float
    pass_a_recall_mean: float
    pass_a_recall_gap_from_raw: float
    pass_a_recall_ratio_to_raw: float
    runtime_sec: float


@dataclass(slots=True, frozen=True)
class PairScoring:
    """Grounding components for one predicted/gold page-pair set."""

    grounding: float
    precision: float
    recall: float


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
        choices=[phase.value for phase in Phase],
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
    parser.add_argument(
        "--max-pass-a-recall-gap",
        type=float,
        default=None,
        help="Optional hard gate: fail when (raw_recall_mean - pass_a_recall_mean) exceeds this value.",
    )
    parser.add_argument(
        "--min-pass-a-recall-ratio",
        type=float,
        default=None,
        help="Optional hard gate: fail when (pass_a_recall_mean / raw_recall_mean) is below this value.",
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


def _predict_page_references(
    *,
    question: QuestionRecord,
    retrieval_result: RetrievalResult,
    base_config: PageAttributionConfig,
) -> list[PageReference]:
    """Compute pre-LLM pages exactly as the answering service does before provider call."""

    pages, _ = _coerce_retrieval_payload(retrieval_result)
    if not pages and not retrieval_result.retrieved_chunk_pages:
        return []

    effective_config = _effective_page_attribution_config(
        base_config=base_config,
        question_text=question.question,
    )
    pass_a_pages = _pass_a_pages_from_retrieval_payload(
        retrieval_output=retrieval_result,
        pages=pages,
        config=effective_config,
    )
    selected_pairs = {
        (page.doc_id, int(page_number))
        for page in pass_a_pages
        for page_number in page.page_numbers
        if int(page_number) > 0
    }
    if selected_pairs:
        return group_page_reference_pairs(selected_pairs)

    fallback_pairs = flatten_page_references(retrieval_result.retrieved_chunk_pages)
    return group_page_reference_pairs(fallback_pairs)


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
        query_expansion_enabled=retrieval_settings.query_expansion_enabled,
        query_expansion_max_queries=retrieval_settings.query_expansion_max_queries,
        query_expansion_case_only=retrieval_settings.query_expansion_case_only,
        page_map_paths=(index_paths.page_map_path,),
    )
    return backend, retrieval_service


def _score_pairs(
    *,
    predicted_pairs: set[tuple[str, int]],
    gold_pairs: set[tuple[str, int]],
) -> PairScoring:
    """Compute grounding, precision, and recall for one page-pair comparison."""

    grounding = score_grounding(predicted_pairs=predicted_pairs, gold_pairs=gold_pairs)
    if not predicted_pairs and not gold_pairs:
        return PairScoring(grounding=grounding, precision=1.0, recall=1.0)
    if not predicted_pairs:
        return PairScoring(grounding=grounding, precision=0.0, recall=0.0)

    overlap = len(predicted_pairs & gold_pairs)
    precision = overlap / len(predicted_pairs)
    recall = overlap / len(gold_pairs) if gold_pairs else 1.0
    return PairScoring(grounding=grounding, precision=precision, recall=recall)


def _mean(values: list[float]) -> float:
    """Return arithmetic mean for non-empty float lists."""

    if not values:
        raise ValueError("Cannot compute mean of an empty list.")
    return sum(values) / len(values)


def _safe_ratio(*, numerator: float, denominator: float) -> float:
    """Return a safe ratio for recall alignment reporting."""

    if denominator == 0.0:
        return 1.0 if numerator == 0.0 else 0.0
    return numerator / denominator


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

    pass_a_scores: list[PairScoring] = []
    raw_scores: list[PairScoring] = []
    for question in questions:
        reference = reference_by_question_id[question.id]
        gold_pairs = flatten_page_references(reference.gold_retrieval)
        query_metadata = extract_query_metadata(question.question)
        retrieval_result = retrieval_service.retrieve(question, query_metadata=query_metadata)

        raw_scores.append(
            _score_pairs(
                predicted_pairs=flatten_page_references(retrieval_result.retrieved_chunk_pages),
                gold_pairs=gold_pairs,
            )
        )

        predicted_references = _predict_page_references(
            question=question,
            retrieval_result=retrieval_result,
            base_config=page_attribution_config,
        )
        pass_a_scores.append(
            _score_pairs(
                predicted_pairs=flatten_page_references(predicted_references),
                gold_pairs=gold_pairs,
            )
        )

    if not pass_a_scores or not raw_scores:
        raise RuntimeError("Grounding benchmark produced no scores.")

    pass_a_grounding_values = [score.grounding for score in pass_a_scores]
    pass_a_precision_values = [score.precision for score in pass_a_scores]
    pass_a_recall_values = [score.recall for score in pass_a_scores]

    raw_grounding_values = [score.grounding for score in raw_scores]
    raw_precision_values = [score.precision for score in raw_scores]
    raw_recall_values = [score.recall for score in raw_scores]

    raw_recall_mean = _mean(raw_recall_values)
    pass_a_recall_mean = _mean(pass_a_recall_values)
    return GroundingRunMetrics(
        question_count=len(pass_a_scores),
        grounding_mean=_mean(pass_a_grounding_values),
        grounding_zero_count=sum(1 for score in pass_a_grounding_values if score == 0.0),
        raw_grounding_mean=_mean(raw_grounding_values),
        raw_precision_mean=_mean(raw_precision_values),
        raw_recall_mean=raw_recall_mean,
        raw_zero_recall_count=sum(1 for score in raw_recall_values if score == 0.0),
        pass_a_precision_mean=_mean(pass_a_precision_values),
        pass_a_recall_mean=pass_a_recall_mean,
        pass_a_recall_gap_from_raw=raw_recall_mean - pass_a_recall_mean,
        pass_a_recall_ratio_to_raw=_safe_ratio(numerator=pass_a_recall_mean, denominator=raw_recall_mean),
        runtime_sec=0.0,
    )


def _print_summary(metrics: GroundingRunMetrics) -> None:
    """Print human-readable summary and greppable metric line."""

    print(f"questions={metrics.question_count}")
    print(f"grounding_mean={metrics.grounding_mean:.12f}")
    print(f"grounding_zero_count={metrics.grounding_zero_count}")
    print(f"raw_grounding_mean={metrics.raw_grounding_mean:.12f}")
    print(f"raw_recall_mean={metrics.raw_recall_mean:.12f}")
    print(f"raw_precision_mean={metrics.raw_precision_mean:.12f}")
    print(f"raw_zero_recall_count={metrics.raw_zero_recall_count}")
    print(f"pass_a_recall_mean={metrics.pass_a_recall_mean:.12f}")
    print(f"pass_a_precision_mean={metrics.pass_a_precision_mean:.12f}")
    print(f"pass_a_recall_gap_from_raw={metrics.pass_a_recall_gap_from_raw:.12f}")
    print(f"pass_a_recall_ratio_to_raw={metrics.pass_a_recall_ratio_to_raw:.12f}")
    print(f"runtime_sec={metrics.runtime_sec:.3f}")
    print(
        "AUTORESEARCH_METRIC "
        f"grounding_mean={metrics.grounding_mean:.12f} "
        f"grounding_zero_count={metrics.grounding_zero_count} "
        f"raw_grounding_mean={metrics.raw_grounding_mean:.12f} "
        f"raw_recall_mean={metrics.raw_recall_mean:.12f} "
        f"raw_precision_mean={metrics.raw_precision_mean:.12f} "
        f"raw_zero_recall_count={metrics.raw_zero_recall_count} "
        f"pass_a_recall_mean={metrics.pass_a_recall_mean:.12f} "
        f"pass_a_precision_mean={metrics.pass_a_precision_mean:.12f} "
        f"pass_a_recall_gap_from_raw={metrics.pass_a_recall_gap_from_raw:.12f} "
        f"pass_a_recall_ratio_to_raw={metrics.pass_a_recall_ratio_to_raw:.12f} "
        f"runtime_sec={metrics.runtime_sec:.3f} "
        f"question_count={metrics.question_count}"
    )


def _validate_recall_alignment(
    *,
    metrics: GroundingRunMetrics,
    max_pass_a_recall_gap: float | None,
    min_pass_a_recall_ratio: float | None,
) -> None:
    """Enforce optional recall-alignment gates for pre-LLM page emission."""

    if max_pass_a_recall_gap is not None and metrics.pass_a_recall_gap_from_raw > max_pass_a_recall_gap:
        raise RuntimeError(
            "Pre-LLM recall alignment gate failed: "
            f"pass_a_recall_gap_from_raw={metrics.pass_a_recall_gap_from_raw:.12f} "
            f"> max_pass_a_recall_gap={max_pass_a_recall_gap:.12f}."
        )
    if min_pass_a_recall_ratio is not None and metrics.pass_a_recall_ratio_to_raw < min_pass_a_recall_ratio:
        raise RuntimeError(
            "Pre-LLM recall alignment gate failed: "
            f"pass_a_recall_ratio_to_raw={metrics.pass_a_recall_ratio_to_raw:.12f} "
            f"< min_pass_a_recall_ratio={min_pass_a_recall_ratio:.12f}."
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
        raw_grounding_mean=raw_metrics.raw_grounding_mean,
        raw_precision_mean=raw_metrics.raw_precision_mean,
        raw_recall_mean=raw_metrics.raw_recall_mean,
        raw_zero_recall_count=raw_metrics.raw_zero_recall_count,
        pass_a_precision_mean=raw_metrics.pass_a_precision_mean,
        pass_a_recall_mean=raw_metrics.pass_a_recall_mean,
        pass_a_recall_gap_from_raw=raw_metrics.pass_a_recall_gap_from_raw,
        pass_a_recall_ratio_to_raw=raw_metrics.pass_a_recall_ratio_to_raw,
        runtime_sec=time.perf_counter() - started_at,
    )
    _validate_recall_alignment(
        metrics=metrics,
        max_pass_a_recall_gap=args.max_pass_a_recall_gap,
        min_pass_a_recall_ratio=args.min_pass_a_recall_ratio,
    )
    _print_summary(metrics)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
