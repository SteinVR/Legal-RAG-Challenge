"""Stage smoke for retrieval behavior."""

from __future__ import annotations

from pathlib import Path

import src.indexing.service as indexing_service
from src.common.schemas import QuestionRecord
from src.indexing.service import HybridIndexService, IndexPaths
from src.ingestion.service import CorpusParseService
from src.retrieval.hybrid_search import QdrantHybridSearchBackend, RRFHybridSearch
from src.retrieval.reranker import LexicalFallbackReranker
from src.retrieval.service import RetrievalService
from tests.support.smoke_harness import DeterministicDenseEmbedder, prepare_synthetic_fixture


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

