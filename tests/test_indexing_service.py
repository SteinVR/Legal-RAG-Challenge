from __future__ import annotations

import importlib
import json
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from qdrant_client import QdrantClient

from src.common.config import AppConfig
from src.common.runtime_logging import configure_runtime_logging, shutdown_runtime_logging
from src.common.schemas import (
    CanonicalPageRecord,
    ContentBlock,
    ContentBlockType,
    CorpusParseManifest,
    CorpusParseManifestRecord,
    PageMapRecord,
    ParseStatus,
    SourceMode,
    TriageLabel,
)


class StubDenseEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def encode(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        vectors: list[list[float]] = []
        for index, text in enumerate(texts, start=1):
            token_count = max(len(text.split()), 1)
            vectors.append([float(token_count), float(len(text)), float(index)])
        return vectors


def _load_indexing_module() -> Any:
    try:
        return importlib.import_module("src.indexing.service")
    except ModuleNotFoundError as exc:
        pytest.fail(f"W3A indexing service module is missing: {exc}")


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig.model_validate(
        {
            "phase": "warmup",
            "storage": {"root_dir": str(tmp_path / "data")},
        }
    )


def _phase_dir(config: AppConfig) -> Path:
    return config.storage.root_dir / config.phase.value


def _corpus_dir(config: AppConfig) -> Path:
    return _phase_dir(config) / config.storage.corpus_dirname


def _text_block(doc_id: str, page_number: int, block_id: str, text: str) -> ContentBlock:
    return ContentBlock(
        block_id=f"{doc_id}-page-{page_number}-{block_id}",
        type=ContentBlockType.TEXT,
        text=text,
        page_number=page_number,
    )


def _table_block(doc_id: str, page_number: int, table_id: str, text: str) -> ContentBlock:
    return ContentBlock(
        block_id=f"{table_id}-row-1",
        type=ContentBlockType.TABLE,
        text=text,
        page_number=page_number,
        table_id=table_id,
        metadata={
            "row_anchor": "Filing fee",
            "column_context": ["Amount"],
            "table_caption": "Schedule of fees",
            "source_page_number": page_number,
        },
    )


def _page_record(
    *,
    doc_id: str,
    page_number: int,
    text: str,
    blocks: Iterable[ContentBlock],
) -> CanonicalPageRecord:
    block_list = list(blocks)
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
        blocks=block_list,
        table_ids=[
            block.table_id for block in block_list if block.type is ContentBlockType.TABLE and block.table_id
        ],
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _write_jsonl(path: Path, records: Iterable[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            serialized = record.model_dump(mode="json") if hasattr(record, "model_dump") else record
            handle.write(json.dumps(serialized, ensure_ascii=False))
            handle.write("\n")


def _legal_fixture_pages() -> list[CanonicalPageRecord]:
    definitions_text = (
        "PART 1 GENERAL PROVISIONS\n\n"
        "Section 1 Definitions\n\n"
        "1. Employee means any individual engaged under a contract of service with a DIFC entity. "
        "The term includes full-time staff, part-time staff, secondees, and temporary workers. "
        "This clause defines employee status for notice, leave, wages, and benefits.\n\n"
        "2. Employer means any DIFC company or branch that engages an employee under this Law."
    )
    notice_text = (
        "PART 2 TERMINATION\n\n"
        "Section 4 Notice\n\n"
        "4. Notice period. An employer must provide thirty calendar days of written notice before termination "
        "unless a longer contractual notice period applies. The employee remains entitled to wages and benefits "
        "during the notice period.\n\n"
        "5. Payment in lieu. The employer may make a payment in lieu of notice when the contract permits."
    )
    overtime_text = (
        "PART 3 WORKING TIME\n\n"
        "Section 7 Overtime\n\n"
        "7. Overtime. Employees who work beyond ordinary hours are entitled to overtime pay or time off in lieu "
        "where the contract or workplace policy requires additional compensation."
    )

    return [
        _page_record(
            doc_id="alpha",
            page_number=1,
            text=definitions_text,
            blocks=[_text_block("alpha", 1, "text-1", definitions_text)],
        ),
        _page_record(
            doc_id="alpha",
            page_number=2,
            text=notice_text,
            blocks=[
                _text_block("alpha", 2, "text-1", notice_text),
                _table_block(
                    "alpha",
                    2,
                    "alpha-p2-t1",
                    "Schedule of fees. Filing fee. Type: Filing fee; Amount: USD 100",
                ),
            ],
        ),
        _page_record(
            doc_id="beta",
            page_number=1,
            text=overtime_text,
            blocks=[_text_block("beta", 1, "text-1", overtime_text)],
        ),
    ]


def _write_corpus_inputs(config: AppConfig, *, pages: list[CanonicalPageRecord] | None = None) -> None:
    pages = list(_legal_fixture_pages() if pages is None else pages)
    corpus_dir = _corpus_dir(config)

    page_map_by_doc: dict[str, list[int]] = {}
    for page in pages:
        page_map_by_doc.setdefault(page.doc_id, []).append(page.page_number)

    page_maps = [
        PageMapRecord(
            doc_id=doc_id,
            filename=f"{doc_id}.pdf",
            document_title=f"{doc_id.title()} Law",
            document_family="law_or_regulation",
            page_count=len(page_numbers),
            page_numbers=sorted(page_numbers),
        )
        for doc_id, page_numbers in sorted(page_map_by_doc.items())
    ]

    manifest = CorpusParseManifest(
        phase=config.phase,
        parsed_at=datetime.now(tz=UTC),
        document_count=len(page_maps),
        page_count=len(pages),
        failed_document_count=0,
        records=[
            CorpusParseManifestRecord(
                doc_id=record.doc_id,
                filename=record.filename,
                sha256=f"{record.doc_id}-sha256",
                page_count=record.page_count,
                parse_status=ParseStatus.PARSED,
            )
            for record in page_maps
        ],
    )

    _write_jsonl(corpus_dir / config.storage.corpus_filename, pages)
    _write_json(
        corpus_dir / config.storage.page_map_filename,
        [record.model_dump(mode="json") for record in page_maps],
    )
    _write_json(
        corpus_dir / config.storage.corpus_manifest_filename,
        manifest.model_dump(mode="json"),
    )


def _normalize_page_parent_map(raw_payload: Any) -> dict[str, dict[str, Any]]:
    if isinstance(raw_payload, dict):
        normalized: dict[str, dict[str, Any]] = {}
        for chunk_id, raw_entry in raw_payload.items():
            if not isinstance(raw_entry, dict):
                raise AssertionError("page_parent_map values must be objects")
            entry = dict(raw_entry)
            entry.setdefault("chunk_id", chunk_id)
            normalized[chunk_id] = entry
        return normalized

    if isinstance(raw_payload, list):
        normalized: dict[str, dict[str, Any]] = {}
        for raw_entry in raw_payload:
            if not isinstance(raw_entry, dict):
                raise AssertionError("page_parent_map entries must be objects")
            chunk_id = raw_entry.get("chunk_id")
            if not isinstance(chunk_id, str) or not chunk_id:
                raise AssertionError("Each page_parent_map entry must include a non-empty chunk_id")
            normalized[chunk_id] = dict(raw_entry)
        return normalized

    raise AssertionError("page_parent_map must be a JSON object or array")


def _entry_page_span(entry: dict[str, Any]) -> list[int]:
    for key in ("page_span", "page_numbers", "parent_page_numbers"):
        value = entry.get(key)
        if isinstance(value, list):
            return value
    raise AssertionError("page_parent_map entry must expose page_span/page_numbers/parent_page_numbers")


def test_build_indices_emits_skip_cache_runtime_event(tmp_path: Path) -> None:
    module = _load_indexing_module()
    config = AppConfig.model_validate(
        {
            "phase": "warmup",
            "storage": {"root_dir": str(tmp_path / "data")},
            "logging": {"directory": str(tmp_path / "logs" / "project" / "runtime"), "console": False},
        }
    )
    _write_corpus_inputs(config)

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


@contextmanager
def _qdrant_client(qdrant_dir: Path) -> Iterable[QdrantClient]:
    client = QdrantClient(path=str(qdrant_dir))
    try:
        yield client
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()


def _collection_name(client: QdrantClient) -> str:
    collections = client.get_collections().collections
    assert collections, "Expected at least one persisted Qdrant collection"
    assert len(collections) == 1, "W3A baseline should persist one collection for the service contract"
    return collections[0].name


def _scroll_all_records(qdrant_dir: Path) -> list[Any]:
    with _qdrant_client(qdrant_dir) as client:
        records, _ = client.scroll(_collection_name(client), limit=512, with_payload=True, with_vectors=True)
    assert records, "Expected persisted index points"
    return records


def test_indexing_package_reexports_public_service_contract() -> None:
    package = importlib.import_module("src.indexing")

    assert hasattr(package, "HybridIndexService")
    assert hasattr(package, "BuildIndexResult")
    assert hasattr(package, "format_build_index_result")


def test_build_indices_requires_corpus_artifacts_before_running(tmp_path: Path) -> None:
    module = _load_indexing_module()
    config = _config(tmp_path)
    service = module.HybridIndexService(config)

    with pytest.raises(ValueError, match="corpus|parse-corpus|page map"):
        service.build_indices(dry_run=False, overwrite=True)


def test_build_indices_dry_run_reports_planned_outputs_without_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_indexing_module()
    config = _config(tmp_path)
    _write_corpus_inputs(config)
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
    module = _load_indexing_module()
    config = _config(tmp_path)
    _write_corpus_inputs(config)
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

    with _qdrant_client(service.paths.qdrant_dir) as client:
        collection_name = _collection_name(client)
        collection_info = client.get_collection(collection_name)
        assert "dense" in collection_info.config.params.vectors
        assert "sparse" in collection_info.config.params.sparse_vectors

    manifest_payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest_payload["dense_encoder"]["model_name"] == module.DEFAULT_QWEN3_EMBEDDING_MODEL
    assert manifest_payload["sparse_encoder"]["scheme"] == "bm25_okapi"
    sparse_state_manifest = manifest_payload["sparse_encoder_state"]
    assert Path(sparse_state_manifest["path"]).name == service.paths.sparse_encoder_state_path.name
    assert isinstance(sparse_state_manifest.get("sha256"), str) and sparse_state_manifest["sha256"]
    sparse_state_payload = json.loads(service.paths.sparse_encoder_state_path.read_text(encoding="utf-8"))
    assert sparse_state_payload["term_index"]
    assert sparse_state_payload["inverse_document_frequency"]

    records = _scroll_all_records(service.paths.qdrant_dir)
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
    page_parent_map = _normalize_page_parent_map(
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
        assert _entry_page_span(mapping) == payload["page_span"]

    table_records = [record for record in records if record.payload["chunk_type"] == "table"]
    assert table_records, "Serialized table blocks must be indexed as table chunks"
    assert all(record.payload["page_span"] == [2] for record in table_records)


def test_build_indices_skips_when_existing_index_artifacts_are_complete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_indexing_module()
    config = _config(tmp_path)
    _write_corpus_inputs(config)
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
    module = _load_indexing_module()
    config = _config(tmp_path)
    _write_corpus_inputs(config)
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
    module = _load_indexing_module()
    config = _config(tmp_path)
    _write_corpus_inputs(config)
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
    module = _load_indexing_module()
    config = _config(tmp_path)
    _write_corpus_inputs(config)
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
    module = _load_indexing_module()
    config = _config(tmp_path)
    _write_corpus_inputs(config)
    monkeypatch.setattr(module, "build_dense_embedder", lambda _settings: StubDenseEmbedder())

    service = module.HybridIndexService(config)
    service.build_indices(dry_run=False, overwrite=True)
    page_parent_map = json.loads(service.paths.page_parent_map_path.read_text(encoding="utf-8"))
    page_parent_map.pop(next(iter(page_parent_map)))
    _write_json(service.paths.page_parent_map_path, page_parent_map)

    rebuilt = service.build_indices(dry_run=False, overwrite=False)

    assert rebuilt.written_paths
    assert not rebuilt.skipped_paths


def test_build_indices_rebuilds_when_source_corpus_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_indexing_module()
    config = _config(tmp_path)
    _write_corpus_inputs(config)
    monkeypatch.setattr(module, "build_dense_embedder", lambda _settings: StubDenseEmbedder())

    service = module.HybridIndexService(config)
    first_result = service.build_indices(dry_run=False, overwrite=True)

    gamma_text = (
        "PART 9 RECORDS\n\n"
        "Section 20 Registers\n\n"
        "20. Registers. The employer must keep a register of employee contracts, leave records, and notices."
    )
    pages = _legal_fixture_pages() + [
        _page_record(
            doc_id="gamma",
            page_number=1,
            text=gamma_text,
            blocks=[_text_block("gamma", 1, "text-1", gamma_text)],
        )
    ]
    _write_corpus_inputs(config, pages=pages)

    rebuilt = service.build_indices(dry_run=False, overwrite=False)

    assert first_result.indexed_document_count == 2
    assert rebuilt.written_paths
    assert not rebuilt.skipped_paths
    assert rebuilt.indexed_document_count == 3
    assert any(record.payload["doc_id"] == "gamma" for record in _scroll_all_records(service.paths.qdrant_dir))


def test_build_indices_rejects_corpus_page_map_mismatches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_indexing_module()
    config = _config(tmp_path)
    _write_corpus_inputs(config)
    corpus_dir = _corpus_dir(config)
    monkeypatch.setattr(module, "build_dense_embedder", lambda _settings: StubDenseEmbedder())

    # Remove alpha page 2 from the page map while keeping it in corpus.jsonl.
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
    _write_json(corpus_dir / config.storage.page_map_filename, broken_page_map)

    service = module.HybridIndexService(config)

    with pytest.raises(ValueError, match="page map|page_parent_map|page attribution"):
        service.build_indices(dry_run=False, overwrite=True)


def test_build_index_chunks_carries_last_seen_headings_across_continuation_pages() -> None:
    module = _load_indexing_module()
    page_one_text = (
        "PART 2 TERMINATION\n\n"
        "Section 4 Notice\n\n"
        "4. Notice period. An employer must provide thirty calendar days of written notice before termination."
    )
    continuation_text = (
        "The employee remains entitled to wages and benefits during the notice period.\n\n"
        "Payment in lieu may be agreed in writing."
    )
    pages = [
        _page_record(
            doc_id="alpha",
            page_number=1,
            text=page_one_text,
            blocks=[_text_block("alpha", 1, "text-1", page_one_text)],
        ),
        _page_record(
            doc_id="alpha",
            page_number=2,
            text=continuation_text,
            blocks=[_text_block("alpha", 2, "text-1", continuation_text)],
        ),
    ]

    chunks = module.build_index_chunks(pages)
    page_one_clause = next(chunk for chunk in chunks if chunk.chunk_id == "alpha-p1-clause-1")
    page_two_clause = next(chunk for chunk in chunks if chunk.chunk_id == "alpha-p2-clause-1")

    assert page_two_clause.section == page_one_clause.section
    assert page_two_clause.neighboring_headings == page_one_clause.neighboring_headings
    assert page_two_clause.text.startswith("The employee remains entitled")


def test_build_index_chunks_preserves_legal_numbering_and_real_section_spans() -> None:
    module = _load_indexing_module()
    pages = _legal_fixture_pages()

    chunks = module.build_index_chunks(pages)
    notice_clause = next(chunk for chunk in chunks if chunk.chunk_id == "alpha-p2-clause-1")
    notice_section = next(
        chunk
        for chunk in chunks
        if chunk.chunk_type == "section" and chunk.section == "Section 4 Notice"
    )
    full_notice_page = next(chunk for chunk in chunks if chunk.chunk_id == "alpha-p2-page")

    assert notice_clause.section == "Section 4 Notice"
    assert notice_clause.neighboring_headings == ["Part 2 TERMINATION", "Section 4 Notice"]
    assert notice_section.text != full_notice_page.text
    assert not notice_section.text.startswith("PART 2 TERMINATION")


def test_build_index_chunks_preserves_first_real_paragraph_when_synthesizing_clauses() -> None:
    module = _load_indexing_module()
    text = (
        "PART 5 BENEFITS\n\n"
        "Section 12 Leave\n\n"
        "Employees are entitled to annual leave after completing probation.\n\n"
        "Unused leave may be carried over subject to employer approval."
    )
    page = _page_record(
        doc_id="gamma",
        page_number=1,
        text=text,
        blocks=[_text_block("gamma", 1, "text-1", text)],
    )

    chunks = module.build_index_chunks([page])
    clause_texts = [chunk.text for chunk in chunks if chunk.chunk_type == "clause"]
    microchunk_texts = [chunk.text for chunk in chunks if chunk.chunk_type == "microchunk"]

    assert clause_texts[0].startswith("Employees are entitled to annual leave")
    assert any(text.startswith("Employees are entitled to annual leave") for text in microchunk_texts)


def test_build_index_chunks_recognizes_article_headings_and_preserves_real_clause_labels() -> None:
    module = _load_indexing_module()
    text = (
        "ARTICLE 3 GENERAL OBLIGATIONS\n\n"
        "(a) The employer must maintain a written policy manual.\n\n"
        "(1) The manual must be accessible to employees.\n\n"
        "10A Supplemental obligations apply to branch offices."
    )
    page = _page_record(
        doc_id="delta",
        page_number=1,
        text=text,
        blocks=[_text_block("delta", 1, "text-1", text)],
    )

    chunks = module.build_index_chunks([page])
    clause_chunks = [chunk for chunk in chunks if chunk.chunk_type == "clause"]
    section_chunk = next(chunk for chunk in chunks if chunk.chunk_type == "section")

    assert [chunk.clause for chunk in clause_chunks] == ["(a)", "(1)", "10A"]
    assert all(chunk.section == "Article 3 GENERAL OBLIGATIONS" for chunk in clause_chunks)
    assert all(chunk.neighboring_headings == ["Article 3 GENERAL OBLIGATIONS"] for chunk in clause_chunks)
    assert section_chunk.section == "Article 3 GENERAL OBLIGATIONS"


def test_build_index_chunks_preserves_orphan_lead_in_before_numbered_clauses() -> None:
    module = _load_indexing_module()
    text = (
        "Section 9 Duties\n\n"
        "These duties apply to all licensed entities operating in the DIFC.\n\n"
        "(a) The entity must maintain accurate records.\n\n"
        "(1) Records must be retained for six years."
    )
    page = _page_record(
        doc_id="epsilon",
        page_number=1,
        text=text,
        blocks=[_text_block("epsilon", 1, "text-1", text)],
    )

    chunks = module.build_index_chunks([page])
    clause_chunks = [chunk for chunk in chunks if chunk.chunk_type == "clause"]
    microchunk_chunks = [chunk for chunk in chunks if chunk.chunk_type == "microchunk"]

    assert clause_chunks[0].clause == "lead-in"
    assert clause_chunks[0].text.startswith("These duties apply to all licensed entities")
    assert [chunk.clause for chunk in clause_chunks[1:]] == ["(a)", "(1)"]
    assert microchunk_chunks[0].clause == "lead-in"
    assert microchunk_chunks[0].text.startswith("These duties apply to all licensed entities")


def test_build_index_chunks_preserves_body_from_merged_heading_paragraph() -> None:
    module = _load_indexing_module()
    text = "Section 9 Duties The entity must maintain records.\n\nAdditional rules apply."
    page = _page_record(
        doc_id="zeta",
        page_number=1,
        text=text,
        blocks=[_text_block("zeta", 1, "text-1", text)],
    )

    chunks = module.build_index_chunks([page])
    clause_chunks = [chunk for chunk in chunks if chunk.chunk_type == "clause"]
    section_chunk = next(chunk for chunk in chunks if chunk.chunk_type == "section")

    assert clause_chunks[0].section == "Section 9 Duties"
    assert clause_chunks[0].text.startswith("The entity must maintain records.")
    assert all("Section 9 Duties The entity must maintain records." not in chunk.text for chunk in clause_chunks)
    assert section_chunk.section == "Section 9 Duties"
    assert section_chunk.text.startswith("The entity must maintain records.")
    assert not section_chunk.text.startswith("Section 9 Duties")


def test_split_microchunks_uses_token_budget_and_overlap_when_configured() -> None:
    module = _load_indexing_module()
    text = "Alpha beta gamma.\n\nDelta epsilon zeta.\n\nEta theta iota."

    microchunks = module._split_microchunks(
        text,
        token_chunk_size=6,
        token_chunk_overlap=3,
        token_counter=lambda value: len(value.replace(".", "").split()),
    )

    assert microchunks == [
        "Alpha beta gamma. Delta epsilon zeta.",
        "Delta epsilon zeta. Eta theta iota.",
    ]


def test_count_tokens_uses_qwen_compatible_counter_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_indexing_module()

    monkeypatch.setattr(
        module,
        "_resolve_qwen_token_counter",
        lambda: (lambda value: len(value.replace(" ", ""))),
    )

    assert module._count_tokens("Alpha beta") == len("Alphabeta")


def test_build_index_chunks_respects_enabled_chunk_families() -> None:
    module = _load_indexing_module()

    chunks = module.build_index_chunks(
        _legal_fixture_pages(),
        enabled_chunk_families={"page", "clause"},
    )

    assert chunks
    assert {chunk.chunk_type for chunk in chunks} == {"page", "clause"}


def test_build_index_chunks_preserves_w4c_structural_metadata_in_payload() -> None:
    module = _load_indexing_module()
    page = CanonicalPageRecord(
        doc_id="alpha",
        page_number=1,
        document_title="Alpha Law",
        document_family="law_or_regulation",
        triage_label=TriageLabel.NATIVE_CLEAN,
        source_mode=SourceMode.NATIVE,
        parse_status=ParseStatus.PARSED,
        quality_score=0.95,
        quality_flags=[],
        parser_provenance="opendataloader:tagged",
        heading_path=["Part 1", "Section 4"],
        block_roles=["clause"],
        source_block_ids=["h1", "c1"],
        text="Section 4 Notice. Notice must be given within 30 days.",
        blocks=[_text_block("alpha", 1, "text-1", "Section 4 Notice. Notice must be given within 30 days.")],
        table_ids=[],
    )

    chunks = module.build_index_chunks([page], enabled_chunk_families={"page"})

    assert len(chunks) == 1
    payload = chunks[0].payload()
    assert payload["parser_provenance"] == "opendataloader:tagged"
    assert payload["heading_path"] == ["Part 1", "Section 4"]
    assert payload["source_block_ids"] == ["h1", "c1"]


def test_format_build_index_result_reports_chunk_and_document_counts(tmp_path: Path) -> None:
    module = _load_indexing_module()
    manifest_path = tmp_path / "warmup" / "index_manifest.json"
    result = module.BuildIndexResult(
        command="build-indices",
        phase="warmup",
        dry_run=False,
        manifest_path=manifest_path,
        planned_paths=[tmp_path / "warmup" / "qdrant"],
        written_paths=[tmp_path / "warmup" / "qdrant"],
        indexed_document_count=2,
        indexed_page_count=3,
        chunk_count=11,
    )

    formatted = module.format_build_index_result(result)

    assert "command: build-indices" in formatted
    assert "indexed_document_count: 2" in formatted
    assert "indexed_page_count: 3" in formatted
    assert "chunk_count: 11" in formatted
