"""Retrieval service contract for hybrid search, reranking, and evidence selection."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from src.common.runtime_logging import get_logger, log_event, questions_debug_enabled
from src.common.schemas import QuestionRecord
from src.evaluation.contracts import PageReference
from src.retrieval.evidence_compressor import SupportPageEvidenceCompressor
from src.retrieval.page_lifter import PageLifter, extract_physical_pages

LOGGER = get_logger("retrieval.service")


class HybridSearch(Protocol):
    """Search interface used by the retrieval service."""

    def search(self, question: QuestionRecord, top_k: int) -> list[dict[str, Any]]:
        """Return the top candidate chunks for a question."""


class Reranker(Protocol):
    """Rerank interface used by the retrieval service."""

    def rerank(
        self,
        question: QuestionRecord,
        candidates: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Return reranked chunks for a question."""


class EvidenceCompressor(Protocol):
    """Evidence compression interface used by the retrieval service."""

    def compress(
        self,
        question: QuestionRecord,
        reranked_chunks: list[dict[str, Any]],
        max_evidence: int,
    ) -> list[dict[str, Any]]:
        """Select the final evidence subset for a question."""


@dataclass(slots=True)
class RetrievedChunk:
    """Typed evidence chunk returned by the retrieval service."""

    chunk_id: str
    doc_id: str
    page_span: list[int]
    chunk_type: str
    text: str
    retrieval_score: float
    rerank_score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "RetrievedChunk":
        """Build a retrieved chunk from a retrieval-stage payload."""

        page_span = extract_physical_pages(payload)
        if not page_span:
            raise ValueError("Retrieved chunks must reference at least one positive physical page.")

        chunk_id = str(payload["chunk_id"]).strip()
        doc_id = str(payload["doc_id"]).strip()
        if not chunk_id:
            raise ValueError("Retrieved chunks must include a non-empty chunk_id.")
        if not doc_id:
            raise ValueError("Retrieved chunks must include a non-empty doc_id.")

        rerank_score_raw = payload.get("rerank_score")

        return cls(
            chunk_id=chunk_id,
            doc_id=doc_id,
            page_span=page_span,
            chunk_type=str(payload["chunk_type"]),
            text=str(payload["text"]),
            retrieval_score=float(payload["retrieval_score"]),
            rerank_score=None if rerank_score_raw is None else float(rerank_score_raw),
            metadata=dict(payload.get("metadata", {})),
        )


@dataclass(slots=True)
class RetrievalResult:
    """Final retrieval output consumed by downstream answering."""

    question_id: str
    query: str
    answer_type: str
    candidate_count: int
    reranked_count: int
    evidence_chunks: list[RetrievedChunk] = field(default_factory=list)
    retrieved_chunk_pages: list[PageReference] = field(default_factory=list)
    is_unanswerable: bool = False


@dataclass(slots=True)
class RetrievalService:
    """Coordinates search, reranking, and final evidence selection."""

    hybrid_search: HybridSearch
    reranker: Reranker
    evidence_compressor: EvidenceCompressor = field(default_factory=SupportPageEvidenceCompressor)
    candidate_budget: int = 10
    rerank_budget: int = 5
    default_evidence_budget: int = 3
    evidence_budget_by_answer_type: dict[str, int] = field(default_factory=dict)
    min_rerank_score: float = 0.0
    page_lifter: PageLifter = field(default_factory=PageLifter)

    def retrieve(self, question: QuestionRecord) -> RetrievalResult:
        """Run the retrieval pipeline for a single question."""

        candidate_budget = self._normalized_budget(self.candidate_budget)
        rerank_budget = self._normalized_budget(self.rerank_budget)

        candidates = self.hybrid_search.search(question, top_k=candidate_budget)
        candidate_window = _copy_payload_window(candidates, limit=candidate_budget)
        candidate_count = len(candidate_window)
        if candidate_count == 0:
            return self._empty_result(question=question, candidate_count=0, reranked_count=0)

        reranked = self.reranker.rerank(
            question,
            _copy_payload_window(candidate_window, limit=candidate_budget),
            top_k=rerank_budget,
        )
        reranked_window = _copy_payload_window(reranked, limit=rerank_budget)
        reranked_count = len(reranked_window)
        if reranked_count == 0:
            return self._empty_result(
                question=question,
                candidate_count=candidate_count,
                reranked_count=0,
            )

        surviving_reranked = self._apply_rerank_threshold(reranked_window)
        if not surviving_reranked:
            return self._empty_result(
                question=question,
                candidate_count=candidate_count,
                reranked_count=reranked_count,
            )

        max_evidence = self._normalized_budget(
            self.evidence_budget_by_answer_type.get(
                question.answer_type,
                self.default_evidence_budget,
            )
        )
        if max_evidence == 0:
            return self._empty_result(
                question=question,
                candidate_count=candidate_count,
                reranked_count=reranked_count,
            )

        selected_payloads = self.evidence_compressor.compress(
            question,
            [dict(item) for item in surviving_reranked],
            max_evidence=max_evidence,
        )
        evidence_chunks = self._materialize_evidence(selected_payloads[:max_evidence])
        if not evidence_chunks:
            return self._empty_result(
                question=question,
                candidate_count=candidate_count,
                reranked_count=reranked_count,
            )

        retrieved_chunk_pages = self.page_lifter.to_page_references(evidence_chunks)
        if not retrieved_chunk_pages:
            return self._empty_result(
                question=question,
                candidate_count=candidate_count,
                reranked_count=reranked_count,
            )

        result = RetrievalResult(
            question_id=question.id,
            query=question.question,
            answer_type=question.answer_type,
            candidate_count=candidate_count,
            reranked_count=reranked_count,
            evidence_chunks=evidence_chunks,
            retrieved_chunk_pages=retrieved_chunk_pages,
            is_unanswerable=False,
        )
        if questions_debug_enabled():
            log_event(
                LOGGER,
                logging.DEBUG,
                "retrieval.complete",
                "Retrieval pipeline completed for question.",
                stage="retrieval",
                question_id=question.id,
                candidate_count=result.candidate_count,
                reranked_count=result.reranked_count,
                evidence_chunk_count=len(result.evidence_chunks),
                unanswerable=result.is_unanswerable,
            )
        return result

    def _apply_rerank_threshold(self, reranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Drop reranked candidates that do not clear the configured score threshold."""

        if self.min_rerank_score <= 0:
            return [dict(item) for item in reranked]

        surviving: list[dict[str, Any]] = []
        for item in reranked:
            rerank_score = item.get("rerank_score")
            if rerank_score is None:
                continue
            if float(rerank_score) >= self.min_rerank_score:
                surviving.append(dict(item))
        return surviving

    def _materialize_evidence(self, payloads: list[dict[str, Any]]) -> list[RetrievedChunk]:
        """Convert payloads into validated evidence chunks, dropping invalid entries."""

        evidence_chunks: list[RetrievedChunk] = []
        for payload in payloads:
            try:
                evidence_chunks.append(RetrievedChunk.from_payload(payload))
            except (KeyError, TypeError, ValueError):
                continue
        return evidence_chunks

    def _empty_result(
        self,
        *,
        question: QuestionRecord,
        candidate_count: int,
        reranked_count: int,
    ) -> RetrievalResult:
        """Build an unanswerable retrieval result."""

        return RetrievalResult(
            question_id=question.id,
            query=question.question,
            answer_type=question.answer_type,
            candidate_count=candidate_count,
            reranked_count=reranked_count,
            evidence_chunks=[],
            retrieved_chunk_pages=[],
            is_unanswerable=True,
        )

    def _normalized_budget(self, budget: int) -> int:
        """Convert caller-provided budgets into safe non-negative integers."""

        return max(int(budget), 0)


def _copy_payload_window(payloads: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    """Return a defensive copy of payloads capped at the provided limit."""

    return [dict(item) for item in payloads[:limit]]
