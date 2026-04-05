"""Retrieval service contract for hybrid search, reranking, and evidence selection."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from src.common.runtime_logging import get_logger, log_event, questions_debug_enabled
from src.common.schemas import QuestionRecord
from src.evaluation.contracts import PageReference
from src.retrieval.evidence_compressor import SupportPageEvidenceCompressor
from src.retrieval.introspection import callable_accepts_keyword, metadata_field
from src.retrieval.page_lifter import PageLifter, extract_physical_pages

LOGGER = get_logger("retrieval.service")


class HybridSearch(Protocol):
    """Search interface used by the retrieval service."""

    def search(
        self,
        question: QuestionRecord,
        top_k: int,
        *,
        query_metadata: Any | None = None,
    ) -> list[dict[str, Any]]:
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
    diagnostics: dict[str, Any] = field(default_factory=dict)
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
    question_class_budgets: dict[str, Any] = field(default_factory=dict)
    min_rerank_score: float = 0.0
    page_lifter: PageLifter = field(default_factory=PageLifter)
    parent_page_expansion_enabled: bool = False
    parent_page_expansion_limit: int = 0

    def retrieve(
        self,
        question: QuestionRecord,
        *,
        query_metadata: Any | None = None,
    ) -> RetrievalResult:
        """Run the retrieval pipeline for a single question."""

        question_class = _derive_question_class(query_metadata)
        candidate_budget, rerank_budget, max_evidence, class_budget_applied = self._resolved_budgets(
            question=question,
            question_class=question_class,
        )
        candidates = _hybrid_search_with_optional_query_metadata(
            self.hybrid_search,
            question,
            top_k=candidate_budget,
            query_metadata=query_metadata,
        )
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

        expanded_reranked, expanded_by_chunk_id = self._expand_parent_pages(surviving_reranked)

        if max_evidence == 0:
            return self._empty_result(
                question=question,
                candidate_count=candidate_count,
                reranked_count=reranked_count,
            )

        selected_payloads_raw = self.evidence_compressor.compress(
            question,
            [dict(item) for item in expanded_reranked],
            max_evidence=max_evidence,
        )
        selected_payloads = self._apply_expansion_to_selected_payloads(
            selected_payloads_raw[:max_evidence],
            expanded_by_chunk_id,
        )
        evidence_chunks = self._materialize_evidence(selected_payloads)
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

        diagnostics: dict[str, Any] = {
            "chunk_family_participation": {
                "candidates": _chunk_family_participation(candidate_window),
                "evidence": _chunk_family_participation(selected_payloads),
            },
            "rerank_effect": {
                "applied": True,
                "candidate_count": candidate_count,
                "reranked_count": reranked_count,
            },
            "parent_page_expansion": {
                "enabled": bool(self.parent_page_expansion_enabled and self.parent_page_expansion_limit > 0),
                "applied": bool(expanded_by_chunk_id),
                "expanded_chunk_count": len(expanded_by_chunk_id),
            },
        }
        if query_metadata is not None:
            diagnostics["prefilter_usage"] = {
                "applied": _has_soft_prefilters(query_metadata),
                "question_class": question_class,
                "candidate_budget": candidate_budget,
                "rerank_budget": rerank_budget,
                "evidence_budget": max_evidence,
                "budget_source": "question_class" if class_budget_applied else "answer_type_or_default",
            }

        result = RetrievalResult(
            question_id=question.id,
            query=question.question,
            answer_type=question.answer_type,
            candidate_count=candidate_count,
            reranked_count=reranked_count,
            evidence_chunks=evidence_chunks,
            retrieved_chunk_pages=retrieved_chunk_pages,
            diagnostics=diagnostics,
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
        """Convert payloads into validated evidence chunks and fail on malformed entries."""

        evidence_chunks: list[RetrievedChunk] = []
        for index, payload in enumerate(payloads, start=1):
            try:
                evidence_chunks.append(RetrievedChunk.from_payload(payload))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"Malformed retrieval payload at position={index}; strict mode forbids silent drops."
                ) from exc
        return evidence_chunks

    def _expand_parent_pages(
        self,
        payloads: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        """Expand page spans to parent pages for the top reranked window when enabled."""

        expanded_payloads = [dict(item) for item in payloads]
        if not self.parent_page_expansion_enabled:
            return expanded_payloads, {}

        expansion_limit = self._normalized_budget(self.parent_page_expansion_limit)
        if expansion_limit == 0:
            return expanded_payloads, {}

        expanded_by_chunk_id: dict[str, dict[str, Any]] = {}
        for index, payload in enumerate(expanded_payloads[:expansion_limit]):
            parent_pages = _normalized_parent_pages(payload.get("parent_page_numbers"))
            if not parent_pages:
                continue
            current_pages = extract_physical_pages(payload)
            if current_pages == parent_pages:
                continue
            payload["page_span"] = list(parent_pages)
            metadata = dict(payload.get("metadata", {}))
            metadata["parent_page_numbers"] = list(parent_pages)
            payload["metadata"] = metadata
            expanded_payloads[index] = payload
            chunk_id = str(payload.get("chunk_id") or "").strip()
            if chunk_id:
                expanded_by_chunk_id[chunk_id] = dict(payload)

        return expanded_payloads, expanded_by_chunk_id

    def _apply_expansion_to_selected_payloads(
        self,
        selected_payloads: list[dict[str, Any]],
        expanded_by_chunk_id: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Execute `_apply_expansion_to_selected_payloads`.

        Args:
            selected_payloads: Input parameter.
            expanded_by_chunk_id: Input parameter.

        Returns:
            Any: The computed result of the function.
        """
        if not selected_payloads:
            return []
        if not expanded_by_chunk_id:
            return [dict(payload) for payload in selected_payloads]

        merged_payloads: list[dict[str, Any]] = []
        for selected in selected_payloads:
            payload = dict(selected)
            chunk_id = str(payload.get("chunk_id") or "").strip()
            expanded = expanded_by_chunk_id.get(chunk_id)
            if expanded is None:
                merged_payloads.append(payload)
                continue

            expanded_page_span = extract_physical_pages(expanded)
            if expanded_page_span:
                payload["page_span"] = expanded_page_span
            parent_pages = _normalized_parent_pages(expanded.get("parent_page_numbers"))
            if parent_pages:
                payload["parent_page_numbers"] = parent_pages
                metadata = dict(payload.get("metadata", {}))
                metadata["parent_page_numbers"] = parent_pages
                payload["metadata"] = metadata
            merged_payloads.append(payload)

        return merged_payloads

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
            diagnostics={},
            is_unanswerable=True,
        )

    def _normalized_budget(self, budget: int) -> int:
        """Convert caller-provided budgets into safe non-negative integers."""

        return max(int(budget), 0)

    def _resolved_budgets(self, *, question: QuestionRecord, question_class: str) -> tuple[int, int, int, bool]:
        """Execute `_resolved_budgets`.

        Args:
            question: Input parameter.
            question_class: Input parameter.

        Returns:
            Any: The computed result of the function.
        """
        question_class_budget = self.question_class_budgets.get(question_class)
        if question_class_budget is None:
            return (
                self._normalized_budget(self.candidate_budget),
                self._normalized_budget(self.rerank_budget),
                self._normalized_budget(
                    self.evidence_budget_by_answer_type.get(
                        question.answer_type,
                        self.default_evidence_budget,
                    )
                ),
                False,
            )

        return (
            self._normalized_budget(metadata_field(question_class_budget, "candidate_budget", self.candidate_budget)),
            self._normalized_budget(metadata_field(question_class_budget, "rerank_budget", self.rerank_budget)),
            self._normalized_budget(
                metadata_field(
                    question_class_budget,
                    "evidence_budget",
                    self.evidence_budget_by_answer_type.get(question.answer_type, self.default_evidence_budget),
                )
            ),
            True,
        )


def _copy_payload_window(payloads: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    """Return a defensive copy of payloads capped at the provided limit."""

    return [dict(item) for item in payloads[:limit]]


def _normalized_parent_pages(raw_value: Any) -> list[int]:
    """Execute `_normalized_parent_pages`.

    Args:
        raw_value: Input parameter.

    Returns:
        Any: The computed result of the function.
    """
    if not isinstance(raw_value, list):
        return []

    pages: set[int] = set()
    for page in raw_value:
        try:
            normalized = int(page)
        except (TypeError, ValueError):
            return []
        if normalized <= 0:
            return []
        pages.add(normalized)
    return sorted(pages)


def _chunk_family_participation(payloads: list[dict[str, Any]]) -> list[str]:
    """Execute `_chunk_family_participation`.

    Args:
        payloads: Input parameter.

    Returns:
        Any: The computed result of the function.
    """
    families: list[str] = []
    seen: set[str] = set()
    for payload in payloads:
        metadata = payload.get("metadata")
        family = None
        if isinstance(metadata, dict):
            family = metadata.get("chunk_family")
        if family is None:
            family = payload.get("chunk_type")
        normalized = str(family or "").strip()
        if not normalized or normalized in seen:
            continue
        families.append(normalized)
        seen.add(normalized)
    return families


def _has_soft_prefilters(query_metadata: Any | None) -> bool:
    """Return whether soft prefilters is present.

    Args:
        query_metadata: Input parameter.

    Returns:
        Any: The computed result of the function.
    """
    return bool(
        _metadata_sequence_length(metadata_field(query_metadata, "legal_entities", ()))
        or _metadata_sequence_length(metadata_field(query_metadata, "document_title_cues", ()))
    )


def _metadata_sequence_length(value: Any) -> int:
    """Execute `_metadata_sequence_length`.

    Args:
        value: Input parameter.

    Returns:
        Any: The computed result of the function.
    """
    try:
        return len(value)
    except TypeError:
        return 0


def _derive_question_class(query_metadata: Any | None) -> str:
    """Execute `_derive_question_class`.

    Args:
        query_metadata: Input parameter.

    Returns:
        Any: The computed result of the function.
    """
    if bool(metadata_field(query_metadata, "likely_multi_document", False)):
        return "cross_case"

    legal_entities = metadata_field(query_metadata, "legal_entities", ())
    case_entity_present = False
    statute_entity_present = False
    for entity in legal_entities:
        entity_type = str(metadata_field(entity, "entity_type", "")).strip()
        if not bool(metadata_field(entity, "is_strong", True)):
            continue
        if entity_type == "case_id":
            case_entity_present = True
        elif entity_type == "statute_id":
            statute_entity_present = True

    if case_entity_present:
        return "case"
    if statute_entity_present:
        return "statute"
    return "free_text"


def _hybrid_search_with_optional_query_metadata(
    hybrid_search: HybridSearch,
    question: QuestionRecord,
    *,
    top_k: int,
    query_metadata: Any | None,
) -> list[dict[str, Any]]:
    """Execute `_hybrid_search_with_optional_query_metadata`.

    Args:
        hybrid_search: Input parameter.
        question: Input parameter.
        top_k: Input parameter.
        query_metadata: Input parameter.

    Returns:
        Any: The computed result of the function.
    """
    if callable_accepts_keyword(hybrid_search.search, "query_metadata"):
        return hybrid_search.search(
            question,
            top_k=top_k,
            query_metadata=query_metadata,
        )
    return hybrid_search.search(question, top_k=top_k)
