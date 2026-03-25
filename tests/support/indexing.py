from __future__ import annotations

import json
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient

from src.common.config import AppConfig
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
from tests.support.documents import write_json, write_jsonl
from tests.support.imports import load_indexing_module


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


def indexing_config(tmp_path: Path) -> AppConfig:
    return AppConfig.model_validate(
        {
            "phase": "warmup",
            "storage": {"root_dir": str(tmp_path / "data")},
        }
    )


def phase_dir(config: AppConfig) -> Path:
    return config.storage.root_dir / config.phase.value


def corpus_dir(config: AppConfig) -> Path:
    return phase_dir(config) / config.storage.corpus_dirname


def text_block(doc_id: str, page_number: int, block_id: str, text: str) -> ContentBlock:
    return ContentBlock(
        block_id=f"{doc_id}-page-{page_number}-{block_id}",
        type=ContentBlockType.TEXT,
        text=text,
        page_number=page_number,
    )


def table_block(doc_id: str, page_number: int, table_id: str, text: str) -> ContentBlock:
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


def page_record(
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


def legal_fixture_pages() -> list[CanonicalPageRecord]:
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
        page_record(
            doc_id="alpha",
            page_number=1,
            text=definitions_text,
            blocks=[text_block("alpha", 1, "text-1", definitions_text)],
        ),
        page_record(
            doc_id="alpha",
            page_number=2,
            text=notice_text,
            blocks=[
                text_block("alpha", 2, "text-1", notice_text),
                table_block(
                    "alpha",
                    2,
                    "alpha-p2-t1",
                    "Schedule of fees. Filing fee. Type: Filing fee; Amount: USD 100",
                ),
            ],
        ),
        page_record(
            doc_id="beta",
            page_number=1,
            text=overtime_text,
            blocks=[text_block("beta", 1, "text-1", overtime_text)],
        ),
    ]


def write_corpus_inputs(config: AppConfig, *, pages: list[CanonicalPageRecord] | None = None) -> None:
    page_rows = list(legal_fixture_pages() if pages is None else pages)
    output_dir = corpus_dir(config)
    page_map_by_doc: dict[str, list[int]] = {}
    for page in page_rows:
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
        page_count=len(page_rows),
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

    write_jsonl(output_dir / config.storage.corpus_filename, page_rows)
    write_json(
        output_dir / config.storage.page_map_filename,
        [record.model_dump(mode="json") for record in page_maps],
    )
    write_json(
        output_dir / config.storage.corpus_manifest_filename,
        manifest.model_dump(mode="json"),
    )


def normalize_page_parent_map(raw_payload: Any) -> dict[str, dict[str, Any]]:
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


def entry_page_span(entry: dict[str, Any]) -> list[int]:
    for key in ("page_span", "page_numbers", "parent_page_numbers"):
        value = entry.get(key)
        if isinstance(value, list):
            return value
    raise AssertionError("page_parent_map entry must expose page_span/page_numbers/parent_page_numbers")


@contextmanager
def qdrant_client(qdrant_dir: Path) -> Iterable[QdrantClient]:
    client = QdrantClient(path=str(qdrant_dir))
    try:
        yield client
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()


def collection_name(client: QdrantClient) -> str:
    collections = client.get_collections().collections
    assert collections, "Expected at least one persisted Qdrant collection"
    assert len(collections) == 1, "W3A baseline should persist one collection for the service contract"
    return collections[0].name


def scroll_all_records(qdrant_dir: Path) -> list[Any]:
    with qdrant_client(qdrant_dir) as client:
        records, _ = client.scroll(collection_name(client), limit=512, with_payload=True, with_vectors=True)
    assert records, "Expected persisted index points"
    return records


def build_persisted_index(tmp_path: Path, monkeypatch: Any) -> Path:
    module = load_indexing_module()
    config = indexing_config(tmp_path)
    write_corpus_inputs(config)
    monkeypatch.setattr(module, "build_dense_embedder", lambda _settings: StubDenseEmbedder())
    service = module.HybridIndexService(config)
    result = service.build_indices(dry_run=False, overwrite=True)
    assert result.chunk_count and result.chunk_count > 0
    return service.paths.index_dir
