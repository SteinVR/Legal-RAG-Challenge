from __future__ import annotations

from typing import Any

import pytest

from src.common.schemas import QuestionRecord
from src.retrieval import (
    PageLifter,
    QwenReranker,
    RRFHybridSearch,
    SupportPageEvidenceCompressor,
    extract_physical_pages,
)
from src.retrieval.reranker import LexicalFallbackReranker


def _chunk(
    chunk_id: str,
    *,
    text: str,
    doc_id: str = "alpha",
    page_span: list[int] | None = None,
    retrieval_score: float = 0.5,
    rerank_score: float | None = None,
    dense_score: float | None = None,
    sparse_score: float | None = None,
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "doc_id": doc_id,
        "page_span": list(page_span or [1]),
        "chunk_type": "clause",
        "text": text,
        "retrieval_score": retrieval_score,
        "rerank_score": rerank_score,
        "dense_score": dense_score,
        "sparse_score": sparse_score,
        "metadata": {},
    }


class StubSearchBackend:
    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = [dict(item) for item in results]
        self.calls: list[dict[str, Any]] = []

    def search(self, question: QuestionRecord, top_k: int) -> list[dict[str, Any]]:
        self.calls.append({"question": question, "top_k": top_k})
        return [dict(item) for item in self.results]


class StubQwenBackend:
    def __init__(self, scores: list[float] | None = None, *, error: Exception | None = None) -> None:
        self.scores = list(scores or [])
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def score(self, query: str, documents: list[str]) -> list[float]:
        self.calls.append({"query": query, "documents": list(documents)})
        if self.error is not None:
            raise self.error
        return list(self.scores)


def test_rrf_hybrid_search_uses_rank_fusion_not_raw_score_addition() -> None:
    question = QuestionRecord(id="q-hybrid", question="termination fee", answer_type="free_text")
    backend = StubSearchBackend(
        [
            _chunk("c1", text="dense-only spike", dense_score=1000.0, sparse_score=0.01),
            _chunk("c2", text="balanced clause", dense_score=0.8, sparse_score=0.8),
            _chunk("c3", text="sparse-leading clause", dense_score=0.7, sparse_score=0.9),
            _chunk("c4", text="weak clause", dense_score=0.2, sparse_score=0.02),
        ]
    )

    hybrid_search = RRFHybridSearch(backend=backend, rrf_k=60)
    results = hybrid_search.search(question, top_k=3)

    assert backend.calls == [{"question": question, "top_k": 3}]
    assert [item["chunk_id"] for item in results] == ["c3", "c2", "c1"]
    assert results[0]["retrieval_score"] == pytest.approx((1 / 63) + (1 / 61))
    assert results[1]["retrieval_score"] == pytest.approx((1 / 62) + (1 / 62))
    assert results[2]["retrieval_score"] == pytest.approx((1 / 61) + (1 / 64))
    assert results[0]["dense_rank"] == 3
    assert results[0]["sparse_rank"] == 1


def test_qwen_reranker_uses_backend_scores_to_order_candidates() -> None:
    question = QuestionRecord(id="q-rerank", question="What is the termination fee?", answer_type="free_text")
    backend = StubQwenBackend(scores=[0.41, 0.97, 0.16])
    reranker = QwenReranker(backend=backend)

    results = reranker.rerank(
        question,
        [
            _chunk("c1", text="The termination fee is described here.", retrieval_score=0.2),
            _chunk("c2", text="Miscellaneous clause", retrieval_score=0.1),
            _chunk("c3", text="General provisions only.", retrieval_score=0.8),
        ],
        top_k=3,
    )

    assert backend.calls == [
        {
            "query": question.question,
            "documents": [
                "The termination fee is described here.",
                "Miscellaneous clause",
                "General provisions only.",
            ],
        }
    ]
    assert [item["chunk_id"] for item in results] == ["c2", "c1", "c3"]
    assert results[0]["rerank_score"] == pytest.approx(0.97)


def test_qwen_reranker_uses_fallback_only_when_explicitly_configured() -> None:
    question = QuestionRecord(id="q-rerank-fallback", question="What is the termination fee?", answer_type="free_text")
    reranker = QwenReranker(
        backend=StubQwenBackend(error=RuntimeError("model unavailable")),
        fallback_reranker=LexicalFallbackReranker(),
    )

    results = reranker.rerank(
        question,
        [
            _chunk("strong", text="The termination fee is defined in this clause.", retrieval_score=0.2),
            _chunk("weak", text="General boilerplate only.", retrieval_score=0.9),
        ],
        top_k=2,
    )

    assert [item["chunk_id"] for item in results] == ["strong", "weak"]
    assert results[0]["rerank_score"] > results[1]["rerank_score"]


def test_page_lifter_and_compressor_ignore_invalid_pages_and_deduplicate_support() -> None:
    question = QuestionRecord(id="q-compress", question="Which pages define the fee?", answer_type="name")
    compressor = SupportPageEvidenceCompressor(max_chunks_per_page=1)
    page_lifter = PageLifter()

    chunks = [
        _chunk("alpha-1", text="fee clause", page_span=[3, 3], retrieval_score=0.6, rerank_score=0.95),
        _chunk("alpha-2", text="fee clause continued", page_span=[3, 4], retrieval_score=0.5, rerank_score=0.85),
        _chunk("invalid", text="bad page span", page_span=[0], retrieval_score=0.9, rerank_score=0.99),
    ]

    selected = compressor.compress(question, chunks, max_evidence=2)
    page_refs = page_lifter.to_page_references(selected)

    assert extract_physical_pages({"page_span": []}) == []
    assert [item["chunk_id"] for item in selected] == ["alpha-1", "alpha-2"]
    assert [item.model_dump() for item in page_refs] == [{"doc_id": "alpha", "page_numbers": [3, 4]}]
