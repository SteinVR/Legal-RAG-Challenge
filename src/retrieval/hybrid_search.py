"""Scale-safe rank-fusion hybrid search for retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from src.common.schemas import QuestionRecord


class SearchBackend(Protocol):
    """Backend interface that yields raw retrieval candidates."""

    def search(self, question: QuestionRecord, top_k: int) -> list[dict[str, Any]]:
        """Return raw candidates for a question."""


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
