from __future__ import annotations

import importlib
from typing import Any

import pytest

from src.common.schemas import QuestionRecord
from src.evaluation.contracts import PageReference


def _load_retrieval_contract() -> tuple[Any, Any]:
    try:
        package_module = importlib.import_module("src.retrieval")
        service_module = importlib.import_module("src.retrieval.service")
    except ModuleNotFoundError:
        pytest.fail(
            "W3B contract missing: expected `src.retrieval.service` with "
            "`RetrievalService`, `RetrievedChunk`, and `RetrievalResult`."
        )

    required_symbols = ("RetrievalService", "RetrievedChunk", "RetrievalResult")
    missing_symbols = [
        name for name in required_symbols if not hasattr(service_module, name)
    ]
    if missing_symbols:
        pytest.fail(
            "W3B contract incomplete: missing "
            + ", ".join(f"`{name}`" for name in missing_symbols)
            + " in `src.retrieval.service`."
        )

    return package_module, service_module


def _chunk(
    chunk_id: str,
    *,
    doc_id: str = "alpha",
    page_span: list[int] | None = None,
    chunk_type: str = "clause",
    text: str | None = None,
    retrieval_score: float = 0.5,
    rerank_score: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "doc_id": doc_id,
        "page_span": list(page_span or [1]),
        "chunk_type": chunk_type,
        "text": text or f"Evidence for {chunk_id}",
        "retrieval_score": retrieval_score,
        "rerank_score": rerank_score,
        "metadata": dict(metadata or {}),
    }


def _copy_payloads(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(item) for item in payloads]


def _chunk_snapshot(chunk: Any) -> dict[str, Any]:
    return {
        "chunk_id": getattr(chunk, "chunk_id"),
        "doc_id": getattr(chunk, "doc_id"),
        "page_span": list(getattr(chunk, "page_span")),
        "chunk_type": getattr(chunk, "chunk_type"),
        "text": getattr(chunk, "text"),
        "retrieval_score": getattr(chunk, "retrieval_score"),
        "rerank_score": getattr(chunk, "rerank_score"),
        "metadata": dict(getattr(chunk, "metadata")),
    }


def _page_snapshot(page_reference: Any) -> dict[str, Any]:
    if hasattr(page_reference, "model_dump"):
        return page_reference.model_dump()
    return {
        "doc_id": getattr(page_reference, "doc_id"),
        "page_numbers": list(getattr(page_reference, "page_numbers")),
    }


class SpyHybridSearch:
    def __init__(self, results: list[dict[str, Any]]) -> None:
        self._results = _copy_payloads(results)
        self.calls: list[dict[str, Any]] = []

    def search(
        self,
        question: QuestionRecord,
        top_k: int,
        *,
        query_metadata: Any | None = None,
    ) -> list[dict[str, Any]]:
        call = {"question": question, "top_k": top_k}
        if query_metadata is not None:
            call["query_metadata"] = query_metadata
        self.calls.append(call)
        return _copy_payloads(self._results[:top_k])


class SpyReranker:
    def __init__(self, results: list[dict[str, Any]] | None = None) -> None:
        self._results = _copy_payloads(results) if results is not None else None
        self.calls: list[dict[str, Any]] = []

    def rerank(
        self,
        question: QuestionRecord,
        candidates: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            {
                "question": question,
                "candidates": _copy_payloads(candidates),
                "top_k": top_k,
            }
        )
        if self._results is not None:
            return _copy_payloads(self._results[:top_k])

        reranked = _copy_payloads(candidates[:top_k])
        for index, item in enumerate(reranked):
            item["rerank_score"] = item.get("rerank_score", 1.0 - (index * 0.1))
        return reranked


class SpyEvidenceCompressor:
    def __init__(self, results: list[dict[str, Any]] | None = None) -> None:
        self._results = _copy_payloads(results) if results is not None else None
        self.calls: list[dict[str, Any]] = []

    def compress(
        self,
        question: QuestionRecord,
        reranked_chunks: list[dict[str, Any]],
        max_evidence: int,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            {
                "question": question,
                "reranked_chunks": _copy_payloads(reranked_chunks),
                "max_evidence": max_evidence,
            }
        )
        if self._results is not None:
            return _copy_payloads(self._results[:max_evidence])
        return _copy_payloads(reranked_chunks[:max_evidence])


class OverReturningHybridSearch(SpyHybridSearch):
    def search(
        self,
        question: QuestionRecord,
        top_k: int,
        *,
        query_metadata: Any | None = None,
    ) -> list[dict[str, Any]]:
        call = {"question": question, "top_k": top_k}
        if query_metadata is not None:
            call["query_metadata"] = query_metadata
        self.calls.append(call)
        return _copy_payloads(self._results)


class MetadataAwareHybridSearch(SpyHybridSearch):
    def search(
        self,
        question: QuestionRecord,
        top_k: int,
        *,
        query_metadata: Any | None = None,
    ) -> list[dict[str, Any]]:
        results = super().search(question, top_k, query_metadata=query_metadata)
        if query_metadata is None:
            return results

        legal_entities = query_metadata.get("legal_entities", [])
        target_values = {
            str(entity.get("normalized_value") or "").casefold()
            for entity in legal_entities
            if isinstance(entity, dict)
        }
        results.sort(
            key=lambda item: (
                0
                if any(target in str(item.get("text") or "").casefold() for target in target_values)
                else 1,
                -float(item.get("retrieval_score", 0.0)),
            )
        )
        return results


class OverReturningReranker(SpyReranker):
    def rerank(
        self,
        question: QuestionRecord,
        candidates: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            {
                "question": question,
                "candidates": _copy_payloads(candidates),
                "top_k": top_k,
            }
        )
        if self._results is not None:
            return _copy_payloads(self._results)
        return super().rerank(question, candidates, top_k)


class FailingReranker:
    def rerank(
        self,
        question: QuestionRecord,
        candidates: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        del question, candidates, top_k
        raise AssertionError("reranker should not run for empty retrieval")


class FailingEvidenceCompressor:
    def __init__(self) -> None:
        self.calls = 0

    def compress(
        self,
        question: QuestionRecord,
        reranked_chunks: list[dict[str, Any]],
        max_evidence: int,
    ) -> list[dict[str, Any]]:
        del question, reranked_chunks, max_evidence
        self.calls += 1
        raise AssertionError("compressor should not run when no evidence survives retrieval")


def test_retrieval_package_exports_service_contract() -> None:
    package_module, service_module = _load_retrieval_contract()

    assert package_module.RetrievalService is service_module.RetrievalService
    assert package_module.RetrievedChunk is service_module.RetrievedChunk
    assert package_module.RetrievalResult is service_module.RetrievalResult


def test_retrieval_service_applies_candidate_rerank_and_evidence_budgets() -> None:
    _, service_module = _load_retrieval_contract()
    question = QuestionRecord(id="q-free", question="Summarize the termination clause.", answer_type="free_text")

    hybrid_search = SpyHybridSearch(
        [_chunk("c1"), _chunk("c2"), _chunk("c3"), _chunk("c4")]
    )
    reranker = SpyReranker(results=[_chunk("c3", rerank_score=0.91), _chunk("c1", rerank_score=0.83)])
    compressor = SpyEvidenceCompressor(results=[_chunk("c3", rerank_score=0.91)])

    service = service_module.RetrievalService(
        hybrid_search=hybrid_search,
        reranker=reranker,
        evidence_compressor=compressor,
        candidate_budget=3,
        rerank_budget=2,
        default_evidence_budget=2,
        evidence_budget_by_answer_type={"free_text": 1},
    )

    result = service.retrieve(question)

    assert isinstance(result, service_module.RetrievalResult)
    assert hybrid_search.calls == [{"question": question, "top_k": 3}]
    assert reranker.calls[0]["question"] == question
    assert [item["chunk_id"] for item in reranker.calls[0]["candidates"]] == ["c1", "c2", "c3"]
    assert reranker.calls[0]["top_k"] == 2
    assert compressor.calls[0]["question"] == question
    assert [item["chunk_id"] for item in compressor.calls[0]["reranked_chunks"]] == ["c3", "c1"]
    assert compressor.calls[0]["max_evidence"] == 1
    assert result.question_id == "q-free"
    assert result.query == question.question
    assert result.answer_type == question.answer_type
    assert result.candidate_count == 3
    assert result.reranked_count == 2
    assert result.is_unanswerable is False


def test_retrieval_service_forwards_optional_query_metadata_to_hybrid_search() -> None:
    _, service_module = _load_retrieval_contract()
    question = QuestionRecord(id="q-meta", question="What does Case CFI 012/2024 say?", answer_type="number")
    hybrid_search = SpyHybridSearch([_chunk("c1", page_span=[2], retrieval_score=0.91)])
    query_metadata = {
        "legal_entities": [{"entity_type": "case_id", "normalized_value": "CFI012/2024"}],
        "likely_multi_document": False,
    }

    service = service_module.RetrievalService(
        hybrid_search=hybrid_search,
        reranker=SpyReranker(results=[_chunk("c1", page_span=[2], rerank_score=0.91)]),
        evidence_compressor=SpyEvidenceCompressor(results=[_chunk("c1", page_span=[2], rerank_score=0.91)]),
        candidate_budget=5,
        rerank_budget=3,
        default_evidence_budget=2,
        evidence_budget_by_answer_type={},
    )

    result = service.retrieve(question, query_metadata=query_metadata)

    assert result.question_id == "q-meta"
    assert hybrid_search.calls == [
        {
            "question": question,
            "top_k": 5,
            "query_metadata": query_metadata,
        }
    ]


def test_retrieval_service_metadata_guidance_can_change_selected_evidence_without_hard_filtering() -> None:
    _, service_module = _load_retrieval_contract()
    question = QuestionRecord(id="q-meta-order", question="What does Case 012/2024 say?", answer_type="number")
    query_metadata = {
        "legal_entities": [{"entity_type": "case_id", "normalized_value": "case 012/2024"}],
        "likely_multi_document": False,
    }
    generic_chunk = _chunk(
        "beta-1",
        doc_id="beta",
        page_span=[2],
        text="Generic contract payment terms.",
        retrieval_score=0.95,
    )
    targeted_chunk = _chunk(
        "alpha-1",
        doc_id="alpha",
        page_span=[4],
        text="Case 012/2024 states that the penalty is AED 500.",
        retrieval_score=0.71,
    )

    service = service_module.RetrievalService(
        hybrid_search=MetadataAwareHybridSearch([generic_chunk, targeted_chunk]),
        reranker=SpyReranker(results=[targeted_chunk, generic_chunk]),
        evidence_compressor=SpyEvidenceCompressor(results=[targeted_chunk]),
        candidate_budget=2,
        rerank_budget=2,
        default_evidence_budget=1,
        evidence_budget_by_answer_type={},
    )

    result = service.retrieve(question, query_metadata=query_metadata)

    assert result.retrieved_chunk_pages == [PageReference(doc_id="alpha", page_numbers=[4])]


def test_retrieval_service_builds_deduplicated_page_references_from_selected_evidence() -> None:
    _, service_module = _load_retrieval_contract()
    question = QuestionRecord(id="q-pages", question="Which pages define the court fee?", answer_type="name")

    selected_evidence = [
        _chunk("alpha-1", doc_id="alpha", page_span=[2, 2], rerank_score=0.95),
        _chunk("alpha-2", doc_id="alpha", page_span=[4, 2], rerank_score=0.88),
        _chunk("beta-1", doc_id="beta", page_span=[5, 3], rerank_score=0.82),
    ]

    service = service_module.RetrievalService(
        hybrid_search=SpyHybridSearch(selected_evidence),
        reranker=SpyReranker(results=selected_evidence),
        evidence_compressor=SpyEvidenceCompressor(results=selected_evidence),
        candidate_budget=10,
        rerank_budget=5,
        default_evidence_budget=4,
        evidence_budget_by_answer_type={},
    )

    result = service.retrieve(question)

    assert all(isinstance(item, PageReference) for item in result.retrieved_chunk_pages)
    assert [_page_snapshot(item) for item in result.retrieved_chunk_pages] == [
        {"doc_id": "alpha", "page_numbers": [2, 4]},
        {"doc_id": "beta", "page_numbers": [3, 5]},
    ]


def test_retrieval_service_returns_unanswerable_without_reranking_when_search_is_empty() -> None:
    _, service_module = _load_retrieval_contract()
    question = QuestionRecord(id="q-null", question="Is there an arbitration clause?", answer_type="boolean")

    service = service_module.RetrievalService(
        hybrid_search=SpyHybridSearch([]),
        reranker=FailingReranker(),
        evidence_compressor=FailingEvidenceCompressor(),
        candidate_budget=8,
        rerank_budget=4,
        default_evidence_budget=2,
        evidence_budget_by_answer_type={},
    )

    result = service.retrieve(question)

    assert result.is_unanswerable is True
    assert result.candidate_count == 0
    assert result.reranked_count == 0
    assert result.evidence_chunks == []
    assert result.retrieved_chunk_pages == []


def test_retrieval_service_returns_unanswerable_when_reranked_scores_do_not_clear_threshold() -> None:
    _, service_module = _load_retrieval_contract()
    question = QuestionRecord(id="q-threshold", question="Who signed the agreement?", answer_type="name")
    compressor = FailingEvidenceCompressor()

    service = service_module.RetrievalService(
        hybrid_search=SpyHybridSearch([_chunk("c1"), _chunk("c2")]),
        reranker=SpyReranker(
            results=[
                _chunk("c1", rerank_score=0.29),
                _chunk("c2", rerank_score=0.11),
            ]
        ),
        evidence_compressor=compressor,
        candidate_budget=5,
        rerank_budget=3,
        default_evidence_budget=2,
        evidence_budget_by_answer_type={},
        min_rerank_score=0.3,
    )

    result = service.retrieve(question)

    assert compressor.calls == 0
    assert result.is_unanswerable is True
    assert result.evidence_chunks == []
    assert result.retrieved_chunk_pages == []


def test_retrieval_service_uses_answer_type_specific_budget_and_default_fallback() -> None:
    _, service_module = _load_retrieval_contract()
    compressor = SpyEvidenceCompressor(results=[_chunk("c1", rerank_score=0.9), _chunk("c2", rerank_score=0.8)])

    service = service_module.RetrievalService(
        hybrid_search=SpyHybridSearch([_chunk("c1"), _chunk("c2"), _chunk("c3")]),
        reranker=SpyReranker(
            results=[
                _chunk("c1", rerank_score=0.9),
                _chunk("c2", rerank_score=0.8),
                _chunk("c3", rerank_score=0.7),
            ]
        ),
        evidence_compressor=compressor,
        candidate_budget=5,
        rerank_budget=3,
        default_evidence_budget=3,
        evidence_budget_by_answer_type={"number": 1},
    )

    number_question = QuestionRecord(id="q-number", question="How many days notice is required?", answer_type="number")
    free_text_question = QuestionRecord(id="q-free", question="Summarize the remedies clause.", answer_type="free_text")

    service.retrieve(number_question)
    service.retrieve(free_text_question)

    assert compressor.calls[0]["question"] == number_question
    assert compressor.calls[0]["max_evidence"] == 1
    assert compressor.calls[1]["question"] == free_text_question
    assert compressor.calls[1]["max_evidence"] == 3


def test_retrieval_service_returns_typed_evidence_chunks_with_scores_and_metadata() -> None:
    _, service_module = _load_retrieval_contract()
    question = QuestionRecord(
        id="q-evidence",
        question="What does Article 7 say about severance?",
        answer_type="free_text",
    )
    selected_chunk = _chunk(
        "alpha-7",
        doc_id="alpha",
        page_span=[7, 8],
        chunk_type="table",
        text="Article 7 severance entitlements are listed in the schedule.",
        retrieval_score=0.41,
        rerank_score=0.97,
        metadata={"section": "Article 7", "entities": ["severance"]},
    )

    service = service_module.RetrievalService(
        hybrid_search=SpyHybridSearch([selected_chunk]),
        reranker=SpyReranker(results=[selected_chunk]),
        evidence_compressor=SpyEvidenceCompressor(results=[selected_chunk]),
        candidate_budget=5,
        rerank_budget=3,
        default_evidence_budget=2,
        evidence_budget_by_answer_type={"free_text": 1},
    )

    result = service.retrieve(question)

    assert len(result.evidence_chunks) == 1
    evidence = result.evidence_chunks[0]
    assert isinstance(evidence, service_module.RetrievedChunk)
    assert _chunk_snapshot(evidence) == {
        "chunk_id": "alpha-7",
        "doc_id": "alpha",
        "page_span": [7, 8],
        "chunk_type": "table",
        "text": "Article 7 severance entitlements are listed in the schedule.",
        "retrieval_score": 0.41,
        "rerank_score": 0.97,
        "metadata": {"section": "Article 7", "entities": ["severance"]},
    }


def test_retrieval_service_clamps_over_returning_search_and_rerank_results() -> None:
    _, service_module = _load_retrieval_contract()
    question = QuestionRecord(id="q-clamp", question="Summarize the indemnity clause.", answer_type="free_text")

    hybrid_search = OverReturningHybridSearch(
        [_chunk("c1"), _chunk("c2"), _chunk("c3"), _chunk("c4")]
    )
    reranker = OverReturningReranker(
        results=[
            _chunk("c4", rerank_score=0.95),
            _chunk("c3", rerank_score=0.91),
            _chunk("c2", rerank_score=0.87),
        ]
    )
    compressor = SpyEvidenceCompressor(results=[_chunk("c4", rerank_score=0.95), _chunk("c3", rerank_score=0.91)])

    service = service_module.RetrievalService(
        hybrid_search=hybrid_search,
        reranker=reranker,
        evidence_compressor=compressor,
        candidate_budget=2,
        rerank_budget=1,
        default_evidence_budget=2,
        evidence_budget_by_answer_type={},
    )

    result = service.retrieve(question)

    assert hybrid_search.calls == [{"question": question, "top_k": 2}]
    assert [item["chunk_id"] for item in reranker.calls[0]["candidates"]] == ["c1", "c2"]
    assert reranker.calls[0]["top_k"] == 1
    assert [item["chunk_id"] for item in compressor.calls[0]["reranked_chunks"]] == ["c4"]
    assert result.candidate_count == 2
    assert result.reranked_count == 1
    assert [_chunk_snapshot(chunk)["chunk_id"] for chunk in result.evidence_chunks] == ["c4", "c3"]


def test_retrieval_service_drops_invalid_page_spans_and_returns_unanswerable() -> None:
    _, service_module = _load_retrieval_contract()
    question = QuestionRecord(id="q-pages-invalid", question="Which page sets the fee?", answer_type="name")

    invalid_evidence = [
        {
            **_chunk("missing-pages"),
            "page_span": [],
        },
        _chunk("zero-page", page_span=[0, 2]),
    ]

    service = service_module.RetrievalService(
        hybrid_search=SpyHybridSearch(invalid_evidence),
        reranker=SpyReranker(results=invalid_evidence),
        evidence_compressor=SpyEvidenceCompressor(results=invalid_evidence),
        candidate_budget=5,
        rerank_budget=3,
        default_evidence_budget=2,
        evidence_budget_by_answer_type={},
    )

    result = service.retrieve(question)

    assert result.is_unanswerable is True
    assert result.evidence_chunks == []
    assert result.retrieved_chunk_pages == []
