"""Stage smoke for indexing artifacts."""

from __future__ import annotations

from pathlib import Path

from qdrant_client import QdrantClient

import src.indexing.service as indexing_service
from src.indexing.service import HybridIndexService, IndexPaths
from src.ingestion.service import CorpusParseService
from tests.support.smoke_harness import DeterministicDenseEmbedder, prepare_synthetic_fixture, read_json


def test_indexing_smoke_builds_queryable_index_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Smoke-check build-indices by asserting real persisted index outputs."""

    fixture = prepare_synthetic_fixture(tmp_path)
    CorpusParseService(fixture.config).parse_corpus(overwrite=True)

    monkeypatch.setattr(
        indexing_service,
        "build_dense_embedder",
        lambda _settings: DeterministicDenseEmbedder(prompt_name="document"),
    )

    result = HybridIndexService(fixture.config).build_indices(overwrite=True)
    index_paths = IndexPaths.from_config(fixture.config)

    assert result.chunk_count is not None and result.chunk_count > 0
    assert index_paths.qdrant_dir.exists()
    assert index_paths.manifest_path.exists()
    assert index_paths.sparse_encoder_state_path.exists()
    assert index_paths.page_parent_map_path.exists()

    manifest = read_json(index_paths.manifest_path)
    page_parent_map = read_json(index_paths.page_parent_map_path)

    assert manifest["chunk_count"] == result.chunk_count
    assert manifest["dense_encoder"]["model_name"] == "deterministic-test-embedder"
    assert len(page_parent_map) == result.chunk_count

    client = QdrantClient(path=str(index_paths.qdrant_dir))
    try:
        collections = client.get_collections().collections
        assert len(collections) == 1
        points_count = client.get_collection(collections[0].name).points_count
        assert points_count == result.chunk_count
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()

