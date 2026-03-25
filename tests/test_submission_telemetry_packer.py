from __future__ import annotations

import pytest

from src.answering.service import AnswerResult
from src.evaluation.contracts import PageReference
from src.retrieval.service import RetrievalResult, RetrievedChunk
from tests.support.imports import load_page_attribution_module
from tests.support.submission import build_answer_telemetry


def test_telemetry_packer_prefers_supporting_pages_and_uses_total_time_for_non_streaming_ttft() -> None:
    page_attribution = load_page_attribution_module()
    retrieval_result = RetrievalResult(
        question_id="q-free",
        query="Summarize the order.",
        answer_type="free_text",
        candidate_count=3,
        reranked_count=2,
        evidence_chunks=[
            RetrievedChunk(
                chunk_id="c1",
                doc_id="alpha",
                page_span=[2, 3],
                chunk_type="clause",
                text="The tribunal dismissed the claim and ordered payment within 14 days.",
                retrieval_score=0.91,
            )
        ],
        retrieved_chunk_pages=[PageReference(doc_id="alpha", page_numbers=[2, 3])],
        is_unanswerable=False,
    )
    answer_result = AnswerResult(
        question_id="q-free",
        answer="The tribunal dismissed the claim.",
        confidence=0.82,
        evidence_pages=[PageReference(doc_id="alpha", page_numbers=[3])],
        page_trace=page_attribution.PageAttributionTrace(
            raw_retrieved_chunk_pages=[PageReference(doc_id="alpha", page_numbers=[2, 3])],
            pass_a_pages=[PageReference(doc_id="alpha", page_numbers=[3])],
            solver_reported_pages=[PageReference(doc_id="alpha", page_numbers=[3])],
            final_emitted_pages=[PageReference(doc_id="alpha", page_numbers=[3])],
            validation_action="solver_subset",
            collapsed_answer=False,
        ),
    )

    telemetry = build_answer_telemetry(
        retrieval_result=retrieval_result,
        answer_result=answer_result,
        model_name="gpt-5-mini",
        input_tokens=144,
        output_tokens=17,
        total_time_ms=1_250,
        ttft_ms=None,
        tpot_ms=0,
    )

    assert telemetry["timing"] == {
        "ttft_ms": pytest.approx(1_250),
        "tpot_ms": pytest.approx(0),
        "total_time_ms": pytest.approx(1_250),
    }
    assert telemetry["retrieval"] == {
        "retrieved_chunk_pages": [{"doc_id": "alpha", "page_numbers": [3]}],
        "raw_retrieved_chunk_pages": [{"doc_id": "alpha", "page_numbers": [2, 3]}],
        "pass_a_pages": [{"doc_id": "alpha", "page_numbers": [3]}],
        "solver_reported_pages": [{"doc_id": "alpha", "page_numbers": [3]}],
        "page_validation": {
            "action": "solver_subset",
            "collapsed_answer": False,
        },
    }
    assert telemetry["usage"] == {"input_tokens": 144, "output_tokens": 17}
    assert telemetry["model_name"] == "gpt-5-mini"


def test_telemetry_packer_preserves_empty_final_pages_for_grounded_no_answer() -> None:
    page_attribution = load_page_attribution_module()
    retrieval_result = RetrievalResult(
        question_id="q-free",
        query="Summarize the order.",
        answer_type="free_text",
        candidate_count=2,
        reranked_count=1,
        evidence_chunks=[
            RetrievedChunk(
                chunk_id="c1",
                doc_id="alpha",
                page_span=[4],
                chunk_type="clause",
                text="The record does not contain an answer to the requested issue.",
                retrieval_score=0.77,
            )
        ],
        retrieved_chunk_pages=[PageReference(doc_id="alpha", page_numbers=[4])],
        is_unanswerable=False,
    )
    answer_result = AnswerResult(
        question_id="q-free",
        answer="There is no information on this question in the provided documents.",
        confidence=0.0,
        evidence_pages=[],
        page_trace=page_attribution.PageAttributionTrace(
            raw_retrieved_chunk_pages=[PageReference(doc_id="alpha", page_numbers=[4])],
            pass_a_pages=[PageReference(doc_id="alpha", page_numbers=[4])],
            solver_reported_pages=[],
            final_emitted_pages=[],
            validation_action="no_answer_empty",
            collapsed_answer=False,
        ),
    )

    telemetry = build_answer_telemetry(
        retrieval_result=retrieval_result,
        answer_result=answer_result,
        model_name="gpt-5-mini",
        input_tokens=32,
        output_tokens=12,
        total_time_ms=800,
        ttft_ms=None,
        tpot_ms=0,
    )

    assert telemetry["retrieval"] == {
        "retrieved_chunk_pages": [],
        "raw_retrieved_chunk_pages": [{"doc_id": "alpha", "page_numbers": [4]}],
        "pass_a_pages": [{"doc_id": "alpha", "page_numbers": [4]}],
        "solver_reported_pages": [],
        "page_validation": {
            "action": "no_answer_empty",
            "collapsed_answer": False,
        },
    }


def test_telemetry_packer_uses_final_emitted_pages_as_authoritative_when_answer_payload_drifted() -> None:
    page_attribution = load_page_attribution_module()
    retrieval_result = RetrievalResult(
        question_id="q-name",
        query="Who is the appointed liquidator?",
        answer_type="name",
        candidate_count=1,
        reranked_count=1,
        evidence_chunks=[
            RetrievedChunk(
                chunk_id="c1",
                doc_id="alpha",
                page_span=[3],
                chunk_type="clause",
                text="Page 3 identifies the respondent but not the liquidator.",
                retrieval_score=0.84,
            )
        ],
        retrieved_chunk_pages=[PageReference(doc_id="alpha", page_numbers=[3])],
        is_unanswerable=False,
    )
    answer_result = AnswerResult(
        question_id="q-name",
        answer=None,
        confidence=0.0,
        evidence_pages=[],
        page_trace=page_attribution.PageAttributionTrace(
            raw_retrieved_chunk_pages=[PageReference(doc_id="alpha", page_numbers=[3])],
            pass_a_pages=[PageReference(doc_id="alpha", page_numbers=[3])],
            solver_reported_pages=[PageReference(doc_id="alpha", page_numbers=[3])],
            final_emitted_pages=[PageReference(doc_id="alpha", page_numbers=[3])],
            validation_action="no_answer_preserved_pages",
            collapsed_answer=False,
        ),
    )

    telemetry = build_answer_telemetry(
        retrieval_result=retrieval_result,
        answer_result=answer_result,
        model_name="gpt-5-mini",
        input_tokens=24,
        output_tokens=0,
        total_time_ms=350,
    )

    assert telemetry["retrieval"] == {
        "retrieved_chunk_pages": [{"doc_id": "alpha", "page_numbers": [3]}],
        "raw_retrieved_chunk_pages": [{"doc_id": "alpha", "page_numbers": [3]}],
        "pass_a_pages": [{"doc_id": "alpha", "page_numbers": [3]}],
        "solver_reported_pages": [{"doc_id": "alpha", "page_numbers": [3]}],
        "page_validation": {
            "action": "no_answer_preserved_pages",
            "collapsed_answer": False,
        },
    }
