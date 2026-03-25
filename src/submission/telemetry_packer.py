"""Telemetry packaging helpers for submission answers."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from src.answering.service import AnswerResult
from src.evaluation.contracts import PageReference
from src.retrieval.service import RetrievalResult


def build_answer_telemetry(
    *,
    retrieval_result: RetrievalResult,
    answer_result: AnswerResult,
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    total_time_ms: float,
    ttft_ms: float | None = None,
    tpot_ms: float = 0.0,
) -> dict[str, Any]:
    """Build telemetry payload for one answer.

    Supporting pages from the final answer take precedence over retrieval-level pages.
    For non-streaming generation, `ttft_ms` falls back to `total_time_ms`.
    """

    resolved_ttft_ms = float(total_time_ms) if ttft_ms is None else float(ttft_ms)
    preferred_pages: list[PageReference] | None
    authoritative_preferred = answer_result.page_trace is not None
    if answer_result.page_trace is not None:
        preferred_pages = answer_result.page_trace.final_emitted_pages
    else:
        preferred_pages = answer_result.evidence_pages or None
    resolved_pages = _coalesce_page_references(
        preferred=preferred_pages,
        fallback=retrieval_result.retrieved_chunk_pages,
        authoritative_preferred=authoritative_preferred,
    )
    retrieved_chunk_pages = [_serialize_page_reference(reference) for reference in resolved_pages]

    return {
        "timing": {
            "ttft_ms": resolved_ttft_ms,
            "tpot_ms": float(tpot_ms),
            "total_time_ms": float(total_time_ms),
        },
        "retrieval": _build_retrieval_telemetry(
            retrieved_chunk_pages=retrieved_chunk_pages,
            retrieval_result=retrieval_result,
            answer_result=answer_result,
        ),
        "usage": {
            "input_tokens": max(int(input_tokens), 0),
            "output_tokens": max(int(output_tokens), 0),
        },
        "model_name": str(model_name),
    }


def pack_answer_telemetry(
    *,
    retrieval_result: RetrievalResult,
    answer_result: AnswerResult,
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    total_time_ms: float,
    ttft_ms: float | None = None,
    tpot_ms: float = 0.0,
) -> dict[str, Any]:
    """Backward-compatible alias for telemetry packaging."""

    return build_answer_telemetry(
        retrieval_result=retrieval_result,
        answer_result=answer_result,
        model_name=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_time_ms=total_time_ms,
        ttft_ms=ttft_ms,
        tpot_ms=tpot_ms,
    )


class TelemetryPacker:
    """OO wrapper for telemetry packing to preserve loose contract variants."""

    def build_answer_telemetry(
        self,
        *,
        retrieval_result: RetrievalResult,
        answer_result: AnswerResult,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        total_time_ms: float,
        ttft_ms: float | None = None,
        tpot_ms: float = 0.0,
    ) -> dict[str, Any]:
        return build_answer_telemetry(
            retrieval_result=retrieval_result,
            answer_result=answer_result,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_time_ms=total_time_ms,
            ttft_ms=ttft_ms,
            tpot_ms=tpot_ms,
        )

    pack_answer = build_answer_telemetry
    pack_answer_telemetry = build_answer_telemetry


def _coalesce_page_references(
    *,
    preferred: list[PageReference] | None,
    fallback: list[PageReference] | None,
    authoritative_preferred: bool = False,
) -> list[PageReference]:
    if authoritative_preferred and preferred is not None:
        candidates = preferred
    else:
        candidates = preferred if preferred else fallback
    if not candidates:
        return []

    pages_by_doc: OrderedDict[str, list[int]] = OrderedDict()
    seen_pages_by_doc: dict[str, set[int]] = {}
    for reference in candidates:
        doc_id = str(reference.doc_id)
        existing_pages = pages_by_doc.setdefault(doc_id, [])
        seen_pages = seen_pages_by_doc.setdefault(doc_id, set())
        for page_number in reference.page_numbers:
            normalized = int(page_number)
            if normalized in seen_pages:
                continue
            seen_pages.add(normalized)
            existing_pages.append(normalized)

    return [
        PageReference(doc_id=doc_id, page_numbers=page_numbers)
        for doc_id, page_numbers in pages_by_doc.items()
    ]


def _serialize_page_reference(reference: PageReference) -> dict[str, Any]:
    return {
        "doc_id": reference.doc_id,
        "page_numbers": list(reference.page_numbers),
    }


def _build_retrieval_telemetry(
    *,
    retrieved_chunk_pages: list[dict[str, Any]],
    retrieval_result: RetrievalResult,
    answer_result: AnswerResult,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"retrieved_chunk_pages": retrieved_chunk_pages}
    page_trace = answer_result.page_trace
    if page_trace is not None:
        payload["raw_retrieved_chunk_pages"] = [
            _serialize_page_reference(reference) for reference in page_trace.raw_retrieved_chunk_pages
        ]
        payload["pass_a_pages"] = [
            _serialize_page_reference(reference) for reference in page_trace.pass_a_pages
        ]
        payload["solver_reported_pages"] = [
            _serialize_page_reference(reference) for reference in page_trace.solver_reported_pages
        ]
        payload["page_validation"] = {
            "action": page_trace.validation_action,
            "collapsed_answer": page_trace.collapsed_answer,
        }
    if retrieval_result.diagnostics:
        payload["diagnostics"] = dict(retrieval_result.diagnostics)
    return payload
