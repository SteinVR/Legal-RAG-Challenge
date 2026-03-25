from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.answering.service import extract_query_metadata
from src.common.schemas import QuestionRecord
from src.retrieval import QdrantHybridSearchBackend
from tests.support.imports import load_indexing_module
from tests.support.indexing import (
    StubDenseEmbedder,
    indexing_config,
    page_record,
    text_block,
    write_corpus_inputs,
)

pytestmark = pytest.mark.integration

def _build_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    module = load_indexing_module()
    config = indexing_config(tmp_path)
    write_corpus_inputs(
        config,
        pages=[
            page_record(
                doc_id="alpha",
                page_number=1,
                text=(
                    "Section 4 Notice. Payment must be made within 10 days after invoice. "
                    "Late payment is prohibited."
                ),
                blocks=[
                    text_block(
                        "alpha",
                        1,
                        "text-1",
                        "Section 4 Notice. Payment must be made within 10 days after invoice. "
                        "Late payment is prohibited.",
                    )
                ],
            ),
            page_record(
                doc_id="alpha",
                page_number=2,
                text=(
                    "Section 5 Extensions. Payment may be made no later than 30 days "
                    "when approved by the tribunal."
                ),
                blocks=[
                    text_block(
                        "alpha",
                        2,
                        "text-1",
                        "Section 5 Extensions. Payment may be made no later than 30 days "
                        "when approved by the tribunal.",
                    )
                ],
            ),
        ],
    )
    monkeypatch.setattr(module, "build_dense_embedder", lambda _settings: StubDenseEmbedder())
    service = module.HybridIndexService(config)
    result = service.build_indices(dry_run=False, overwrite=True)
    assert result.chunk_count and result.chunk_count > 0
    return service.paths.index_dir


def test_qdrant_hybrid_backend_retrieves_candidates_from_persisted_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index_dir = _build_index(tmp_path, monkeypatch)
    backend = QdrantHybridSearchBackend(
        index_dir=index_dir,
        dense_embedder=StubDenseEmbedder(),
    )
    question = QuestionRecord(id="q-1", question="When is payment due?", answer_type="date")

    try:
        candidates = backend.search(question, top_k=5)
    finally:
        backend.close()

    assert candidates
    assert all(candidate["chunk_id"] for candidate in candidates)
    assert all(candidate["doc_id"] == "alpha" for candidate in candidates)
    assert all(isinstance(candidate["page_span"], list) and candidate["page_span"] for candidate in candidates)
    assert all(candidate["parent_page_numbers"] == candidate["page_span"] for candidate in candidates)
    assert all(isinstance(candidate["retrieval_score"], float) for candidate in candidates)
    assert any(candidate["dense_score"] is not None for candidate in candidates)
    assert all(candidate["sparse_score"] is None for candidate in candidates)


def test_qdrant_hybrid_backend_can_enable_sparse_compat_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index_dir = _build_index(tmp_path, monkeypatch)
    backend = QdrantHybridSearchBackend(
        index_dir=index_dir,
        dense_embedder=StubDenseEmbedder(),
        enable_sparse_compat=True,
    )
    question = QuestionRecord(id="q-1b", question="When is payment due?", answer_type="date")

    try:
        candidates = backend.search(question, top_k=5)
    finally:
        backend.close()

    assert candidates
    assert any(candidate["sparse_score"] is not None for candidate in candidates)


def test_qdrant_hybrid_backend_is_restartable_with_persisted_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index_dir = _build_index(tmp_path, monkeypatch)
    question = QuestionRecord(id="q-2", question="Is payment prohibited?", answer_type="boolean")

    backend_one = QdrantHybridSearchBackend(
        index_dir=index_dir,
        dense_embedder=StubDenseEmbedder(),
    )
    first = backend_one.search(question, top_k=3)
    backend_one.close()

    backend_two = QdrantHybridSearchBackend(
        index_dir=index_dir,
        dense_embedder=StubDenseEmbedder(),
    )
    second = backend_two.search(question, top_k=3)
    backend_two.close()

    assert first
    assert second
    assert {item["chunk_id"] for item in first} == {item["chunk_id"] for item in second}


def test_qdrant_hybrid_backend_falls_back_to_dense_only_when_sparse_state_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index_dir = _build_index(tmp_path, monkeypatch)
    sparse_state_path = index_dir / "sparse_encoder_state.json"
    sparse_state_path.unlink()

    backend = QdrantHybridSearchBackend(
        index_dir=index_dir,
        dense_embedder=StubDenseEmbedder(),
    )
    question = QuestionRecord(id="q-3", question="Summarize payment terms", answer_type="free_text")

    try:
        candidates = backend.search(question, top_k=4)
    finally:
        backend.close()

    assert candidates
    assert all(candidate["sparse_score"] is None for candidate in candidates)


def test_qdrant_hybrid_backend_applies_query_metadata_as_soft_boost_without_filtering() -> None:
    class StubClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def query_points(self, **kwargs: Any) -> Any:
            self.calls.append(dict(kwargs))
            dense_hits = [
                SimpleNamespace(
                    id="beta-1",
                    score=0.34,
                    payload={
                        "chunk_id": "beta-1",
                        "doc_id": "beta",
                        "page_span": [2],
                        "chunk_type": "clause",
                        "text": "Generic contract payment terms.",
                        "document_title": "Generic Contract",
                        "entities": ["Generic Contract"],
                    },
                ),
                SimpleNamespace(
                    id="alpha-1",
                    score=0.30,
                    payload={
                        "chunk_id": "alpha-1",
                        "doc_id": "alpha",
                        "page_span": [1],
                        "chunk_type": "clause",
                        "text": "Case 012/2024 under DIFC Employment Law sets the penalty at AED 500.",
                        "document_title": "DIFC Employment Law",
                        "entities": ["DIFC Employment Law", "Case 012/2024"],
                    },
                ),
            ]
            return SimpleNamespace(points=dense_hits)

        def close(self) -> None:
            return None

    backend = QdrantHybridSearchBackend(index_dir=Path("/tmp/unused"), dense_embedder=StubDenseEmbedder())
    backend._client = StubClient()
    backend._resolved_collection_name = "test"
    backend._is_loaded = True

    question = QuestionRecord(
        id="q-meta",
        question="Under DIFC Employment Law, what is the penalty in Case 012/2024?",
        answer_type="number",
    )

    try:
        candidates = backend.search(question, top_k=2, query_metadata=extract_query_metadata(question.question))
    finally:
        backend.close()

    assert [candidate["chunk_id"] for candidate in candidates] == ["alpha-1", "beta-1"]
    assert candidates[0]["metadata_boost"] > 0.0
    assert candidates[1]["metadata_boost"] == pytest.approx(0.0)
