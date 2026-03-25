from __future__ import annotations

import importlib
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.answering.service import extract_query_metadata
from src.common.config import AppConfig
from src.common.schemas import (
    CanonicalPageRecord,
    ContentBlock,
    ContentBlockType,
    CorpusParseManifest,
    CorpusParseManifestRecord,
    PageMapRecord,
    ParseStatus,
    QuestionRecord,
    SourceMode,
    TriageLabel,
)
from src.retrieval import QdrantHybridSearchBackend


class StubDenseEmbedder:
    def encode(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for index, text in enumerate(texts, start=1):
            token_count = max(len(text.split()), 1)
            vectors.append([float(token_count), float(len(text)), float(index)])
        return vectors


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig.model_validate(
        {
            "phase": "warmup",
            "storage": {"root_dir": str(tmp_path / "data")},
        }
    )


def _text_block(doc_id: str, page_number: int, block_id: str, text: str) -> ContentBlock:
    return ContentBlock(
        block_id=f"{doc_id}-page-{page_number}-{block_id}",
        type=ContentBlockType.TEXT,
        text=text,
        page_number=page_number,
    )


def _page(
    *,
    doc_id: str,
    page_number: int,
    text: str,
) -> CanonicalPageRecord:
    return CanonicalPageRecord(
        doc_id=doc_id,
        page_number=page_number,
        document_title=f"{doc_id.title()} Law",
        document_family="law_or_regulation",
        triage_label=TriageLabel.NATIVE_CLEAN,
        source_mode=SourceMode.NATIVE,
        parse_status=ParseStatus.PARSED,
        quality_score=0.97,
        quality_flags=[],
        text=text,
        blocks=[_text_block(doc_id, page_number, "text-1", text)],
        table_ids=[],
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, payload: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for item in payload:
            serialized = item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            handle.write(json.dumps(serialized, ensure_ascii=False))
            handle.write("\n")


def _write_corpus_inputs(config: AppConfig) -> None:
    corpus_dir = config.storage.root_dir / config.phase.value / config.storage.corpus_dirname
    pages = [
        _page(
            doc_id="alpha",
            page_number=1,
            text=(
                "Section 4 Notice. Payment must be made within 10 days after invoice. "
                "Late payment is prohibited."
            ),
        ),
        _page(
            doc_id="alpha",
            page_number=2,
            text=(
                "Section 5 Extensions. Payment may be made no later than 30 days "
                "when approved by the tribunal."
            ),
        ),
    ]

    page_map = [
        PageMapRecord(
            doc_id="alpha",
            filename="alpha.pdf",
            document_title="Alpha Law",
            document_family="law_or_regulation",
            page_count=2,
            page_numbers=[1, 2],
        )
    ]
    manifest = CorpusParseManifest(
        phase=config.phase,
        parsed_at=datetime.now(tz=UTC),
        document_count=1,
        page_count=2,
        failed_document_count=0,
        records=[
            CorpusParseManifestRecord(
                doc_id="alpha",
                filename="alpha.pdf",
                sha256="alpha-sha",
                page_count=2,
                parse_status=ParseStatus.PARSED,
            )
        ],
    )

    _write_jsonl(corpus_dir / config.storage.corpus_filename, pages)
    _write_json(
        corpus_dir / config.storage.page_map_filename,
        [item.model_dump(mode="json") for item in page_map],
    )
    _write_json(
        corpus_dir / config.storage.corpus_manifest_filename,
        manifest.model_dump(mode="json"),
    )


def _build_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    module = importlib.import_module("src.indexing.service")
    config = _config(tmp_path)
    _write_corpus_inputs(config)
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
