"""Stage smoke for retrieval behavior."""

from __future__ import annotations

from pathlib import Path

import src.indexing.service as indexing_service
from src.common.schemas import QuestionRecord
from src.indexing.service import HybridIndexService, IndexPaths
from src.retrieval.evidence_compressor import SupportPageEvidenceCompressor
from src.ingestion.service import CorpusParseService
from src.retrieval.hybrid_search import QdrantHybridSearchBackend, RRFHybridSearch
from src.retrieval.reranker import LexicalFallbackReranker
from src.retrieval.service import RetrievalService
from tests.support.smoke_harness import DeterministicDenseEmbedder, prepare_synthetic_fixture


class CapturingHybridSearch:
    """Hybrid-search stub that captures the requested candidate budget."""

    def __init__(self) -> None:
        self.last_top_k: int | None = None

    def search(self, question: QuestionRecord, top_k: int, *, query_metadata: object | None = None) -> list[dict[str, object]]:
        """Return synthetic candidates and record the requested top_k."""

        del question, query_metadata
        self.last_top_k = top_k
        return [
            {
                "chunk_id": "law-title-page",
                "doc_id": "synthetic_law",
                "page_span": [1],
                "chunk_type": "page",
                "text": "DIFC LAW NO. 3 OF 2004",
                "retrieval_score": 1.0,
            }
        ]


class CapturingReranker:
    """Reranker stub that captures the rerank budget."""

    def __init__(self) -> None:
        self.last_top_k: int | None = None

    def rerank(
        self,
        question: QuestionRecord,
        candidates: list[dict[str, object]],
        top_k: int,
    ) -> list[dict[str, object]]:
        """Return candidates with synthetic rerank scores and record top_k."""

        del question
        self.last_top_k = top_k
        return [{**dict(candidate), "rerank_score": 1.0} for candidate in candidates[:top_k]]


def test_retrieval_smoke_returns_grounded_pages(tmp_path: Path, monkeypatch) -> None:
    """Smoke-check retrieval with real indexed artifacts and grounded output pages."""

    fixture = prepare_synthetic_fixture(tmp_path)
    CorpusParseService(fixture.config).parse_corpus(overwrite=True)

    monkeypatch.setattr(
        indexing_service,
        "build_dense_embedder",
        lambda _settings: DeterministicDenseEmbedder(prompt_name="document"),
    )
    HybridIndexService(fixture.config).build_indices(overwrite=True)
    index_paths = IndexPaths.from_config(fixture.config)

    backend = QdrantHybridSearchBackend(
        index_dir=index_paths.index_dir,
        dense_embedder=DeterministicDenseEmbedder(prompt_name="query"),
        enable_sparse_compat=True,
    )
    retrieval = RetrievalService(
        hybrid_search=RRFHybridSearch(backend=backend),
        reranker=LexicalFallbackReranker(),
        candidate_budget=8,
        rerank_budget=4,
        default_evidence_budget=2,
    )
    question = QuestionRecord(
        id="smoke-retrieval-q1",
        question="Within how many days must the notice be filed?",
        answer_type="number",
    )

    try:
        result = retrieval.retrieve(question)
    finally:
        backend.close()

    assert result.is_unanswerable is False
    assert result.evidence_chunks
    assert result.retrieved_chunk_pages
    assert any("30 days" in chunk.text for chunk in result.evidence_chunks)
    for page_ref in result.retrieved_chunk_pages:
        assert page_ref.doc_id
        assert all(page_number > 0 for page_number in page_ref.page_numbers)


def test_retrieval_smoke_boosts_candidate_budget_for_title_page_law_number() -> None:
    """Ensure title-page law-number queries use expanded candidate budget."""

    search = CapturingHybridSearch()
    reranker = CapturingReranker()
    retrieval = RetrievalService(
        hybrid_search=search,
        reranker=reranker,
        candidate_budget=8,
        rerank_budget=4,
        default_evidence_budget=2,
        evidence_budget_by_answer_type={"number": 2},
    )
    question = QuestionRecord(
        id="smoke-retrieval-title-law-number-q1",
        question="According to the title page, what is the official DIFC Law number?",
        answer_type="number",
    )

    result = retrieval.retrieve(question)

    assert search.last_top_k == 12
    assert reranker.last_top_k == 4
    assert result.evidence_chunks
    assert result.retrieved_chunk_pages


def test_retrieval_smoke_issue_date_prefers_page_chunk_over_microchunk() -> None:
    """Ensure issue-date compression prioritizes full-page chunks on the same page."""

    compressor = SupportPageEvidenceCompressor(max_chunks_per_page=1)
    question = QuestionRecord(
        id="smoke-retrieval-issue-date-priority-q1",
        question="What is the date of issue of the document in case ARB 034/2025?",
        answer_type="date",
    )
    reranked_chunks = [
        {
            "chunk_id": "doc-p1-micro-1",
            "doc_id": "doc",
            "page_span": [1],
            "chunk_type": "microchunk",
            "text": "dated 12 September 2025",
            "retrieval_score": 1.0,
            "rerank_score": 0.99,
        },
        {
            "chunk_id": "doc-p1-page",
            "doc_id": "doc",
            "page_span": [1],
            "chunk_type": "page",
            "text": "DECEMBER 19, 2025",
            "retrieval_score": 0.9,
            "rerank_score": 0.99,
        },
    ]

    selected = compressor.compress(question, reranked_chunks, max_evidence=1)

    assert selected
    assert selected[0]["chunk_id"] == "doc-p1-page"
