from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.common.config import AppConfig
from src.common.runtime_logging import configure_runtime_logging, shutdown_runtime_logging
from src.common.schemas import PageMapRecord
from tests.support.documents import write_json
from tests.support.imports import load_indexing_module
from tests.support.indexing import (
    StubDenseEmbedder,
    collection_name,
    corpus_dir,
    entry_page_span,
    indexing_config,
    legal_fixture_pages,
    normalize_page_parent_map,
    page_record,
    scroll_all_records,
    text_block,
    write_corpus_inputs,
)

pytestmark = pytest.mark.integration


@pytest.mark.slow
def test_build_indices_emits_skip_cache_runtime_event(tmp_path: Path) -> None:
    module = load_indexing_module()
    config = AppConfig.model_validate(
        {
            "phase": "warmup",
            "storage": {"root_dir": str(tmp_path / "data")},
            "logging": {"directory": str(tmp_path / "logs" / "project" / "runtime"), "console": False},
        }
    )
    write_corpus_inputs(config)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(module, "build_dense_embedder", lambda _settings: StubDenseEmbedder())
    service = module.HybridIndexService(config)
    try:
        service.build_indices(overwrite=True)

        context = configure_runtime_logging(config, command="build-indices", phase=config.phase.value)
        try:
            result = service.build_indices(overwrite=False)
        finally:
            shutdown_runtime_logging()
    finally:
        monkeypatch.undo()

    payloads = [
        json.loads(line)
        for line in context.log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert result.chunk_count is not None
    assert any(payload["event"] == "index.skip_cache" for payload in payloads)


def test_indexing_package_reexports_public_service_contract() -> None:
    package = __import__("src.indexing", fromlist=["unused"])

    assert hasattr(package, "HybridIndexService")
    assert hasattr(package, "BuildIndexResult")
    assert hasattr(package, "format_build_index_result")


def test_build_indices_requires_corpus_artifacts_before_running(tmp_path: Path) -> None:
    module = load_indexing_module()
    config = indexing_config(tmp_path)
    service = module.HybridIndexService(config)

    with pytest.raises(ValueError, match="corpus|parse-corpus|page map"):
        service.build_indices(dry_run=False, overwrite=True)


def test_build_indices_dry_run_reports_planned_outputs_without_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_indexing_module()
    config = indexing_config(tmp_path)
    write_corpus_inputs(config)
    monkeypatch.setattr(module, "build_dense_embedder", lambda _settings: StubDenseEmbedder())

    service = module.HybridIndexService(config)
    result = service.build_indices(dry_run=True)

    assert result.command == "build-indices"
    assert result.phase == "warmup"
    assert result.dry_run is True
    assert result.planned_paths
    assert not result.written_paths
    assert not result.skipped_paths
    assert not service.paths.qdrant_dir.exists()
    assert not service.paths.page_parent_map_path.exists()


def test_build_indices_persists_hybrid_index_and_exact_page_parent_map(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_indexing_module()
    config = indexing_config(tmp_path)
    write_corpus_inputs(config)
    dense_embedder = StubDenseEmbedder()
    monkeypatch.setattr(module, "build_dense_embedder", lambda _settings: dense_embedder)

    service = module.HybridIndexService(config)
    result = service.build_indices(dry_run=False, overwrite=True)

    assert result.written_paths
    assert result.indexed_document_count == 2
    assert result.indexed_page_count == 3
    assert result.chunk_count is not None and result.chunk_count > result.indexed_page_count
    assert result.manifest_path.exists()
    assert service.paths.qdrant_dir.exists()
    assert service.paths.page_parent_map_path.exists()
    assert service.paths.sparse_encoder_state_path.exists()
    assert dense_embedder.calls, "Dense embedder should be used during index construction"

    from qdrant_client import QdrantClient

    client = QdrantClient(path=str(service.paths.qdrant_dir))
    try:
        collection_info = client.get_collection(collection_name(client))
        assert "dense" in collection_info.config.params.vectors
        assert "sparse" in collection_info.config.params.sparse_vectors
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()

    manifest_payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest_payload["dense_encoder"]["model_name"] == module.DEFAULT_QWEN3_EMBEDDING_MODEL
    assert manifest_payload["sparse_encoder"]["scheme"] == "bm25_okapi"
    sparse_state_manifest = manifest_payload["sparse_encoder_state"]
    assert Path(sparse_state_manifest["path"]).name == service.paths.sparse_encoder_state_path.name
    assert isinstance(sparse_state_manifest.get("sha256"), str) and sparse_state_manifest["sha256"]
    sparse_state_payload = json.loads(service.paths.sparse_encoder_state_path.read_text(encoding="utf-8"))
    assert sparse_state_payload["term_index"]
    assert sparse_state_payload["inverse_document_frequency"]

    records = scroll_all_records(service.paths.qdrant_dir)
    assert len(records) == result.chunk_count
    chunk_types = {record.payload["chunk_type"] for record in records}
    assert {"page", "section", "clause", "microchunk", "table"} <= chunk_types
    assert "semantic-table" not in chunk_types
    assert "semantic_table" not in chunk_types

    payload_doc_pages = {
        ("alpha", 1),
        ("alpha", 2),
        ("beta", 1),
    }
    page_parent_map = normalize_page_parent_map(
        json.loads(service.paths.page_parent_map_path.read_text(encoding="utf-8"))
    )
    assert page_parent_map, "page_parent_map must contain one entry per chunk"

    for record in records:
        payload = record.payload
        assert payload["chunk_id"]
        assert payload["doc_id"]
        assert isinstance(payload["page_span"], list) and payload["page_span"]
        assert all(isinstance(page_number, int) and page_number >= 1 for page_number in payload["page_span"])
        assert payload["chunk_type"] in {"page", "section", "clause", "microchunk", "table"}
        assert "section" in payload
        assert isinstance(payload["entities"], list)
        assert isinstance(payload["dates"], list)
        assert isinstance(payload["neighboring_headings"], list)
        assert isinstance(payload["token_count"], int) and payload["token_count"] >= 1
        assert isinstance(payload["bm25_terms"], list)
        if payload["chunk_type"] in {"clause", "microchunk"}:
            assert payload.get("clause")
            assert payload["neighboring_headings"]
        assert record.vector["dense"]
        assert record.vector["sparse"].indices
        assert (payload["doc_id"], payload["page_span"][0]) in payload_doc_pages

        mapping = page_parent_map[payload["chunk_id"]]
        assert mapping["doc_id"] == payload["doc_id"]
        assert entry_page_span(mapping) == payload["page_span"]

    table_records = [record for record in records if record.payload["chunk_type"] == "table"]
    assert table_records, "Serialized table blocks must be indexed as table chunks"
    assert all(record.payload["page_span"] == [2] for record in table_records)


def test_build_indices_propagates_multi_page_section_parent_pages_into_chunk_payloads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_indexing_module()
    config = indexing_config(tmp_path)
    shared_section_page_1 = (
        "PART 2 TERMINATION\n\n"
        "Section 4 Notice\n\n"
        "4. Notice period. An employer must provide thirty calendar days of written notice before termination."
    )
    shared_section_page_2 = (
        "PART 2 TERMINATION\n\n"
        "Section 4 Notice\n\n"
        "5. Payment in lieu. The employer may make a payment in lieu of notice when the contract permits."
    )
    write_corpus_inputs(
        config,
        pages=[
            page_record(
                doc_id="alpha",
                page_number=1,
                text=shared_section_page_1,
                blocks=[text_block("alpha", 1, "text-1", shared_section_page_1)],
            ),
            page_record(
                doc_id="alpha",
                page_number=2,
                text=shared_section_page_2,
                blocks=[text_block("alpha", 2, "text-1", shared_section_page_2)],
            ),
        ],
    )
    monkeypatch.setattr(module, "build_dense_embedder", lambda _settings: StubDenseEmbedder())

    service = module.HybridIndexService(config)
    service.build_indices(dry_run=False, overwrite=True)

    records = scroll_all_records(service.paths.qdrant_dir)
    multi_page_parent_chunks = [
        record.payload
        for record in records
        if record.payload["chunk_type"] in {"page", "clause", "microchunk"}
        and record.payload["page_span"] in ([1], [2])
        and record.payload["parent_page_numbers"] == [1, 2]
    ]

    assert multi_page_parent_chunks, "Expected single-page chunks to inherit the multi-page section parent span."


def test_build_indices_skips_when_existing_index_artifacts_are_complete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_indexing_module()
    config = indexing_config(tmp_path)
    write_corpus_inputs(config)
    monkeypatch.setattr(module, "build_dense_embedder", lambda _settings: StubDenseEmbedder())

    service = module.HybridIndexService(config)
    first_result = service.build_indices(dry_run=False, overwrite=True)
    second_result = service.build_indices(dry_run=False, overwrite=False)

    assert first_result.chunk_count and first_result.chunk_count > 0
    assert not second_result.written_paths
    assert second_result.skipped_paths


def test_build_indices_rebuilds_when_page_parent_map_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_indexing_module()
    config = indexing_config(tmp_path)
    write_corpus_inputs(config)
    monkeypatch.setattr(module, "build_dense_embedder", lambda _settings: StubDenseEmbedder())

    service = module.HybridIndexService(config)
    service.build_indices(dry_run=False, overwrite=True)
    service.paths.page_parent_map_path.unlink()

    rebuilt = service.build_indices(dry_run=False, overwrite=False)

    assert rebuilt.written_paths
    assert not rebuilt.skipped_paths
    assert service.paths.page_parent_map_path.exists()


def test_build_indices_keeps_dense_index_runnable_when_sparse_compat_state_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_indexing_module()
    config = indexing_config(tmp_path)
    write_corpus_inputs(config)
    monkeypatch.setattr(module, "build_dense_embedder", lambda _settings: StubDenseEmbedder())

    service = module.HybridIndexService(config)
    service.build_indices(dry_run=False, overwrite=True)
    service.paths.sparse_encoder_state_path.unlink()

    second_result = service.build_indices(dry_run=False, overwrite=False)

    assert not second_result.written_paths
    assert second_result.skipped_paths


def test_build_indices_rebuilds_when_page_parent_map_is_unreadable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_indexing_module()
    config = indexing_config(tmp_path)
    write_corpus_inputs(config)
    monkeypatch.setattr(module, "build_dense_embedder", lambda _settings: StubDenseEmbedder())

    service = module.HybridIndexService(config)
    service.build_indices(dry_run=False, overwrite=True)
    service.paths.page_parent_map_path.write_text("{not valid json", encoding="utf-8")

    rebuilt = service.build_indices(dry_run=False, overwrite=False)

    assert rebuilt.written_paths
    assert not rebuilt.skipped_paths


def test_build_indices_rebuilds_when_page_parent_map_entry_count_mismatches_chunk_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_indexing_module()
    config = indexing_config(tmp_path)
    write_corpus_inputs(config)
    monkeypatch.setattr(module, "build_dense_embedder", lambda _settings: StubDenseEmbedder())

    service = module.HybridIndexService(config)
    service.build_indices(dry_run=False, overwrite=True)
    page_parent_map = json.loads(service.paths.page_parent_map_path.read_text(encoding="utf-8"))
    page_parent_map.pop(next(iter(page_parent_map)))
    write_json(service.paths.page_parent_map_path, page_parent_map)

    rebuilt = service.build_indices(dry_run=False, overwrite=False)

    assert rebuilt.written_paths
    assert not rebuilt.skipped_paths


def test_build_indices_rebuilds_when_source_corpus_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_indexing_module()
    config = indexing_config(tmp_path)
    write_corpus_inputs(config)
    monkeypatch.setattr(module, "build_dense_embedder", lambda _settings: StubDenseEmbedder())

    service = module.HybridIndexService(config)
    first_result = service.build_indices(dry_run=False, overwrite=True)

    gamma_text = (
        "PART 9 RECORDS\n\n"
        "Section 20 Registers\n\n"
        "20. Registers. The employer must keep a register of employee contracts, leave records, and notices."
    )
    pages = legal_fixture_pages() + [
        page_record(
            doc_id="gamma",
            page_number=1,
            text=gamma_text,
            blocks=[text_block("gamma", 1, "text-1", gamma_text)],
        )
    ]
    write_corpus_inputs(config, pages=pages)

    rebuilt = service.build_indices(dry_run=False, overwrite=False)

    assert first_result.indexed_document_count == 2
    assert rebuilt.written_paths
    assert not rebuilt.skipped_paths
    assert rebuilt.indexed_document_count == 3
    assert any(record.payload["doc_id"] == "gamma" for record in scroll_all_records(service.paths.qdrant_dir))


def test_build_indices_rejects_corpus_page_map_mismatches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_indexing_module()
    config = indexing_config(tmp_path)
    write_corpus_inputs(config)
    output_dir = corpus_dir(config)
    monkeypatch.setattr(module, "build_dense_embedder", lambda _settings: StubDenseEmbedder())

    broken_page_map = [
        PageMapRecord(
            doc_id="alpha",
            filename="alpha.pdf",
            document_title="Alpha Law",
            document_family="law_or_regulation",
            page_count=1,
            page_numbers=[1],
        ).model_dump(mode="json"),
        PageMapRecord(
            doc_id="beta",
            filename="beta.pdf",
            document_title="Beta Law",
            document_family="law_or_regulation",
            page_count=1,
            page_numbers=[1],
        ).model_dump(mode="json"),
    ]
    write_json(output_dir / config.storage.page_map_filename, broken_page_map)

    service = module.HybridIndexService(config)

    with pytest.raises(ValueError, match="page map|page_parent_map|page attribution"):
        service.build_indices(dry_run=False, overwrite=True)
