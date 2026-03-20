"""Canonical corpus assembly for W2C."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from src.common.config import AppConfig
from src.common.schemas import (
    CanonicalPageRecord,
    ContentBlock,
    ContentBlockType,
    CorpusParseManifest,
    CorpusParseManifestRecord,
    PageMapRecord,
    ParseStatus,
    TableBlock,
)

from .pdf_parser import ParsedDocument


def build_canonical_page_records(
    document: ParsedDocument,
    table_blocks_by_page: dict[int, list[TableBlock]],
) -> list[CanonicalPageRecord]:
    """Build canonical page-level records from parsed-page results."""

    records: list[CanonicalPageRecord] = []
    for page in document.pages:
        text_blocks = _text_blocks_for_page(document.doc_id, page.page_number, page.text)
        page_tables = table_blocks_by_page.get(page.page_number, [])
        table_content_blocks = _table_content_blocks_for_page(page.page_number, page_tables)
        table_ids = list(dict.fromkeys(block.table_id for block in table_content_blocks if block.table_id))
        records.append(
            CanonicalPageRecord(
                doc_id=document.doc_id,
                page_number=page.page_number,
                document_title=page.document_title,
                document_family=page.document_family,
                triage_label=page.triage_label,
                source_mode=page.source_mode,
                parse_status=page.parse_status,
                quality_score=page.quality_score,
                quality_flags=page.quality_flags,
                text=page.text,
                blocks=[*text_blocks, *table_content_blocks],
                table_ids=table_ids,
            )
        )
    return records


def build_page_map_record(document: ParsedDocument) -> PageMapRecord:
    """Build the page map summary for one document."""

    return PageMapRecord(
        doc_id=document.doc_id,
        filename=document.filename,
        document_title=document.document_title,
        document_family=document.document_family,
        page_count=document.page_count,
        page_numbers=[page.page_number for page in document.pages],
    )


def build_manifest_record(
    document: ParsedDocument,
    *,
    parse_status: ParseStatus,
    failure_reason: str | None = None,
) -> CorpusParseManifestRecord:
    """Build the per-document parse manifest row."""

    return CorpusParseManifestRecord(
        doc_id=document.doc_id,
        filename=document.filename,
        sha256=document.sha256,
        page_count=document.page_count,
        parse_status=parse_status,
        failure_reason=failure_reason,
    )


def build_failed_manifest_record(pdf_path: str | Path, failure_reason: str) -> CorpusParseManifestRecord:
    """Build a manifest row when a document could not be parsed at all."""

    path = Path(pdf_path)
    return CorpusParseManifestRecord(
        doc_id=path.stem,
        filename=path.name,
        sha256=sha256_for_file(path),
        page_count=0,
        parse_status=ParseStatus.FAILED,
        failure_reason=failure_reason,
    )


@dataclass(slots=True)
class CorpusArtifacts:
    """Aggregate canonical corpus outputs for one parse run."""

    corpus_records: list[CanonicalPageRecord]
    page_map_records: list[PageMapRecord]
    manifest: CorpusParseManifest
    debug_markdown: dict[str, str]


def build_corpus_artifacts(
    *,
    phase: str,
    documents: list[ParsedDocument],
    serialized_tables_by_doc: dict[str, dict[int, list[TableBlock]]] | None = None,
) -> CorpusArtifacts:
    """Build all canonical corpus outputs from parsed documents."""

    corpus_records: list[CanonicalPageRecord] = []
    page_map_records: list[PageMapRecord] = []
    manifest_records: list[CorpusParseManifestRecord] = []
    debug_markdown: dict[str, str] = {}

    for document in documents:
        page_table_map = serialized_tables_by_doc.get(document.doc_id, {}) if serialized_tables_by_doc else {}
        page_records = build_canonical_page_records(document, page_table_map)
        table_blocks = _unique_table_blocks(page_table_map)
        corpus_records.extend(page_records)
        page_map_records.append(build_page_map_record(document))
        manifest_records.append(
            build_manifest_record(
                document,
                parse_status=document.parse_status,
                failure_reason=document.failure_reason,
            )
        )
        debug_markdown[document.doc_id] = render_debug_markdown(document, page_records, table_blocks)

    manifest = CorpusParseManifest(
        phase=phase,
        parsed_at=datetime.now(tz=UTC),
        document_count=len(documents),
        page_count=sum(document.page_count for document in documents),
        failed_document_count=sum(1 for document in documents if document.parse_status is ParseStatus.FAILED),
        records=manifest_records,
    )
    return CorpusArtifacts(
        corpus_records=corpus_records,
        page_map_records=page_map_records,
        manifest=manifest,
        debug_markdown=debug_markdown,
    )


def render_debug_markdown(
    document: ParsedDocument,
    page_records: list[CanonicalPageRecord],
    table_blocks: list[TableBlock],
) -> str:
    """Render a debug-friendly markdown summary for one document."""

    lines = [
        f"# {document.document_title or document.doc_id}",
        "",
        f"- doc_id: {document.doc_id}",
        f"- family: {document.document_family}",
        f"- page_count: {document.page_count}",
        f"- detected_tables: {len(table_blocks)}",
        "",
    ]

    for page_record in page_records:
        lines.extend(
            [
                f"## Page {page_record.page_number}",
                "",
                f"- triage: {page_record.triage_label.value}",
                f"- source_mode: {page_record.source_mode.value}",
                f"- parse_status: {page_record.parse_status.value}",
                f"- quality_score: {page_record.quality_score}",
                f"- quality_flags: {', '.join(page_record.quality_flags) if page_record.quality_flags else 'none'}",
                "",
                page_record.text or "_no text_",
                "",
            ]
        )

        if page_record.table_ids:
            lines.append(f"- table_ids: {', '.join(page_record.table_ids)}")
            lines.append("")

    if table_blocks:
        lines.extend(["## Tables", ""])
        for table_block in table_blocks:
            lines.extend(
                [
                    f"### {table_block.table_id}",
                    "",
                    f"- page_span: {table_block.page_span}",
                    f"- header_signature: {table_block.header_signature}",
                    "",
                    table_block.raw_markdown or "_no markdown_",
                    "",
                ]
            )
            for serialized_block in table_block.serialized_blocks:
                lines.append(f"- p{serialized_block.source_page_number}: {serialized_block.text}")
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def sha256_for_file(path: str | Path) -> str:
    """Compute the sha256 hash for a file."""

    file_path = Path(path)
    digest = sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unique_table_blocks(page_table_map: dict[int, list[TableBlock]]) -> list[TableBlock]:
    seen: set[str] = set()
    table_blocks: list[TableBlock] = []
    for page_number in sorted(page_table_map):
        for table_block in page_table_map[page_number]:
            if table_block.table_id in seen:
                continue
            seen.add(table_block.table_id)
            table_blocks.append(table_block)
    return table_blocks


def _text_blocks_for_page(doc_id: str, page_number: int, text: str) -> list[ContentBlock]:
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    if not paragraphs and text.strip():
        paragraphs = [text.strip()]

    blocks: list[ContentBlock] = []
    for block_index, paragraph in enumerate(paragraphs, start=1):
        blocks.append(
            ContentBlock(
                block_id=f"{doc_id}-page-{page_number}-text-{block_index}",
                type=ContentBlockType.TEXT,
                text=paragraph,
                page_number=page_number,
            )
        )
    return blocks


def _table_content_blocks_for_page(page_number: int, table_blocks: list[TableBlock]) -> list[ContentBlock]:
    blocks: list[ContentBlock] = []
    for table_block in table_blocks:
        for serialized_block in table_block.serialized_blocks:
            if serialized_block.source_page_number != page_number:
                continue
            blocks.append(
                ContentBlock(
                    block_id=serialized_block.block_id,
                    type=ContentBlockType.TABLE,
                    text=serialized_block.text,
                    page_number=serialized_block.source_page_number,
                    table_id=table_block.table_id,
                    metadata={
                        "row_anchor": serialized_block.row_anchor,
                        "column_context": serialized_block.column_context,
                        "table_caption": serialized_block.table_caption,
                        "source_page_number": serialized_block.source_page_number,
                    },
                )
            )
    return blocks


CorpusBuildResult = CorpusArtifacts


class CorpusBuilder:
    """Backward-compatible OO wrapper around ``build_corpus_artifacts``."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config

    def build(
        self,
        *,
        phase: str,
        documents: list[ParsedDocument],
        serialized_tables_by_doc: dict[str, dict[int, list[TableBlock]]] | None = None,
    ) -> CorpusArtifacts:
        return build_corpus_artifacts(
            phase=phase,
            documents=documents,
            serialized_tables_by_doc=serialized_tables_by_doc,
        )
