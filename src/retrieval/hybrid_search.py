"""Scale-safe rank-fusion hybrid search for retrieval."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from qdrant_client import QdrantClient, models

from src.common.schemas import QuestionRecord
from src.indexing.service import BM25SparseEncoder


class SearchBackend(Protocol):
    """Backend interface that yields raw retrieval candidates."""

    def search(self, question: QuestionRecord, top_k: int) -> list[dict[str, Any]]:
        """Return raw candidates for a question."""


class DenseEmbedder(Protocol):
    """Minimal dense query embedder contract used by retrieval backends."""

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode text inputs as dense vectors."""


@dataclass(slots=True)
class QdrantHybridSearchBackend:
    """Dense-first Qdrant retrieval backend over persisted W3A artifacts."""

    index_dir: Path
    dense_embedder: DenseEmbedder
    collection_name: str | None = None
    candidate_multiplier: int = 3
    enable_sparse_compat: bool = False
    _client: QdrantClient | None = field(default=None, init=False, repr=False)
    _resolved_collection_name: str | None = field(default=None, init=False, repr=False)
    _sparse_encoder: BM25SparseEncoder | None = field(default=None, init=False, repr=False)
    _is_loaded: bool = field(default=False, init=False, repr=False)

    def search(self, question: QuestionRecord, top_k: int) -> list[dict[str, Any]]:
        result_limit = max(int(top_k), 0)
        if result_limit == 0:
            return []

        self._ensure_loaded()
        assert self._client is not None
        assert self._resolved_collection_name is not None

        query_vectors = self.dense_embedder.encode([question.question])
        if len(query_vectors) != 1:
            raise ValueError("Dense embedder must return exactly one query vector.")
        dense_query = [float(value) for value in query_vectors[0]]

        dense_limit = max(result_limit * max(self.candidate_multiplier, 1), result_limit)
        dense_hits = self._client.query_points(
            collection_name=self._resolved_collection_name,
            query=dense_query,
            using="dense",
            limit=dense_limit,
            with_payload=True,
            with_vectors=False,
        ).points

        sparse_hits: list[models.ScoredPoint] = []
        if self._sparse_encoder is not None:
            sparse_hits = self._client.query_points(
                collection_name=self._resolved_collection_name,
                query=self._sparse_encoder.encode(question.question),
                using="sparse",
                limit=dense_limit,
                with_payload=True,
                with_vectors=False,
            ).points

        merged = _merge_scored_hits(dense_hits=dense_hits, sparse_hits=sparse_hits)
        merged.sort(
            key=lambda candidate: (
                -candidate["retrieval_score"],
                str(candidate["chunk_id"]),
            )
        )
        return merged[:result_limit]

    def close(self) -> None:
        if self._client is None:
            return
        close = getattr(self._client, "close", None)
        if callable(close):
            close()
        self._client = None
        self._resolved_collection_name = None
        self._sparse_encoder = None
        self._is_loaded = False

    def _ensure_loaded(self) -> None:
        if self._is_loaded:
            return

        manifest = _read_index_manifest(self.index_dir)
        self._resolved_collection_name = self.collection_name or str(manifest["collection_name"])
        qdrant_dir = self.index_dir / "qdrant"
        if not qdrant_dir.exists():
            raise ValueError(f"Qdrant index directory does not exist: {qdrant_dir}")

        self._client = QdrantClient(path=str(qdrant_dir))
        if self.enable_sparse_compat:
            sparse_state_path = _resolve_sparse_state_path(self.index_dir, manifest)
            if sparse_state_path.exists():
                sparse_state_payload = json.loads(sparse_state_path.read_text(encoding="utf-8"))
                self._sparse_encoder = BM25SparseEncoder.from_state(sparse_state_payload)
        self._is_loaded = True


@dataclass(slots=True)
class RRFHybridSearch:
    """Fuse dense and sparse rankings using reciprocal rank fusion."""

    backend: SearchBackend
    rrf_k: int = 60
    dense_weight: float = 1.0
    sparse_weight: float = 1.0

    def search(self, question: QuestionRecord, top_k: int) -> list[dict[str, Any]]:
        result_limit = max(int(top_k), 0)
        if result_limit == 0:
            return []

        raw_candidates = [dict(candidate) for candidate in self.backend.search(question, top_k=top_k)]
        if not raw_candidates:
            return []

        dense_ranks = self._rank_candidates(raw_candidates, primary_key="dense_score", fallback_key="retrieval_score")
        sparse_ranks = self._rank_candidates(raw_candidates, primary_key="sparse_score")
        ranked_candidates = [
            self._normalize_candidate(candidate, dense_ranks, sparse_ranks)
            for candidate in raw_candidates
        ]
        ranked_candidates.sort(
            key=lambda candidate: (
                -candidate["retrieval_score"],
                candidate["best_rank"],
                candidate["rank_sum"],
                candidate["chunk_id"],
            ),
        )
        return ranked_candidates[:result_limit]

    def _normalize_candidate(
        self,
        candidate: dict[str, Any],
        dense_ranks: dict[str, int],
        sparse_ranks: dict[str, int],
    ) -> dict[str, Any]:
        normalized = dict(candidate)
        chunk_id = str(candidate.get("chunk_id") or "")
        dense_rank = dense_ranks.get(chunk_id)
        sparse_rank = sparse_ranks.get(chunk_id)
        ranks = [rank for rank in (dense_rank, sparse_rank) if rank is not None]

        normalized["dense_score"] = _score(candidate.get("dense_score"), fallback=candidate.get("retrieval_score"))
        normalized["sparse_score"] = _optional_score(candidate.get("sparse_score"))
        normalized["dense_rank"] = dense_rank
        normalized["sparse_rank"] = sparse_rank
        normalized["retrieval_score"] = self._rrf_score(dense_rank, self.dense_weight) + self._rrf_score(
            sparse_rank,
            self.sparse_weight,
        )
        normalized["best_rank"] = min(ranks) if ranks else 10**9
        normalized["rank_sum"] = sum(ranks) if ranks else 10**9
        return normalized

    def _rank_candidates(
        self,
        candidates: list[dict[str, Any]],
        *,
        primary_key: str,
        fallback_key: str | None = None,
    ) -> dict[str, int]:
        scored_candidates = []
        for candidate in candidates:
            chunk_id = str(candidate.get("chunk_id") or "")
            score = _optional_score(candidate.get(primary_key))
            if score is None and fallback_key is not None:
                score = _optional_score(candidate.get(fallback_key))
            if not chunk_id or score is None:
                continue
            scored_candidates.append((chunk_id, score))

        scored_candidates.sort(key=lambda item: (-item[1], item[0]))
        return {
            chunk_id: rank
            for rank, (chunk_id, _score_value) in enumerate(scored_candidates, start=1)
        }

    def _rrf_score(self, rank: int | None, weight: float) -> float:
        if rank is None:
            return 0.0
        return float(weight) / (self.rrf_k + rank)


def _score(value: Any, *, fallback: Any = None) -> float:
    if value is None:
        value = fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _optional_score(value: Any) -> float | None:
    if value is None:
        return None
    return _score(value)


def _read_index_manifest(index_dir: Path) -> dict[str, Any]:
    manifest_path = index_dir / "index_manifest.json"
    if not manifest_path.exists():
        raise ValueError(f"Index manifest is missing: {manifest_path}")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Index manifest must be a JSON object.")
    collection_name = payload.get("collection_name")
    if not isinstance(collection_name, str) or not collection_name:
        raise ValueError("Index manifest must include a non-empty collection_name.")
    return payload


def _resolve_sparse_state_path(index_dir: Path, manifest: dict[str, Any]) -> Path:
    sparse_state = manifest.get("sparse_encoder_state")
    if isinstance(sparse_state, dict):
        state_path_raw = sparse_state.get("path")
        if isinstance(state_path_raw, str) and state_path_raw.strip():
            state_path = Path(state_path_raw)
            if state_path.is_absolute():
                return state_path
            manifest_relative_path = index_dir / state_path
            if manifest_relative_path.exists() or not state_path.exists():
                return manifest_relative_path
            if state_path.exists():
                return state_path
    return index_dir / "sparse_encoder_state.json"


def _merge_scored_hits(
    *,
    dense_hits: list[models.ScoredPoint],
    sparse_hits: list[models.ScoredPoint],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}

    for hit in dense_hits:
        payload = dict(hit.payload or {})
        chunk_id = _extract_chunk_id(payload, hit.id)
        candidate = merged.get(chunk_id)
        if candidate is None:
            candidate = _candidate_from_payload(chunk_id, payload)
            merged[chunk_id] = candidate
        candidate["dense_score"] = float(hit.score)

    for hit in sparse_hits:
        payload = dict(hit.payload or {})
        chunk_id = _extract_chunk_id(payload, hit.id)
        candidate = merged.get(chunk_id)
        if candidate is None:
            candidate = _candidate_from_payload(chunk_id, payload)
            merged[chunk_id] = candidate
        candidate["sparse_score"] = float(hit.score)

    for candidate in merged.values():
        dense_score = _optional_score(candidate.get("dense_score"))
        sparse_score = _optional_score(candidate.get("sparse_score"))
        if dense_score is None and sparse_score is None:
            candidate["retrieval_score"] = 0.0
            continue
        candidate["retrieval_score"] = (dense_score or 0.0) + (sparse_score or 0.0)

    return list(merged.values())


def _extract_chunk_id(payload: dict[str, Any], point_id: Any) -> str:
    chunk_id = str(payload.get("chunk_id") or "").strip()
    if chunk_id:
        return chunk_id
    return str(point_id)


def _candidate_from_payload(chunk_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    page_span = payload.get("page_span")
    if not isinstance(page_span, list) or not page_span:
        page_span = payload.get("page_numbers")
    if not isinstance(page_span, list):
        page_span = []

    normalized_page_span: list[int] = []
    for page_number in page_span:
        try:
            parsed = int(page_number)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            normalized_page_span.append(parsed)

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    else:
        metadata = dict(metadata)

    return {
        "chunk_id": chunk_id,
        "doc_id": str(payload.get("doc_id") or ""),
        "page_span": normalized_page_span,
        "chunk_type": str(payload.get("chunk_type") or "unknown"),
        "text": str(payload.get("text") or ""),
        "metadata": metadata,
        "dense_score": None,
        "sparse_score": None,
        "retrieval_score": 0.0,
    }
