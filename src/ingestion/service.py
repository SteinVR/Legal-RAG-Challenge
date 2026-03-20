"""Phase-aware corpus parsing orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Sequence

from src.common.config import AppConfig
from src.common.schemas import (
    CanonicalPageRecord,
    CorpusParseManifest,
    CorpusParseManifestRecord,
    PageMapRecord,
    ParseStatus,
    TableBlock,
)
from src.ingestion.corpus_builder import CorpusBuilder, build_failed_manifest_record
from src.ingestion.ocr_engine import build_ocr_engine
from src.ingestion.pdf_parser import DocumentParser
from src.ingestion.table_serializer import serialize_document_tables
from src.submission.sync import PhasePaths


@dataclass(slots=True)
class CorpusPaths:
    """Resolved local filesystem layout for corpus parsing artifacts."""

    documents_dir: Path
    corpus_dir: Path
    corpus_path: Path
    page_map_path: Path
    corpus_manifest_path: Path
    debug_dir: Path

    @classmethod
    def from_config(cls, config: AppConfig) -> "CorpusPaths":
        phase_paths = PhasePaths.from_config(config)
        corpus_dir = phase_paths.phase_dir / config.storage.corpus_dirname
        return cls(
            documents_dir=phase_paths.documents_extract_dir,
            corpus_dir=corpus_dir,
            corpus_path=corpus_dir / config.storage.corpus_filename,
            page_map_path=corpus_dir / config.storage.page_map_filename,
            corpus_manifest_path=corpus_dir / config.storage.corpus_manifest_filename,
            debug_dir=corpus_dir / config.storage.debug_dirname,
        )

    def ensure_directories(self) -> None:
        self.corpus_dir.mkdir(parents=True, exist_ok=True)
        self.debug_dir.mkdir(parents=True, exist_ok=True)


@dataclass(slots=True)
class ParseCorpusResult:
    """User-facing summary for parse-corpus CLI actions."""

    command: str
    phase: str
    dry_run: bool
    manifest_path: Path
    planned_paths: list[Path] = field(default_factory=list)
    written_paths: list[Path] = field(default_factory=list)
    skipped_paths: list[Path] = field(default_factory=list)
    parsed_document_count: int | None = None
    parsed_page_count: int | None = None
    failed_document_count: int | None = None


class CorpusParseService:
    """Orchestrates phase-local PDF parsing into canonical corpus artifacts."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.paths = CorpusPaths.from_config(config)
        self.ocr_engine = build_ocr_engine(config.ingestion)
        self.parser = DocumentParser(config, ocr_engine=self.ocr_engine)
        self.builder = CorpusBuilder(config)

    def parse_corpus(
        self,
        *,
        dry_run: bool = False,
        overwrite: bool | None = None,
        doc_ids: Sequence[str] | None = None,
    ) -> ParseCorpusResult:
        overwrite = self.config.download.overwrite if overwrite is None else overwrite
        planned_paths = self._artifact_paths()
        result = ParseCorpusResult(
            command="parse-corpus",
            phase=self.config.phase.value,
            dry_run=dry_run,
            manifest_path=self.paths.corpus_manifest_path,
            planned_paths=planned_paths,
        )
        if dry_run:
            return result

        if not self.paths.documents_dir.exists():
            raise ValueError(
                f"Documents directory does not exist: {self.paths.documents_dir}. "
                "Run sync-phase first or pass a config with extracted PDFs."
            )

        selected_doc_ids = {doc_id for doc_id in (doc_ids or []) if doc_id}
        pdf_paths = sorted(self.paths.documents_dir.rglob("*.pdf"))
        if selected_doc_ids:
            pdf_paths = [path for path in pdf_paths if path.stem in selected_doc_ids]
        if not pdf_paths:
            raise ValueError(f"No PDFs found for parsing in {self.paths.documents_dir}")

        if not overwrite and self._artifact_set_complete(selected_doc_ids):
            result.skipped_paths.extend(self._artifact_paths())
            return result

        self.paths.ensure_directories()

        successful_documents = []
        serialized_tables_by_doc: dict[str, dict[int, list[TableBlock]]] = {}
        manifest_records: list[CorpusParseManifestRecord] = []
        failed_document_count = 0

        for pdf_path in pdf_paths:
            try:
                document = self.parser.parse_document(pdf_path)
                successful_documents.append(document)
                serialized_tables_by_doc[document.doc_id] = serialize_document_tables(document)
            except Exception as exc:
                failed_document_count += 1
                manifest_records.append(build_failed_manifest_record(pdf_path, str(exc)))

        build_result = self.builder.build(
            phase=self.config.phase.value,
            documents=successful_documents,
            serialized_tables_by_doc=serialized_tables_by_doc,
        )
        page_records = list(build_result.corpus_records)
        page_map_records = list(build_result.page_map_records)
        success_manifest_records = list(build_result.manifest.records)
        debug_markdown = dict(build_result.debug_markdown)

        manifest = CorpusParseManifest(
            phase=self.config.phase,
            parsed_at=datetime.now(tz=UTC),
            document_count=len(success_manifest_records) + failed_document_count,
            page_count=len(page_records),
            failed_document_count=failed_document_count,
            records=[*success_manifest_records, *manifest_records],
        )

        self._write_jsonl(self.paths.corpus_path, page_records)
        self._write_json(self.paths.page_map_path, page_map_records)
        self._write_json(self.paths.corpus_manifest_path, manifest)
        self._write_debug_files(debug_markdown)

        result.written_paths.extend(self._artifact_paths())
        result.parsed_document_count = len(success_manifest_records)
        result.parsed_page_count = len(page_records)
        result.failed_document_count = failed_document_count
        return result

    def _artifact_paths(self) -> list[Path]:
        return [
            self.paths.corpus_path,
            self.paths.page_map_path,
            self.paths.corpus_manifest_path,
            self.paths.debug_dir,
        ]

    def _artifact_set_complete(self, selected_doc_ids: set[str]) -> bool:
        if any(not path.exists() for path in self._artifact_paths()):
            return False

        try:
            manifest = CorpusParseManifest.model_validate_json(
                self.paths.corpus_manifest_path.read_text(encoding="utf-8")
            )
        except Exception:
            return False

        manifest_doc_ids = {record.doc_id for record in manifest.records}
        if selected_doc_ids and manifest_doc_ids != selected_doc_ids:
            return False

        required_doc_ids = {
            record.doc_id
            for record in manifest.records
            if record.parse_status is not ParseStatus.FAILED
            and (not selected_doc_ids or record.doc_id in selected_doc_ids)
        }
        if selected_doc_ids and required_doc_ids != selected_doc_ids:
            return False
        return all((self.paths.debug_dir / f"{doc_id}.md").exists() for doc_id in required_doc_ids)

    def _write_jsonl(self, path: Path, records: Iterable[CanonicalPageRecord]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=False))
                handle.write("\n")

    def _write_json(self, path: Path, payload: CorpusParseManifest | list[PageMapRecord]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            if isinstance(payload, CorpusParseManifest):
                serialized = payload.model_dump(mode="json")
            else:
                serialized = [item.model_dump(mode="json") for item in payload]
            json.dump(serialized, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

    def _write_debug_files(self, debug_markdown: dict[str, str]) -> None:
        for existing_file in self.paths.debug_dir.glob("*.md"):
            existing_file.unlink()
        for doc_id, markdown in debug_markdown.items():
            target = self.paths.debug_dir / f"{doc_id}.md"
            with target.open("w", encoding="utf-8") as handle:
                handle.write(markdown)
                if not markdown.endswith("\n"):
                    handle.write("\n")


def format_parse_result(result: ParseCorpusResult) -> str:
    """Return a human-readable parse-corpus CLI summary."""

    lines = [
        f"command: {result.command}",
        f"phase: {result.phase}",
        f"dry_run: {str(result.dry_run).lower()}",
        f"manifest: {result.manifest_path}",
    ]
    if result.parsed_document_count is not None:
        lines.append(f"parsed_document_count: {result.parsed_document_count}")
    if result.parsed_page_count is not None:
        lines.append(f"parsed_page_count: {result.parsed_page_count}")
    if result.failed_document_count is not None:
        lines.append(f"failed_document_count: {result.failed_document_count}")
    if result.planned_paths:
        lines.append("planned_paths:")
        lines.extend(f"  - {path}" for path in result.planned_paths)
    if result.written_paths:
        lines.append("written_paths:")
        lines.extend(f"  - {path}" for path in result.written_paths)
    if result.skipped_paths:
        lines.append("skipped_paths:")
        lines.extend(f"  - {path}" for path in result.skipped_paths)
    return "\n".join(lines)
