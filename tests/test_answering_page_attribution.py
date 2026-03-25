from __future__ import annotations

from typing import Any

import pytest

from src.evaluation.contracts import PageReference
from src.retrieval.service import RetrievedChunk
from tests.support.imports import load_page_attribution_module as _load_page_attribution_module


def _candidate_page(
    module: Any,
    *,
    doc_id: str = "alpha",
    page_number: int,
    text: str,
    chunk_ids: list[str],
    best_retrieval_score: float = 0.0,
    best_rerank_score: float | None = None,
) -> Any:
    return module.CandidatePage(
        doc_id=doc_id,
        page_number=page_number,
        text=text,
        chunk_ids=chunk_ids,
        best_retrieval_score=best_retrieval_score,
        best_rerank_score=best_rerank_score,
    )


def _page_snapshot(candidate: Any) -> dict[str, Any]:
    return {
        "doc_id": candidate.doc_id,
        "page_number": candidate.page_number,
        "chunk_ids": list(candidate.chunk_ids),
    }


def _ref_snapshot(ref: PageReference) -> dict[str, Any]:
    return {"doc_id": ref.doc_id, "page_numbers": list(ref.page_numbers)}


def test_pass_a_suppresses_title_pages_when_stronger_legal_page_exists() -> None:
    module = _load_page_attribution_module()
    config = module.PageAttributionConfig()
    raw_pages = [
        _candidate_page(
            module,
            page_number=1,
            text="Service Agreement ACME LLC Table of Contents",
            chunk_ids=["cover"],
            best_retrieval_score=0.41,
            best_rerank_score=0.62,
        ),
        _candidate_page(
            module,
            page_number=3,
            text="Clause 4. The tenant must pay the fee within 10 days of invoice.",
            chunk_ids=["clause-4"],
            best_retrieval_score=0.77,
            best_rerank_score=0.94,
        ),
    ]

    result = module.prune_candidate_pages(raw_pages, config=config)

    assert [_page_snapshot(page) for page in result.selected_pages] == [
        {"doc_id": "alpha", "page_number": 3, "chunk_ids": ["clause-4"]}
    ]
    assert [_page_snapshot(page) for page in result.suppressed_pages] == [
        {"doc_id": "alpha", "page_number": 1, "chunk_ids": ["cover"]}
    ]


def test_pass_a_can_suppress_strongest_title_page_when_substantive_page_exists() -> None:
    module = _load_page_attribution_module()
    config = module.PageAttributionConfig()
    raw_pages = [
        _candidate_page(
            module,
            page_number=1,
            text="Master Services Agreement Table of Contents",
            chunk_ids=["cover-strongest"],
            best_retrieval_score=0.78,
            best_rerank_score=0.97,
        ),
        _candidate_page(
            module,
            page_number=4,
            text="Clause 11. The respondent must pay costs within 14 days.",
            chunk_ids=["clause-11"],
            best_retrieval_score=0.62,
            best_rerank_score=0.83,
        ),
    ]

    result = module.prune_candidate_pages(raw_pages, config=config)

    assert [_page_snapshot(page) for page in result.selected_pages] == [
        {"doc_id": "alpha", "page_number": 4, "chunk_ids": ["clause-11"]}
    ]
    assert [_page_snapshot(page) for page in result.suppressed_pages] == [
        {"doc_id": "alpha", "page_number": 1, "chunk_ids": ["cover-strongest"]}
    ]


def test_pass_a_suppresses_repeated_boilerplate_but_keeps_substantive_page() -> None:
    module = _load_page_attribution_module()
    config = module.PageAttributionConfig()
    repeated = "ACME LLC Confidential Draft - Internal Circulation Only"
    raw_pages = [
        _candidate_page(
            module,
            page_number=1,
            text=repeated,
            chunk_ids=["boilerplate-1"],
            best_retrieval_score=0.52,
            best_rerank_score=0.73,
        ),
        _candidate_page(
            module,
            page_number=2,
            text=repeated,
            chunk_ids=["boilerplate-2"],
            best_retrieval_score=0.49,
            best_rerank_score=0.71,
        ),
        _candidate_page(
            module,
            page_number=6,
            text="Article 8. The claimant may terminate the agreement after 30 days' notice.",
            chunk_ids=["article-8"],
            best_retrieval_score=0.81,
            best_rerank_score=0.96,
        ),
    ]

    result = module.prune_candidate_pages(raw_pages, config=config)

    assert [_page_snapshot(page) for page in result.selected_pages] == [
        {"doc_id": "alpha", "page_number": 6, "chunk_ids": ["article-8"]}
    ]
    assert [_page_snapshot(page) for page in result.suppressed_pages] == [
        {"doc_id": "alpha", "page_number": 1, "chunk_ids": ["boilerplate-1"]},
        {"doc_id": "alpha", "page_number": 2, "chunk_ids": ["boilerplate-2"]},
    ]


def test_pass_a_can_suppress_strongest_repeated_boilerplate_if_substantive_page_exists() -> None:
    module = _load_page_attribution_module()
    config = module.PageAttributionConfig()
    repeated = "ACME LLC Confidential Draft - Internal Circulation Only"
    raw_pages = [
        _candidate_page(
            module,
            page_number=1,
            text=repeated,
            chunk_ids=["boilerplate-strongest"],
            best_retrieval_score=0.74,
            best_rerank_score=0.95,
        ),
        _candidate_page(
            module,
            page_number=2,
            text=repeated,
            chunk_ids=["boilerplate-secondary"],
            best_retrieval_score=0.60,
            best_rerank_score=0.84,
        ),
        _candidate_page(
            module,
            page_number=6,
            text="Article 8. The claimant may terminate the agreement after 30 days' notice.",
            chunk_ids=["article-8"],
            best_retrieval_score=0.58,
            best_rerank_score=0.81,
        ),
    ]

    result = module.prune_candidate_pages(raw_pages, config=config)

    assert [_page_snapshot(page) for page in result.selected_pages] == [
        {"doc_id": "alpha", "page_number": 6, "chunk_ids": ["article-8"]}
    ]
    assert [_page_snapshot(page) for page in result.suppressed_pages] == [
        {"doc_id": "alpha", "page_number": 1, "chunk_ids": ["boilerplate-strongest"]},
        {"doc_id": "alpha", "page_number": 2, "chunk_ids": ["boilerplate-secondary"]},
    ]


def test_pass_a_does_not_treat_cross_document_repetition_as_boilerplate() -> None:
    module = _load_page_attribution_module()
    config = module.PageAttributionConfig()
    repeated = "ACME LLC Confidential Draft - Internal Circulation Only"
    raw_pages = [
        _candidate_page(
            module,
            doc_id="alpha",
            page_number=2,
            text=repeated,
            chunk_ids=["alpha-shared"],
            best_retrieval_score=0.62,
            best_rerank_score=0.74,
        ),
        _candidate_page(
            module,
            doc_id="alpha",
            page_number=6,
            text="Article 8. The claimant may terminate the agreement after 30 days' notice.",
            chunk_ids=["alpha-article-8"],
            best_retrieval_score=0.83,
            best_rerank_score=0.96,
        ),
        _candidate_page(
            module,
            doc_id="beta",
            page_number=4,
            text=repeated,
            chunk_ids=["beta-shared"],
            best_retrieval_score=0.61,
            best_rerank_score=0.73,
        ),
        _candidate_page(
            module,
            doc_id="beta",
            page_number=9,
            text="Clause 5. The respondent shall bear all tribunal and filing costs.",
            chunk_ids=["beta-clause-5"],
            best_retrieval_score=0.82,
            best_rerank_score=0.95,
        ),
    ]

    result = module.prune_candidate_pages(raw_pages, config=config)

    assert [_page_snapshot(page) for page in result.selected_pages] == [
        {"doc_id": "alpha", "page_number": 2, "chunk_ids": ["alpha-shared"]},
        {"doc_id": "alpha", "page_number": 6, "chunk_ids": ["alpha-article-8"]},
        {"doc_id": "beta", "page_number": 4, "chunk_ids": ["beta-shared"]},
        {"doc_id": "beta", "page_number": 9, "chunk_ids": ["beta-clause-5"]},
    ]
    assert result.suppressed_pages == []


def test_pass_a_preserves_multi_page_chunk_spans() -> None:
    module = _load_page_attribution_module()
    config = module.PageAttributionConfig()
    raw_pages = [
        _candidate_page(
            module,
            page_number=5,
            text="Schedule A begins the payment table.",
            chunk_ids=["table-1"],
            best_retrieval_score=0.74,
            best_rerank_score=0.91,
        ),
        _candidate_page(
            module,
            page_number=6,
            text="Schedule A continues with the payment table and deadlines.",
            chunk_ids=["table-1"],
            best_retrieval_score=0.72,
            best_rerank_score=0.89,
        ),
    ]

    result = module.prune_candidate_pages(raw_pages, config=config)

    assert [_page_snapshot(page) for page in result.selected_pages] == [
        {"doc_id": "alpha", "page_number": 5, "chunk_ids": ["table-1"]},
        {"doc_id": "alpha", "page_number": 6, "chunk_ids": ["table-1"]},
    ]
    assert result.suppressed_pages == []


def test_pass_a_never_returns_empty_selection_when_raw_pages_exist() -> None:
    module = _load_page_attribution_module()
    config = module.PageAttributionConfig()
    raw_pages = [
        _candidate_page(
            module,
            page_number=1,
            text="Table of Contents",
            chunk_ids=["cover"],
            best_retrieval_score=0.31,
            best_rerank_score=0.40,
        )
    ]

    result = module.prune_candidate_pages(raw_pages, config=config)

    assert [_page_snapshot(page) for page in result.selected_pages] == [
        {"doc_id": "alpha", "page_number": 1, "chunk_ids": ["cover"]}
    ]
    assert result.suppressed_pages == []


def test_pass_b_uses_solver_subset_without_adding_new_pages() -> None:
    module = _load_page_attribution_module()
    config = module.PageAttributionConfig()

    result = module.finalize_page_attribution(
        answer="The tribunal dismissed the claim.",
        answer_type="free_text",
        raw_retrieved_chunk_pages=[PageReference(doc_id="alpha", page_numbers=[1, 3])],
        pass_a_pages=[PageReference(doc_id="alpha", page_numbers=[1, 3])],
        solver_reported_pages=[
            PageReference(doc_id="alpha", page_numbers=[3]),
            PageReference(doc_id="beta", page_numbers=[9]),
        ],
        supported_page_pairs={("alpha", 3)},
        answer_supported=True,
        is_no_answer=False,
        config=config,
    )

    assert [_ref_snapshot(reference) for reference in result.final_pages] == [
        {"doc_id": "alpha", "page_numbers": [3]}
    ]
    assert [_ref_snapshot(reference) for reference in result.accepted_solver_pages] == [
        {"doc_id": "alpha", "page_numbers": [3]}
    ]
    assert result.validation_action == "solver_subset"
    assert result.collapsed_answer is False


def test_pass_b_trims_unsupported_pages_before_collapsing_answer() -> None:
    module = _load_page_attribution_module()
    config = module.PageAttributionConfig()

    result = module.finalize_page_attribution(
        answer="The claim was dismissed on page 3.",
        answer_type="free_text",
        raw_retrieved_chunk_pages=[PageReference(doc_id="alpha", page_numbers=[1, 3])],
        pass_a_pages=[PageReference(doc_id="alpha", page_numbers=[1, 3])],
        solver_reported_pages=[],
        supported_page_pairs={("alpha", 3)},
        answer_supported=True,
        is_no_answer=False,
        config=config,
    )

    assert [_ref_snapshot(reference) for reference in result.final_pages] == [
        {"doc_id": "alpha", "page_numbers": [3]}
    ]
    assert result.validation_action == "trimmed_pages"
    assert result.collapsed_answer is False


def test_pass_b_emits_empty_pages_for_grounded_no_answer() -> None:
    module = _load_page_attribution_module()
    config = module.PageAttributionConfig()

    result = module.finalize_page_attribution(
        answer="There is no information on this question in the provided documents.",
        answer_type="free_text",
        raw_retrieved_chunk_pages=[PageReference(doc_id="alpha", page_numbers=[4])],
        pass_a_pages=[PageReference(doc_id="alpha", page_numbers=[4])],
        solver_reported_pages=[],
        supported_page_pairs=set(),
        answer_supported=False,
        is_no_answer=True,
        config=config,
    )

    assert result.final_pages == []
    assert result.validation_action == "no_answer_empty"
    assert result.collapsed_answer is False


def test_pass_b_strict_suppress_mode_preserves_legacy_collapse_behavior() -> None:
    module = _load_page_attribution_module()
    config = module.PageAttributionConfig(validation_mode="strict_suppress")

    result = module.finalize_page_attribution(
        answer="The fine is AED 250 and payable in 10 days.",
        answer_type="free_text",
        raw_retrieved_chunk_pages=[PageReference(doc_id="alpha", page_numbers=[2, 3])],
        pass_a_pages=[PageReference(doc_id="alpha", page_numbers=[2, 3])],
        solver_reported_pages=[],
        supported_page_pairs={("alpha", 2)},
        answer_supported=False,
        is_no_answer=False,
        config=config,
    )

    assert result.final_pages == []
    assert result.validation_action == "collapsed_answer"
    assert result.collapsed_answer is True


def test_pass_a_can_build_candidate_pages_from_retrieved_chunks() -> None:
    module = _load_page_attribution_module()
    chunks = [
        RetrievedChunk(
            chunk_id="c1",
            doc_id="alpha",
            page_span=[2, 3],
            chunk_type="clause",
            text="Clause 4. The fee is payable within 10 days.",
            retrieval_score=0.85,
            rerank_score=0.94,
        ),
        RetrievedChunk(
            chunk_id="c2",
            doc_id="alpha",
            page_span=[1],
            chunk_type="title",
            text="Service Agreement",
            retrieval_score=0.50,
            rerank_score=0.61,
        ),
    ]

    candidates = module.candidate_pages_from_chunks(chunks)

    assert [_page_snapshot(page) for page in candidates] == [
        {"doc_id": "alpha", "page_number": 2, "chunk_ids": ["c1"]},
        {"doc_id": "alpha", "page_number": 3, "chunk_ids": ["c1"]},
        {"doc_id": "alpha", "page_number": 1, "chunk_ids": ["c2"]},
    ]


def test_pass_a_mixed_content_page_prefers_substantive_text_over_marker_heavy_toc() -> None:
    module = _load_page_attribution_module()
    config = module.PageAttributionConfig()
    toc_text = (
        "Table of Contents Article 1 Scope Clause 2 Term Clause 3 Fees "
        "Section 4 Notices Clause 5 Payment"
    )
    substantive_text = "Clause 12. The respondent shall pay all awarded costs within 14 days."
    chunks = [
        RetrievedChunk(
            chunk_id="p1-toc",
            doc_id="alpha",
            page_span=[1],
            chunk_type="title",
            text=toc_text,
            retrieval_score=0.92,
            rerank_score=0.99,
        ),
        RetrievedChunk(
            chunk_id="p1-substantive",
            doc_id="alpha",
            page_span=[1],
            chunk_type="clause",
            text=substantive_text,
            retrieval_score=0.56,
            rerank_score=0.72,
        ),
        RetrievedChunk(
            chunk_id="p4-substantive",
            doc_id="alpha",
            page_span=[4],
            chunk_type="clause",
            text="Article 7. The claimant may recover tribunal fees and legal costs.",
            retrieval_score=0.83,
            rerank_score=0.96,
        ),
    ]

    candidates = module.candidate_pages_from_chunks(chunks)
    page_one_candidate = next(candidate for candidate in candidates if candidate.page_number == 1)
    result = module.prune_candidate_pages(candidates, config=config)

    assert page_one_candidate.text == substantive_text
    assert sorted((page.doc_id, page.page_number) for page in result.selected_pages) == [
        ("alpha", 1),
        ("alpha", 4),
    ]
    assert result.suppressed_pages == []


@pytest.mark.parametrize(
    "page_one_chunk_order",
    [
        ("p1-boilerplate", "p1-substantive"),
        ("p1-substantive", "p1-boilerplate"),
    ],
)
def test_pass_a_mixed_content_page_is_order_invariant(page_one_chunk_order: tuple[str, str]) -> None:
    module = _load_page_attribution_module()
    config = module.PageAttributionConfig()
    repeated_boilerplate = "ACME LLC Confidential Draft - Internal Circulation Only"
    chunk_by_id = {
        "p1-boilerplate": RetrievedChunk(
            chunk_id="p1-boilerplate",
            doc_id="alpha",
            page_span=[1],
            chunk_type="title",
            text=repeated_boilerplate,
            retrieval_score=0.88,
            rerank_score=0.90,
        ),
        "p1-substantive": RetrievedChunk(
            chunk_id="p1-substantive",
            doc_id="alpha",
            page_span=[1],
            chunk_type="clause",
            text="Clause 12. The respondent shall pay all awarded costs within 14 days.",
            retrieval_score=0.54,
            rerank_score=0.70,
        ),
        "p2-boilerplate": RetrievedChunk(
            chunk_id="p2-boilerplate",
            doc_id="alpha",
            page_span=[2],
            chunk_type="header",
            text=repeated_boilerplate,
            retrieval_score=0.68,
            rerank_score=0.74,
        ),
        "p4-substantive": RetrievedChunk(
            chunk_id="p4-substantive",
            doc_id="alpha",
            page_span=[4],
            chunk_type="clause",
            text="Article 7. The claimant may recover tribunal fees and legal costs.",
            retrieval_score=0.82,
            rerank_score=0.95,
        ),
        "p3-boilerplate": RetrievedChunk(
            chunk_id="p3-boilerplate",
            doc_id="alpha",
            page_span=[3],
            chunk_type="header",
            text=repeated_boilerplate,
            retrieval_score=0.63,
            rerank_score=0.69,
        ),
    }
    chunks = [
        chunk_by_id[page_one_chunk_order[0]],
        chunk_by_id[page_one_chunk_order[1]],
        chunk_by_id["p2-boilerplate"],
        chunk_by_id["p3-boilerplate"],
        chunk_by_id["p4-substantive"],
    ]

    candidates = module.candidate_pages_from_chunks(chunks)
    page_one_candidate = next(candidate for candidate in candidates if candidate.page_number == 1)
    result = module.prune_candidate_pages(candidates, config=config)

    assert page_one_candidate.text == "Clause 12. The respondent shall pay all awarded costs within 14 days."
    assert [(page.doc_id, page.page_number) for page in result.selected_pages] == [
        ("alpha", 4),
        ("alpha", 1),
    ]
    assert [(page.doc_id, page.page_number) for page in result.suppressed_pages] == [
        ("alpha", 2),
        ("alpha", 3),
    ]
