"""Hybrid indexing service for canonical legal corpora."""

from __future__ import annotations

import json
import logging
import math
import re
import shutil
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models

from src.common.config import AppConfig
from src.common.runtime_logging import get_logger, log_event
from src.common.schemas import (
    CanonicalPageRecord,
    ContentBlockType,
    CorpusParseManifest,
    PageMapRecord,
)
from src.submission.sync import PhasePaths

LOGGER = get_logger("indexing.service")

DEFAULT_QWEN3_EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-0.6B"
DEFAULT_QWEN3_PROMPT_NAME = "document"
DEFAULT_EMBED_BATCH_SIZE = 16
BM25_K1 = 1.5
BM25_B = 0.75
MAX_BM25_TERMS_METADATA = 32

_SECTION_RE = re.compile(r"(?im)^(section\s+\d+[a-zA-Z0-9.-]*\s+[^\n]+)$")
_PART_RE = re.compile(r"(?im)^(part\s+\d+[a-zA-Z0-9.-]*\s+[^\n]+)$")
_ARTICLE_RE = re.compile(r"(?im)^(article\s+\d+[a-zA-Z0-9.-]*\s+[^\n]+)$")
_PARAGRAPH_CLAUSE_RE = re.compile(
    r"^(?P<label>(?:\([A-Za-z0-9]+\)|\d+[A-Za-z]?(?:[.)])?|[A-Za-z](?:[.)])))\s+(?P<body>.+)$",
    re.DOTALL,
)
_ENTITY_RE = re.compile(r"\b[A-Z][A-Za-z0-9&/-]{2,}\b")
_DATE_RE = re.compile(
    r"\b(?:\d{1,2}\s+[A-Z][a-z]+\s+\d{4}|[A-Z][a-z]+\s+\d{1,2},\s+\d{4}|\d{4}-\d{2}-\d{2})\b"
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_BODY_START_CUES = {
    "a",
    "an",
    "the",
    "this",
    "these",
    "those",
    "any",
    "each",
    "every",
    "no",
    "such",
    "additional",
    "further",
    "supplemental",
    "all",
    "if",
    "when",
    "where",
    "unless",
}
_BODY_VERBS = {"is", "are", "must", "shall", "may", "can", "will", "remains", "means", "includes"}


@dataclass(slots=True)
class IndexPaths:
    """Resolved filesystem layout for indexing outputs."""

    corpus_path: Path
    page_map_path: Path
    corpus_manifest_path: Path
    index_dir: Path
    qdrant_dir: Path
    page_parent_map_path: Path
    manifest_path: Path
    sparse_encoder_state_path: Path

    @classmethod
    def from_config(cls, config: AppConfig) -> "IndexPaths":
        phase_paths = PhasePaths.from_config(config)
        index_dir = phase_paths.phase_dir / "index"
        return cls(
            corpus_path=phase_paths.corpus_path,
            page_map_path=phase_paths.page_map_path,
            corpus_manifest_path=phase_paths.corpus_manifest_path,
            index_dir=index_dir,
            qdrant_dir=index_dir / "qdrant",
            page_parent_map_path=index_dir / "page_parent_map.json",
            manifest_path=index_dir / "index_manifest.json",
            sparse_encoder_state_path=index_dir / "sparse_encoder_state.json",
        )

    def ensure_directories(self) -> None:
        self.index_dir.mkdir(parents=True, exist_ok=True)


@dataclass(slots=True)
class BuildIndexResult:
    """User-facing summary for a build-indices action."""

    command: str
    phase: str
    dry_run: bool
    manifest_path: Path
    planned_paths: list[Path] = field(default_factory=list)
    written_paths: list[Path] = field(default_factory=list)
    skipped_paths: list[Path] = field(default_factory=list)
    indexed_document_count: int | None = None
    indexed_page_count: int | None = None
    chunk_count: int | None = None


@dataclass(slots=True)
class HeadingContext:
    """Rolling heading context preserved across continuation pages."""

    part_label: str | None = None
    article_label: str | None = None
    section_label_value: str | None = None

    def merged_with(self, text: str) -> "HeadingContext":
        explicit_part = _extract_part_heading(text)
        explicit_article = _extract_article_heading(text)
        explicit_section = _extract_section_heading(text)
        if explicit_part and explicit_part != self.part_label and explicit_article is None and explicit_section is None:
            return HeadingContext(part_label=explicit_part, article_label=None, section_label_value=None)
        if explicit_article and explicit_article != self.article_label and explicit_section is None:
            return HeadingContext(
                part_label=explicit_part or self.part_label,
                article_label=explicit_article,
                section_label_value=None,
            )
        return HeadingContext(
            part_label=explicit_part or self.part_label,
            article_label=explicit_article or self.article_label,
            section_label_value=explicit_section or self.section_label_value,
        )

    def neighboring_headings(self) -> list[str]:
        headings: list[str] = []
        if self.part_label:
            headings.append(self.part_label)
        if self.article_label:
            headings.append(self.article_label)
        if self.section_label_value:
            headings.append(self.section_label_value)
        return headings

    def section_label(self) -> str:
        if self.section_label_value:
            return self.section_label_value
        if self.article_label:
            return self.article_label
        if self.part_label:
            return self.part_label
        return ""


@dataclass(slots=True)
class PageChunkContext:
    """Per-page heading context used to derive truthful higher-level chunks."""

    page: CanonicalPageRecord
    headings: HeadingContext


@dataclass(slots=True)
class IndexChunk:
    """Intermediate indexing unit persisted into Qdrant."""

    chunk_id: str
    doc_id: str
    page_span: list[int]
    chunk_type: str
    text: str
    section: str
    clause: str | None
    neighboring_headings: list[str]
    entities: list[str]
    dates: list[str]
    token_count: int
    bm25_terms: list[str]
    document_title: str | None = None
    document_family: str | None = None
    parser_provenance: str | None = None
    heading_path: list[str] = field(default_factory=list)
    source_block_ids: list[str] = field(default_factory=list)
    parent_page_numbers: list[int] = field(default_factory=list)

    def payload(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "page_span": list(self.page_span),
            "parent_page_numbers": list(self.parent_page_numbers or self.page_span),
            "chunk_type": self.chunk_type,
            "text": self.text,
            "section": self.section,
            "clause": self.clause,
            "neighboring_headings": list(self.neighboring_headings),
            "entities": list(self.entities),
            "dates": list(self.dates),
            "token_count": self.token_count,
            "bm25_terms": list(self.bm25_terms),
            "document_title": self.document_title,
            "document_family": self.document_family,
            "parser_provenance": self.parser_provenance,
            "heading_path": list(self.heading_path),
            "source_block_ids": list(self.source_block_ids),
        }


class DenseEmbedder:
    """Dense embedding protocol for the indexing service."""

    model_name: str
    prompt_name: str | None
    normalize_embeddings: bool

    def encode(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class Qwen3DenseEmbedder(DenseEmbedder):
    """Local Qwen3 embedding path used by the indexing baseline."""

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_QWEN3_EMBEDDING_MODEL,
        prompt_name: str | None = DEFAULT_QWEN3_PROMPT_NAME,
        normalize_embeddings: bool = True,
        batch_size: int = DEFAULT_EMBED_BATCH_SIZE,
        local_files_only: bool = True,
    ) -> None:
        self.model_name = model_name
        self.prompt_name = prompt_name
        self.normalize_embeddings = normalize_embeddings
        self.batch_size = batch_size
        self.local_files_only = local_files_only
        self._model: Any | None = None

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        model = self._load_model()
        encode_kwargs: dict[str, Any] = {
            "batch_size": self.batch_size,
            "convert_to_numpy": True,
            "normalize_embeddings": self.normalize_embeddings,
            "show_progress_bar": False,
        }
        if self.prompt_name:
            encode_kwargs["prompt_name"] = self.prompt_name

        try:
            vectors = model.encode(texts, **encode_kwargs)
        except TypeError:
            encode_kwargs.pop("prompt_name", None)
            vectors = model.encode(texts, **encode_kwargs)

        if hasattr(vectors, "tolist"):
            return [[float(value) for value in row] for row in vectors.tolist()]
        return [[float(value) for value in row] for row in vectors]

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required to build dense indices with Qwen3-Embedding-0.6B."
            ) from exc

        try:
            self._model = SentenceTransformer(
                self.model_name,
                trust_remote_code=True,
                local_files_only=self.local_files_only,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Qwen3 embedding model '{self.model_name}' is not available locally. "
                "Pre-download it before running build-indices without a test stub."
            ) from exc
        return self._model


def build_dense_embedder(_settings: AppConfig) -> DenseEmbedder:
    """Build the dense embedder used for index construction (prompt_name='document')."""

    return Qwen3DenseEmbedder()


def build_query_embedder(_settings: AppConfig) -> DenseEmbedder:
    """Build the dense embedder used for query-time retrieval (prompt_name='query')."""

    return Qwen3DenseEmbedder(prompt_name="query")


class BM25SparseEncoder:
    """BM25 Okapi sparse encoder with retrieval-facing metadata."""

    def __init__(
        self,
        texts: list[str],
        *,
        k1: float = BM25_K1,
        b: float = BM25_B,
    ) -> None:
        self.k1 = k1
        self.b = b
        tokenized_texts = [_tokenize(text) for text in texts]
        self.document_count = len(tokenized_texts)
        self.document_lengths = [max(len(tokens), 1) for tokens in tokenized_texts]
        self.average_document_length = (
            sum(self.document_lengths) / len(self.document_lengths) if self.document_lengths else 1.0
        )

        document_frequency: Counter[str] = Counter()
        for tokens in tokenized_texts:
            document_frequency.update(set(tokens))
        if not document_frequency:
            document_frequency["_empty"] = 1

        self.term_index = {term: index for index, term in enumerate(sorted(document_frequency))}
        self.inverse_document_frequency = {
            term: math.log(1.0 + ((self.document_count - frequency + 0.5) / (frequency + 0.5)))
            for term, frequency in document_frequency.items()
        }

    def encode(self, text: str) -> models.SparseVector:
        return self.encode_tokens(_tokenize(text))

    def encode_tokens(self, tokens: list[str]) -> models.SparseVector:
        frequencies = Counter(tokens or ["_empty"])
        document_length = max(len(tokens), 1)
        weighted_terms: list[tuple[int, float]] = []

        for term, frequency in frequencies.items():
            term_id = self.term_index.get(term)
            if term_id is None:
                continue
            idf = self.inverse_document_frequency.get(term, 0.0)
            denominator = frequency + self.k1 * (
                1.0 - self.b + self.b * (document_length / self.average_document_length)
            )
            weight = idf * ((frequency * (self.k1 + 1.0)) / denominator)
            weighted_terms.append((term_id, float(weight)))

        weighted_terms.sort(key=lambda item: item[0])
        if not weighted_terms:
            weighted_terms = [(0, 0.0)]
        return models.SparseVector(
            indices=[index for index, _ in weighted_terms],
            values=[value for _, value in weighted_terms],
        )

    def metadata(self) -> dict[str, Any]:
        return {
            "scheme": "bm25_okapi",
            "tokenizer": "regex-lowercase",
            "k1": self.k1,
            "b": self.b,
            "average_document_length": self.average_document_length,
            "document_count": self.document_count,
            "vocabulary_size": len(self.term_index),
        }

    def export_state(self) -> dict[str, Any]:
        return {
            "version": 1,
            "metadata": self.metadata(),
            "term_index": dict(self.term_index),
            "inverse_document_frequency": dict(self.inverse_document_frequency),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "BM25SparseEncoder":
        metadata = state.get("metadata")
        term_index_raw = state.get("term_index")
        idf_raw = state.get("inverse_document_frequency")
        if not isinstance(metadata, Mapping):
            raise ValueError("sparse encoder state must include metadata.")
        if not isinstance(term_index_raw, Mapping) or not term_index_raw:
            raise ValueError("sparse encoder state must include term_index mapping.")
        if not isinstance(idf_raw, Mapping) or not idf_raw:
            raise ValueError("sparse encoder state must include inverse_document_frequency mapping.")

        encoder = cls.__new__(cls)
        encoder.k1 = float(metadata.get("k1", BM25_K1))
        encoder.b = float(metadata.get("b", BM25_B))
        encoder.document_count = int(metadata.get("document_count", 1))
        encoder.average_document_length = float(metadata.get("average_document_length", 1.0))
        encoder.document_lengths = [1] * max(encoder.document_count, 1)
        encoder.term_index = {str(term): int(index) for term, index in term_index_raw.items()}
        encoder.inverse_document_frequency = {
            str(term): float(weight) for term, weight in idf_raw.items() if str(term) in encoder.term_index
        }
        if not encoder.inverse_document_frequency:
            raise ValueError("sparse encoder inverse_document_frequency cannot be empty.")
        return encoder


class HybridIndexService:
    """Builds phase-local hybrid indices from canonical corpus artifacts."""

    collection_name = "legal_hybrid_index"

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.paths = IndexPaths.from_config(config)

    def build_indices(
        self,
        *,
        dry_run: bool = False,
        overwrite: bool | None = None,
    ) -> BuildIndexResult:
        overwrite = self.config.download.overwrite if overwrite is None else overwrite
        planned_paths = [*self._artifact_paths(), *self._optional_artifact_paths()]
        log_event(
            LOGGER,
            logging.INFO,
            "index.start",
            "Starting index build.",
            stage="indexing",
            dry_run=dry_run,
            overwrite=overwrite,
            corpus_path=self.paths.corpus_path,
            index_dir=self.paths.index_dir,
        )
        result = BuildIndexResult(
            command="build-indices",
            phase=self.config.phase.value,
            dry_run=dry_run,
            manifest_path=self.paths.manifest_path,
            planned_paths=planned_paths,
        )

        if dry_run:
            log_event(
                LOGGER,
                logging.INFO,
                "index.dry_run",
                "Index build dry-run completed.",
                stage="indexing",
                planned_paths=planned_paths,
            )
            return result

        corpus_pages, page_map_records, corpus_manifest = self._load_corpus_inputs()
        self._validate_page_attribution(corpus_pages, page_map_records)
        source_manifest = self._build_source_manifest(corpus_pages, page_map_records, corpus_manifest)
        result.indexed_document_count = source_manifest["indexed_document_count"]
        result.indexed_page_count = source_manifest["indexed_page_count"]

        if not overwrite:
            existing_manifest = self._load_existing_manifest(source_manifest)
            if existing_manifest is not None:
                result.skipped_paths.extend(path for path in planned_paths if path.exists())
                result.chunk_count = existing_manifest.get("chunk_count")
                log_event(
                    LOGGER,
                    logging.INFO,
                    "index.skip_cache",
                    "Skipped index build because artifacts are up to date.",
                    stage="indexing",
                    chunk_count=result.chunk_count,
                    skipped_paths=result.skipped_paths,
                )
                return result

        enabled_chunk_families = set(self.config.indexing.enabled_chunk_families)
        chunks = build_index_chunks(
            corpus_pages,
            enabled_chunk_families=enabled_chunk_families,
            token_chunk_size=self.config.indexing.token_chunk_size,
            token_chunk_overlap=self.config.indexing.token_chunk_overlap,
        )
        dense_embedder = build_dense_embedder(self.config)
        embedding_started_at = time.perf_counter()
        dense_vectors = dense_embedder.encode([chunk.text for chunk in chunks])
        embedding_duration_ms = round((time.perf_counter() - embedding_started_at) * 1000, 3)
        if len(dense_vectors) != len(chunks):
            raise ValueError("Dense embedder returned a mismatched number of vectors for indexing chunks.")
        sparse_encoder = BM25SparseEncoder([chunk.text for chunk in chunks])

        self.paths.ensure_directories()
        if self.paths.qdrant_dir.exists():
            shutil.rmtree(self.paths.qdrant_dir)
        self.paths.qdrant_dir.mkdir(parents=True, exist_ok=True)

        page_parent_map = self._write_qdrant_index(chunks, dense_vectors, sparse_encoder)
        manifest_payload = {
            **source_manifest,
            "command": "build-indices",
            "phase": self.config.phase.value,
            "collection_name": self.collection_name,
            "chunk_count": len(chunks),
            "built_at": datetime.now(tz=UTC).isoformat(),
            "chunking": {
                "levels": sorted(enabled_chunk_families),
                "carry_heading_context": True,
                "unnumbered_clause_strategy": "paragraph-synthesis",
                "token_chunk_size": self.config.indexing.token_chunk_size,
                "token_chunk_overlap": self.config.indexing.token_chunk_overlap,
            },
            "dense_encoder": dense_encoder_contract(dense_embedder),
            "sparse_encoder": sparse_encoder.metadata(),
            "sparse_encoder_state": {
                "path": self.paths.sparse_encoder_state_path.name,
            },
        }

        self._write_json(self.paths.page_parent_map_path, page_parent_map)
        self._write_json(self.paths.sparse_encoder_state_path, sparse_encoder.export_state())
        manifest_payload["sparse_encoder_state"]["sha256"] = _sha256_for_file(self.paths.sparse_encoder_state_path)
        self._write_json(self.paths.manifest_path, manifest_payload)

        result.written_paths.extend(planned_paths)
        result.chunk_count = len(chunks)
        log_event(
            LOGGER,
            logging.INFO,
            "index.complete",
            "Index build completed.",
            stage="indexing",
            indexed_document_count=result.indexed_document_count,
            indexed_page_count=result.indexed_page_count,
            chunk_count=result.chunk_count,
            embedding_duration_ms=embedding_duration_ms,
            dense_model=getattr(dense_embedder, "model_name", None),
            written_paths=result.written_paths,
        )
        return result

    def _artifact_paths(self) -> list[Path]:
        return [
            self.paths.qdrant_dir,
            self.paths.page_parent_map_path,
            self.paths.manifest_path,
        ]

    def _optional_artifact_paths(self) -> list[Path]:
        return [self.paths.sparse_encoder_state_path]

    def _load_corpus_inputs(
        self,
    ) -> tuple[list[CanonicalPageRecord], list[PageMapRecord], CorpusParseManifest]:
        required_paths = [
            self.paths.corpus_path,
            self.paths.page_map_path,
            self.paths.corpus_manifest_path,
        ]
        missing_paths = [path for path in required_paths if not path.exists()]
        if missing_paths:
            raise ValueError(
                "Indexing requires existing corpus artifacts before running: "
                f"missing {', '.join(str(path) for path in missing_paths)}. "
                "Run parse-corpus first."
            )

        corpus_pages: list[CanonicalPageRecord] = []
        with self.paths.corpus_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                corpus_pages.append(CanonicalPageRecord.model_validate_json(line))

        page_map_payload = json.loads(self.paths.page_map_path.read_text(encoding="utf-8"))
        page_map_records = [PageMapRecord.model_validate(record) for record in page_map_payload]
        corpus_manifest = CorpusParseManifest.model_validate_json(
            self.paths.corpus_manifest_path.read_text(encoding="utf-8")
        )
        return corpus_pages, page_map_records, corpus_manifest

    def _validate_page_attribution(
        self,
        corpus_pages: list[CanonicalPageRecord],
        page_map_records: list[PageMapRecord],
    ) -> None:
        corpus_page_numbers: dict[str, list[int]] = defaultdict(list)
        for page in corpus_pages:
            corpus_page_numbers[page.doc_id].append(page.page_number)

        page_map_by_doc = {record.doc_id: sorted(record.page_numbers) for record in page_map_records}
        corpus_by_doc = {doc_id: sorted(page_numbers) for doc_id, page_numbers in corpus_page_numbers.items()}
        if corpus_by_doc != page_map_by_doc:
            raise ValueError(
                "Corpus page attribution does not match the page map; "
                "rebuild parse-corpus inputs before build-indices."
            )

    def _build_source_manifest(
        self,
        corpus_pages: list[CanonicalPageRecord],
        page_map_records: list[PageMapRecord],
        corpus_manifest: CorpusParseManifest,
    ) -> dict[str, Any]:
        return {
            "source_artifacts": {
                "corpus_path": str(self.paths.corpus_path),
                "corpus_sha256": _sha256_for_file(self.paths.corpus_path),
                "page_map_path": str(self.paths.page_map_path),
                "page_map_sha256": _sha256_for_file(self.paths.page_map_path),
                "corpus_manifest_path": str(self.paths.corpus_manifest_path),
                "corpus_manifest_sha256": _sha256_for_file(self.paths.corpus_manifest_path),
            },
            "indexed_document_count": len(page_map_records),
            "indexed_page_count": len(corpus_pages),
            "parse_document_count": corpus_manifest.document_count,
            "parse_page_count": corpus_manifest.page_count,
        }

    def _load_existing_manifest(self, source_manifest: dict[str, Any]) -> dict[str, Any] | None:
        if any(not path.exists() for path in self._artifact_paths()):
            return None

        client: QdrantClient | None = None
        try:
            manifest_payload = json.loads(self.paths.manifest_path.read_text(encoding="utf-8"))
            if manifest_payload.get("source_artifacts") != source_manifest["source_artifacts"]:
                return None

            client = QdrantClient(path=str(self.paths.qdrant_dir))
            collections = client.get_collections().collections
            if len(collections) != 1:
                return None
            collection_name = collections[0].name
            collection_info = client.get_collection(collection_name)
            chunk_count = manifest_payload.get("chunk_count")
            if not isinstance(chunk_count, int) or chunk_count <= 0:
                return None
            if collection_info.points_count == 0:
                return None
            if collection_info.points_count != chunk_count:
                return None
            if _load_page_parent_map(path=self.paths.page_parent_map_path, expected_chunk_count=chunk_count) is None:
                return None
            return manifest_payload
        except Exception:
            return None
        finally:
            if client is not None:
                _close_client(client)

    def _write_qdrant_index(
        self,
        chunks: list[IndexChunk],
        dense_vectors: list[list[float]],
        sparse_encoder: BM25SparseEncoder,
    ) -> dict[str, dict[str, Any]]:
        if not chunks:
            raise ValueError("No index chunks were generated from the canonical corpus.")

        client = QdrantClient(path=str(self.paths.qdrant_dir))
        try:
            if client.collection_exists(self.collection_name):
                client.delete_collection(self.collection_name)
            client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "dense": models.VectorParams(
                        size=len(dense_vectors[0]),
                        distance=models.Distance.COSINE,
                    )
                },
                sparse_vectors_config={"sparse": models.SparseVectorParams()},
            )

            points: list[models.PointStruct] = []
            page_parent_map: dict[str, dict[str, Any]] = {}
            for chunk, dense_vector in zip(chunks, dense_vectors, strict=True):
                points.append(
                    models.PointStruct(
                        id=str(uuid5(NAMESPACE_URL, chunk.chunk_id)),
                        vector={
                            "dense": dense_vector,
                            "sparse": sparse_encoder.encode_tokens(_tokenize(chunk.text)),
                        },
                        payload=chunk.payload(),
                    )
                )
                page_parent_map[chunk.chunk_id] = {
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "page_span": list(chunk.page_span),
                    "page_numbers": list(chunk.page_span),
                    "parent_page_numbers": list(chunk.parent_page_numbers or chunk.page_span),
                    "chunk_type": chunk.chunk_type,
                    "section": chunk.section,
                    "clause": chunk.clause,
                    "neighboring_headings": list(chunk.neighboring_headings),
                    "parser_provenance": chunk.parser_provenance,
                    "heading_path": list(chunk.heading_path),
                    "source_block_ids": list(chunk.source_block_ids),
                }

            client.upsert(collection_name=self.collection_name, points=points, wait=True)
            return page_parent_map
        finally:
            _close_client(client)

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")


def dense_encoder_contract(embedder: DenseEmbedder | None = None) -> dict[str, Any]:
    """Return the dense-encoder contract that retrieval can rely on."""

    model_name = getattr(embedder, "model_name", DEFAULT_QWEN3_EMBEDDING_MODEL)
    prompt_name = getattr(embedder, "prompt_name", DEFAULT_QWEN3_PROMPT_NAME)
    normalize_embeddings = getattr(embedder, "normalize_embeddings", True)
    return {
        "provider": "sentence_transformers",
        "family": "qwen3_embedding",
        "model_name": model_name,
        "prompt_name": prompt_name,
        "normalize_embeddings": normalize_embeddings,
        "local_files_only": True,
    }


def build_index_chunks(
    pages: Iterable[CanonicalPageRecord],
    *,
    enabled_chunk_families: set[str] | None = None,
    token_chunk_size: int = 300,
    token_chunk_overlap: int = 50,
) -> list[IndexChunk]:
    """Derive structure-aware hybrid indexing chunks from canonical pages."""

    families = {
        str(name).strip()
        for name in (enabled_chunk_families or {"page", "section", "clause", "microchunk", "table"})
        if str(name).strip()
    }
    if not families:
        return []

    chunks: list[IndexChunk] = []
    pages_by_doc: dict[str, list[CanonicalPageRecord]] = defaultdict(list)
    for page in pages:
        pages_by_doc[page.doc_id].append(page)

    for doc_id in sorted(pages_by_doc):
        page_contexts: list[PageChunkContext] = []
        last_headings = HeadingContext()
        for page in sorted(pages_by_doc[doc_id], key=lambda item: item.page_number):
            current_headings = last_headings.merged_with(page.text)
            last_headings = current_headings
            page_contexts.append(PageChunkContext(page=page, headings=current_headings))

        parent_page_numbers_by_page = _parent_page_numbers_by_page(page_contexts)
        for page_context in page_contexts:
            page = page_context.page
            neighboring_headings = page_context.headings.neighboring_headings()
            section_title = page_context.headings.section_label()
            page_prefix = f"{page.doc_id}-p{page.page_number}"
            parent_page_numbers = parent_page_numbers_by_page.get(page.page_number, [page.page_number])

            if "page" in families:
                chunks.append(
                    _make_chunk(
                        chunk_id=f"{page_prefix}-page",
                        doc_id=page.doc_id,
                        page_span=[page.page_number],
                        parent_page_numbers=parent_page_numbers,
                        chunk_type="page",
                        text=page.text,
                        section=section_title,
                        clause=None,
                        neighboring_headings=neighboring_headings,
                        document_title=page.document_title,
                        document_family=page.document_family,
                        parser_provenance=page.parser_provenance,
                        heading_path=page.heading_path,
                        source_block_ids=page.source_block_ids,
                    )
                )

            if "clause" in families or "microchunk" in families:
                chunks.extend(
                    _clause_chunks_for_page(
                        page,
                        page_context.headings,
                        parent_page_numbers=parent_page_numbers,
                        include_clause_chunks="clause" in families,
                        include_microchunks="microchunk" in families,
                        token_chunk_size=token_chunk_size,
                        token_chunk_overlap=token_chunk_overlap,
                    )
                )

            if "table" in families:
                for table_block in page.blocks:
                    if table_block.type is not ContentBlockType.TABLE:
                        continue
                    chunks.append(
                        _make_chunk(
                            chunk_id=table_block.block_id,
                            doc_id=page.doc_id,
                            page_span=[page.page_number],
                            parent_page_numbers=parent_page_numbers,
                            chunk_type="table",
                            text=table_block.text,
                            section=section_title,
                            clause=table_block.metadata.get("row_anchor"),
                            neighboring_headings=neighboring_headings,
                            document_title=page.document_title,
                            document_family=page.document_family,
                            parser_provenance=page.parser_provenance,
                            heading_path=_heading_path_for_block(page, table_block),
                            source_block_ids=_source_block_ids_for_block(page, table_block),
                        )
                    )

        if "section" in families:
            chunks.extend(_section_chunks_for_doc(page_contexts))

    return chunks


def format_build_index_result(result: BuildIndexResult) -> str:
    """Return a human-readable build-indices summary."""

    lines = [
        f"command: {result.command}",
        f"phase: {result.phase}",
        f"dry_run: {str(result.dry_run).lower()}",
        f"manifest: {result.manifest_path}",
    ]
    if result.indexed_document_count is not None:
        lines.append(f"indexed_document_count: {result.indexed_document_count}")
    if result.indexed_page_count is not None:
        lines.append(f"indexed_page_count: {result.indexed_page_count}")
    if result.chunk_count is not None:
        lines.append(f"chunk_count: {result.chunk_count}")
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


def _clause_chunks_for_page(
    page: CanonicalPageRecord,
    headings: HeadingContext,
    *,
    parent_page_numbers: list[int],
    include_clause_chunks: bool,
    include_microchunks: bool,
    token_chunk_size: int,
    token_chunk_overlap: int,
) -> list[IndexChunk]:
    clause_sources = _clause_sources_for_text(page.text)
    chunks: list[IndexChunk] = []
    neighboring_headings = headings.neighboring_headings() or [f"Page {page.page_number}"]
    section_title = headings.section_label()

    for clause_index, (clause_label, clause_text) in enumerate(clause_sources, start=1):
        clause_name = clause_label
        clause_chunk_id = f"{page.doc_id}-p{page.page_number}-clause-{clause_index}"
        if include_clause_chunks:
            chunks.append(
                _make_chunk(
                    chunk_id=clause_chunk_id,
                    doc_id=page.doc_id,
                    page_span=[page.page_number],
                    parent_page_numbers=parent_page_numbers,
                    chunk_type="clause",
                    text=clause_text,
                    section=section_title,
                    clause=clause_name,
                    neighboring_headings=neighboring_headings,
                    document_title=page.document_title,
                    document_family=page.document_family,
                    parser_provenance=page.parser_provenance,
                    heading_path=page.heading_path,
                    source_block_ids=page.source_block_ids,
                )
            )

        if include_microchunks:
            for micro_index, micro_text in enumerate(
                _split_microchunks(
                    clause_text,
                    token_chunk_size=token_chunk_size,
                    token_chunk_overlap=token_chunk_overlap,
                ),
                start=1,
            ):
                chunks.append(
                    _make_chunk(
                        chunk_id=f"{clause_chunk_id}-micro-{micro_index}",
                        doc_id=page.doc_id,
                        page_span=[page.page_number],
                        parent_page_numbers=parent_page_numbers,
                        chunk_type="microchunk",
                        text=micro_text,
                        section=section_title,
                        clause=clause_name,
                        neighboring_headings=neighboring_headings,
                        document_title=page.document_title,
                        document_family=page.document_family,
                        parser_provenance=page.parser_provenance,
                        heading_path=page.heading_path,
                        source_block_ids=page.source_block_ids,
                    )
                )
    return chunks


def _clause_sources_for_text(text: str) -> list[tuple[str, str]]:
    paragraphs = _content_paragraphs(text)
    lead_in_parts: list[str] = []
    numbered_clauses: list[tuple[str, str]] = []
    current_label: str | None = None
    current_parts: list[str] = []

    for paragraph in paragraphs:
        match = _PARAGRAPH_CLAUSE_RE.match(paragraph)
        if match:
            if current_label is None and lead_in_parts:
                numbered_clauses.append(("lead-in", "\n\n".join(lead_in_parts).strip()))
                lead_in_parts = []
            if current_label is not None and current_parts:
                numbered_clauses.append((current_label, "\n\n".join(current_parts).strip()))
            current_label = match.group("label").strip()
            current_parts = [paragraph.strip()]
            continue

        if current_label is not None:
            current_parts.append(paragraph.strip())
        else:
            lead_in_parts.append(paragraph.strip())

    if current_label is not None and current_parts:
        numbered_clauses.append((current_label, "\n\n".join(current_parts).strip()))

    if numbered_clauses:
        return numbered_clauses

    return [
        (str(index), paragraph)
        for index, paragraph in enumerate(paragraphs, start=1)
        if paragraph.strip()
    ]


def _content_paragraphs(text: str) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    content_paragraphs: list[str] = []
    for paragraph in paragraphs:
        split_heading = _split_heading_paragraph(paragraph)
        if split_heading is None:
            content_paragraphs.append(paragraph)
            continue
        if split_heading.body_text:
            content_paragraphs.append(split_heading.body_text)
    return content_paragraphs or paragraphs


def _split_microchunks(
    text: str,
    *,
    token_chunk_size: int = 300,
    token_chunk_overlap: int = 50,
    token_counter: Callable[[str], int] | None = None,
) -> list[str]:
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]
    if not sentences:
        return [text.strip()]

    counter = token_counter or _count_tokens
    chunk_size = max(int(token_chunk_size), 1)
    overlap_target = max(int(token_chunk_overlap), 0)

    microchunks: list[str] = []
    start_index = 0
    while start_index < len(sentences):
        window: list[str] = []
        window_tokens = 0
        index = start_index
        while index < len(sentences):
            sentence = sentences[index]
            sentence_tokens = max(counter(sentence), 1)
            if window and (window_tokens + sentence_tokens) > chunk_size:
                break
            window.append(sentence)
            window_tokens += sentence_tokens
            index += 1
            if window_tokens >= chunk_size:
                break

        if not window:
            window = [sentences[start_index]]
            index = start_index + 1

        chunk = " ".join(window).strip()
        if chunk:
            microchunks.append(chunk)
        if index >= len(sentences):
            break

        overlap_tokens = 0
        overlap_count = 0
        for sentence in reversed(window):
            overlap_tokens += max(counter(sentence), 1)
            overlap_count += 1
            if overlap_tokens >= overlap_target:
                break

        next_start = index - overlap_count
        if next_start <= start_index:
            next_start = start_index + 1
        start_index = next_start

    return microchunks or [text.strip()]


def _count_tokens(text: str) -> int:
    normalized = text.strip()
    if not normalized:
        return 0
    return _resolve_qwen_token_counter()(normalized)


@lru_cache(maxsize=1)
def _resolve_qwen_token_counter() -> Callable[[str], int]:
    try:
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(
            DEFAULT_QWEN3_EMBEDDING_MODEL,
            local_files_only=True,
        )
    except Exception:
        return _fallback_token_count

    def _count_with_tokenizer(text: str) -> int:
        return len(tokenizer.encode(text, add_special_tokens=False))

    return _count_with_tokenizer


def _fallback_token_count(text: str) -> int:
    return len(_tokenize(text))


def _extract_part_heading(text: str) -> str | None:
    return _extract_heading_by_kind(text, "part")


def _extract_section_heading(text: str) -> str | None:
    return _extract_heading_by_kind(text, "section")


def _extract_article_heading(text: str) -> str | None:
    return _extract_heading_by_kind(text, "article")


def _normalize_heading_value(value: str) -> str:
    normalized = " ".join(value.split()).strip()
    tokens = normalized.split(" ", 1)
    if not tokens:
        return normalized
    if len(tokens) == 1:
        return tokens[0].title()
    return f"{tokens[0].title()} {tokens[1]}"


@dataclass(slots=True)
class SplitHeadingParagraph:
    """Heading label and optional body remainder extracted from one paragraph."""

    kind: str
    label: str
    body_text: str | None = None


def _extract_heading_by_kind(text: str, kind: str) -> str | None:
    for paragraph in [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]:
        split_heading = _split_heading_paragraph(paragraph)
        if split_heading is None or split_heading.kind != kind:
            continue
        return split_heading.label
    return None


def _split_heading_paragraph(paragraph: str) -> SplitHeadingParagraph | None:
    normalized = " ".join(paragraph.split()).strip()
    for kind, keyword in (("part", "part"), ("article", "article"), ("section", "section")):
        split_heading = _split_heading_keyword_paragraph(normalized, kind=kind, keyword=keyword)
        if split_heading is not None:
            return split_heading
    return None


def _split_heading_keyword_paragraph(
    paragraph: str,
    *,
    kind: str,
    keyword: str,
) -> SplitHeadingParagraph | None:
    match = re.match(rf"^(?P<prefix>{keyword}\s+\d+[A-Za-z0-9.-]*)\s+(?P<rest>.+)$", paragraph, flags=re.IGNORECASE)
    if not match:
        return None

    prefix = _normalize_heading_value(match.group("prefix"))
    rest_tokens = match.group("rest").split()
    if not rest_tokens:
        return SplitHeadingParagraph(kind=kind, label=prefix)

    heading_tokens: list[str] = []
    body_tokens: list[str] = []
    for index, token in enumerate(rest_tokens):
        if index > 0 and _looks_like_body_start(rest_tokens[index:]):
            body_tokens = rest_tokens[index:]
            break
        heading_tokens.append(token)

    label = prefix if not heading_tokens else _normalize_heading_value(f"{prefix} {' '.join(heading_tokens)}")
    body_text = " ".join(body_tokens).strip() or None
    return SplitHeadingParagraph(kind=kind, label=label, body_text=body_text)


def _looks_like_body_start(tokens: list[str]) -> bool:
    if not tokens:
        return False
    first = tokens[0].strip("()[]{}.,;:")
    if not first:
        return False

    lower_first = first.lower()
    if lower_first in _BODY_START_CUES:
        return True

    if len(tokens) >= 2:
        second = tokens[1].strip("()[]{}.,;:").lower()
        if second in _BODY_VERBS and first[:1].isupper() and not first.isupper():
            return True
    return False


def _section_chunks_for_doc(page_contexts: list[PageChunkContext]) -> list[IndexChunk]:
    section_chunks: list[IndexChunk] = []
    current_group: list[PageChunkContext] = []
    current_key: tuple[str, tuple[str, ...]] | None = None

    for page_context in page_contexts:
        section_label = page_context.headings.section_label()
        neighboring_headings = tuple(page_context.headings.neighboring_headings())
        if not section_label or not neighboring_headings:
            if current_group:
                section_chunks.append(_build_section_chunk(current_group, len(section_chunks) + 1))
                current_group = []
                current_key = None
            continue

        group_key = (section_label, neighboring_headings)
        if current_key is None or group_key == current_key:
            current_group.append(page_context)
            current_key = group_key
            continue

        section_chunks.append(_build_section_chunk(current_group, len(section_chunks) + 1))
        current_group = [page_context]
        current_key = group_key

    if current_group:
        section_chunks.append(_build_section_chunk(current_group, len(section_chunks) + 1))

    return section_chunks


def _parent_page_numbers_by_page(page_contexts: list[PageChunkContext]) -> dict[int, list[int]]:
    parent_pages_by_page: dict[int, list[int]] = {}
    current_group: list[PageChunkContext] = []
    current_key: tuple[str, tuple[str, ...]] | None = None

    def flush_group() -> None:
        if not current_group:
            return
        group_pages = [page_context.page.page_number for page_context in current_group]
        for page_context in current_group:
            parent_pages_by_page[page_context.page.page_number] = list(group_pages)

    for page_context in page_contexts:
        section_label = page_context.headings.section_label()
        neighboring_headings = tuple(page_context.headings.neighboring_headings())
        if not section_label or not neighboring_headings:
            flush_group()
            current_group = []
            current_key = None
            parent_pages_by_page[page_context.page.page_number] = [page_context.page.page_number]
            continue

        group_key = (section_label, neighboring_headings)
        if current_key is None or group_key == current_key:
            current_group.append(page_context)
            current_key = group_key
            continue

        flush_group()
        current_group = [page_context]
        current_key = group_key

    flush_group()
    return parent_pages_by_page


def _build_section_chunk(page_contexts: list[PageChunkContext], section_index: int) -> IndexChunk:
    first_page = page_contexts[0].page
    headings = page_contexts[0].headings
    section_text = "\n\n".join(_section_body_for_page(page_context.page) for page_context in page_contexts).strip()
    page_span = [page_context.page.page_number for page_context in page_contexts]
    return _make_chunk(
        chunk_id=f"{first_page.doc_id}-section-{section_index}",
        doc_id=first_page.doc_id,
        page_span=page_span,
        parent_page_numbers=page_span,
        chunk_type="section",
        text=section_text or "\n\n".join(page_context.page.text.strip() for page_context in page_contexts).strip(),
        section=headings.section_label(),
        clause=None,
        neighboring_headings=headings.neighboring_headings(),
        document_title=first_page.document_title,
        document_family=first_page.document_family,
        parser_provenance=first_page.parser_provenance,
        heading_path=_combined_heading_path(page_contexts),
        source_block_ids=_combined_source_block_ids(page_contexts),
    )


def _section_body_for_page(page: CanonicalPageRecord) -> str:
    return "\n\n".join(_content_paragraphs(page.text)).strip()


def _load_page_parent_map(
    path: Path,
    *,
    expected_chunk_count: int,
) -> dict[str, dict[str, Any]] | None:
    raw_payload = json.loads(path.read_text(encoding="utf-8"))
    normalized = _normalize_page_parent_map_payload(raw_payload)
    if len(normalized) != expected_chunk_count:
        return None

    for chunk_id, entry in normalized.items():
        if not isinstance(chunk_id, str) or not chunk_id:
            return None
        if not isinstance(entry.get("doc_id"), str) or not entry["doc_id"]:
            return None
        page_span = _page_span_from_entry(entry)
        if not page_span or not all(isinstance(page_number, int) and page_number >= 1 for page_number in page_span):
            return None
    return normalized


def _load_sparse_encoder_state(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        BM25SparseEncoder.from_state(payload)
    except Exception:
        return None
    return payload


def _normalize_page_parent_map_payload(raw_payload: Any) -> dict[str, dict[str, Any]]:
    if isinstance(raw_payload, dict):
        normalized: dict[str, dict[str, Any]] = {}
        for chunk_id, entry in raw_payload.items():
            if not isinstance(entry, dict):
                raise ValueError("page_parent_map values must be objects")
            normalized[chunk_id] = dict(entry)
            normalized[chunk_id].setdefault("chunk_id", chunk_id)
        return normalized

    if isinstance(raw_payload, list):
        normalized = {}
        for entry in raw_payload:
            if not isinstance(entry, dict):
                raise ValueError("page_parent_map entries must be objects")
            chunk_id = entry.get("chunk_id")
            if not isinstance(chunk_id, str) or not chunk_id:
                raise ValueError("page_parent_map entries must include a non-empty chunk_id")
            normalized[chunk_id] = dict(entry)
        return normalized

    raise ValueError("page_parent_map must be a JSON object or array")


def _page_span_from_entry(entry: dict[str, Any]) -> list[int] | None:
    for key in ("page_span", "page_numbers", "parent_page_numbers"):
        value = entry.get(key)
        if isinstance(value, list):
            return value
    return None


def _make_chunk(
    *,
    chunk_id: str,
    doc_id: str,
    page_span: list[int],
    parent_page_numbers: list[int] | None = None,
    chunk_type: str,
    text: str,
    section: str,
    clause: str | None,
    neighboring_headings: list[str],
    document_title: str | None,
    document_family: str | None,
    parser_provenance: str | None = None,
    heading_path: list[str] | None = None,
    source_block_ids: list[str] | None = None,
) -> IndexChunk:
    normalized_text = text.strip()
    tokens = _tokenize(normalized_text)
    return IndexChunk(
        chunk_id=chunk_id,
        doc_id=doc_id,
        page_span=list(page_span),
        parent_page_numbers=list(parent_page_numbers or page_span),
        chunk_type=chunk_type,
        text=normalized_text,
        section=section,
        clause=clause,
        neighboring_headings=_ordered_unique(neighboring_headings),
        entities=_extract_entities(normalized_text),
        dates=_extract_dates(normalized_text),
        token_count=len(tokens),
        bm25_terms=_ordered_unique(tokens)[:MAX_BM25_TERMS_METADATA],
        document_title=document_title,
        document_family=document_family,
        parser_provenance=parser_provenance,
        heading_path=_ordered_unique(heading_path or []),
        source_block_ids=_ordered_unique(source_block_ids or []),
    )


def _combined_heading_path(page_contexts: list[PageChunkContext]) -> list[str]:
    combined: list[str] = []
    for page_context in page_contexts:
        combined.extend(page_context.page.heading_path)
    return _ordered_unique(combined)


def _combined_source_block_ids(page_contexts: list[PageChunkContext]) -> list[str]:
    combined: list[str] = []
    for page_context in page_contexts:
        combined.extend(page_context.page.source_block_ids)
    return _ordered_unique(combined)


def _heading_path_for_block(page: CanonicalPageRecord, block: Any) -> list[str]:
    metadata = getattr(block, "metadata", None)
    if isinstance(metadata, dict):
        heading_path = metadata.get("heading_path")
        if isinstance(heading_path, list):
            return _ordered_unique(str(item).strip() for item in heading_path if str(item).strip())
    return list(page.heading_path)


def _source_block_ids_for_block(page: CanonicalPageRecord, block: Any) -> list[str]:
    metadata = getattr(block, "metadata", None)
    candidate_ids: list[str] = []
    if isinstance(metadata, dict):
        source_block_ids = metadata.get("source_block_ids")
        if isinstance(source_block_ids, list):
            candidate_ids.extend(str(item).strip() for item in source_block_ids if str(item).strip())
        source_block_id = metadata.get("source_block_id")
        if source_block_id:
            candidate_ids.append(str(source_block_id).strip())
    block_id = getattr(block, "block_id", "")
    if block_id:
        candidate_ids.append(str(block_id).strip())
    candidate_ids.extend(page.source_block_ids)
    return _ordered_unique(candidate_ids)


def _extract_entities(text: str, limit: int = 8) -> list[str]:
    entities = [match.group(0) for match in _ENTITY_RE.finditer(text)]
    return _ordered_unique(entities)[:limit]


def _extract_dates(text: str, limit: int = 6) -> list[str]:
    dates = [match.group(0) for match in _DATE_RE.finditer(text)]
    return _ordered_unique(dates)[:limit]


def _ordered_unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _sha256_for_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _close_client(client: QdrantClient) -> None:
    close = getattr(client, "close", None)
    if callable(close):
        close()
