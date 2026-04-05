"""Integration smoke over the real warmup runtime (no OpenAI calls)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.answering.service import AnsweringService
from src.common.config import AppConfig, load_app_config
from src.common.schemas import QuestionRecord
from src.indexing.service import IndexPaths, build_query_embedder
from src.retrieval.hybrid_search import QdrantHybridSearchBackend, RRFHybridSearch
from src.retrieval.reranker import QwenReranker
from src.retrieval.service import RetrievalService
from src.submission.sync import PhasePaths
from tests.support.smoke_harness import NoApiProvider, normalize_compact_text


def _assert_required_path(path: Path, description: str) -> None:
    """Fail loudly when mandatory warmup runtime artifacts are missing."""

    assert path.exists(), f"{description} is required for warmup smoke test: {path}"


def _load_smoke_questions(path: Path) -> list[QuestionRecord]:
    """Load the agreed 5-question warmup smoke slice."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    return [QuestionRecord.model_validate(item) for item in payload]


def _load_gold_answers(path: Path) -> dict[str, dict[str, Any]]:
    """Load gold answers keyed by question_id for smoke assertions."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    references = payload.get("references", [])
    return {str(item["question_id"]): dict(item) for item in references}


def _assert_typed_answer_matches_gold(
    *,
    answer_type: str,
    actual: Any,
    expected: Any,
) -> None:
    """Compare typed answers against warmup gold answers with type-aware matching."""

    if answer_type == "boolean":
        assert isinstance(actual, bool)
        assert actual is bool(expected)
        return
    if answer_type == "number":
        assert float(actual) == pytest.approx(float(expected), rel=0.0, abs=1e-9)
        return
    if answer_type == "date":
        assert str(actual) == str(expected)
        return
    if answer_type == "name":
        assert normalize_compact_text(str(actual)).casefold() == normalize_compact_text(str(expected)).casefold()
        return
    raise AssertionError(f"Unexpected typed answer_type in warmup smoke: {answer_type}")


def _preflight_local_model_runtime(config: AppConfig) -> tuple[Any, QwenReranker]:
    """Hard-fail early when local embedding/reranker runtimes are unavailable."""

    query_embedder = build_query_embedder(config)
    try:
        vectors = query_embedder.encode(["warmup smoke model preflight"])
    except Exception as exc:
        raise AssertionError(
            "Warmup smoke hard-fail: local embedding runtime is unavailable. "
            "Prepare the Qwen3 embedding snapshot for offline loading before running this suite."
        ) from exc
    assert vectors and vectors[0], "Warmup smoke hard-fail: embedding preflight returned empty vectors."
    embedder_model = query_embedder._load_model()
    embedder_device = str(getattr(embedder_model, "device", "")).lower()
    assert embedder_device.startswith(
        "cuda"
    ), f"Warmup smoke hard-fail: embedding model is not on GPU (actual_device={embedder_device!r})."

    reranker = QwenReranker()
    try:
        scores = reranker.backend.score(
            "warmup smoke model preflight",
            ["This preflight passage checks local reranker availability."],
        )
    except Exception as exc:
        raise AssertionError(
            "Warmup smoke hard-fail: local reranker runtime is unavailable. "
            "Prepare the Qwen3 reranker snapshot for offline loading before running this suite."
        ) from exc
    assert scores and len(scores) == 1, "Warmup smoke hard-fail: reranker preflight returned invalid scores."
    reranker_device = str(getattr(reranker.backend, "_runtime_device", "")).lower()
    assert reranker_device.startswith(
        "cuda"
    ), f"Warmup smoke hard-fail: reranker is not on GPU (actual_device={reranker_device!r})."
    return query_embedder, reranker


@pytest.mark.integration
@pytest.mark.slow
def test_warmup_smoke_5_questions_no_openai() -> None:
    """Run the 5-question warmup smoke with local retrieval models and no OpenAI provider calls."""

    questions_path = Path("data/warmup/questions/questions_smoke.json")
    benchmark_path = Path("data/other/dev/gold/warmup100/dev-gold-warmup100-v1.benchmark.json")
    _assert_required_path(questions_path, "Smoke question slice")
    _assert_required_path(benchmark_path, "Warmup benchmark references")

    config = load_app_config(env_file=Path(".env"), phase_override="warmup")
    phase_paths = PhasePaths.from_config(config)
    index_paths = IndexPaths.from_config(config)
    _assert_required_path(phase_paths.corpus_path, "Warmup corpus artifact")
    _assert_required_path(index_paths.manifest_path, "Warmup index manifest")
    _assert_required_path(index_paths.qdrant_dir, "Warmup Qdrant directory")

    questions = _load_smoke_questions(questions_path)
    assert len(questions) == 5, "Warmup smoke must stay pinned to 5 questions."
    gold_answers = _load_gold_answers(benchmark_path)
    assert all(question.id in gold_answers for question in questions)
    query_embedder, reranker = _preflight_local_model_runtime(config)

    backend = QdrantHybridSearchBackend(
        index_dir=index_paths.index_dir,
        dense_embedder=query_embedder,
        enable_sparse_compat=True,
    )
    retrieval = RetrievalService(
        hybrid_search=RRFHybridSearch(backend=backend),
        reranker=reranker,
        candidate_budget=config.retrieval.candidate_budget,
        rerank_budget=config.retrieval.rerank_budget,
        default_evidence_budget=config.retrieval.default_evidence_budget,
        evidence_budget_by_answer_type=dict(config.retrieval.evidence_budget_by_answer_type),
        question_class_budgets=dict(config.retrieval.question_class_budgets),
        min_rerank_score=config.retrieval.min_rerank_score,
        parent_page_expansion_enabled=config.retrieval.parent_page_expansion_enabled,
        parent_page_expansion_limit=config.retrieval.parent_page_expansion_limit,
    )
    answering = AnsweringService(
        retriever=retrieval,
        provider=NoApiProvider(),
        reasoning_effort_by_type=config.answering.reasoning_effort_by_type,
        confidence_threshold_by_type=config.answering.confidence_threshold_by_type,
    )

    try:
        for question in questions:
            result = answering.answer_question(question)
            assert result.evidence_pages, f"No grounding pages emitted for question_id={question.id}"

            if question.answer_type == "free_text":
                assert isinstance(result.answer, str)
                assert result.answer.strip()
                continue

            expected = gold_answers[question.id]["answer"]
            _assert_typed_answer_matches_gold(
                answer_type=question.answer_type,
                actual=result.answer,
                expected=expected,
            )
    finally:
        backend.close()
