"""Two-pass page attribution helpers for W4A grounding precision."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal

from src.evaluation.contracts import PageReference
from src.retrieval.service import RetrievedChunk

ValidationMode = Literal["degrade_first", "strict_suppress"]

_LEGAL_MARKER_PATTERN = re.compile(
    r"\b(?:article|clause|section|schedule|tribunal|court|claim|claimant|respondent|agreement|shall|must|may)\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class PageAttributionConfig:
    pass_a_enabled: bool = True
    suppress_title_pages: bool = True
    suppress_repeated_boilerplate: bool = True
    validation_mode: ValidationMode = "degrade_first"
    emit_empty_pages_for_no_answer: bool = True
    allow_solver_page_narrowing: bool = True


@dataclass(slots=True)
class CandidatePage:
    doc_id: str
    page_number: int
    text: str
    chunk_ids: list[str] = field(default_factory=list)
    best_retrieval_score: float = 0.0
    best_rerank_score: float | None = None


@dataclass(slots=True)
class PassAResult:
    selected_pages: list[CandidatePage] = field(default_factory=list)
    suppressed_pages: list[CandidatePage] = field(default_factory=list)


@dataclass(slots=True)
class FinalizedPageAttribution:
    final_pages: list[PageReference] = field(default_factory=list)
    accepted_solver_pages: list[PageReference] = field(default_factory=list)
    validation_action: str = "preserved_pages"
    collapsed_answer: bool = False


@dataclass(slots=True)
class PageAttributionTrace:
    raw_retrieved_chunk_pages: list[PageReference] = field(default_factory=list)
    pass_a_pages: list[PageReference] = field(default_factory=list)
    solver_reported_pages: list[PageReference] = field(default_factory=list)
    final_emitted_pages: list[PageReference] = field(default_factory=list)
    validation_action: str = "preserved_pages"
    collapsed_answer: bool = False


def candidate_pages_from_chunks(chunks: Iterable[RetrievedChunk]) -> list[CandidatePage]:
    pages_by_key: OrderedDict[tuple[str, int], CandidatePage] = OrderedDict()
    best_text_rank_by_key: dict[tuple[str, int], tuple[int, int, float, float, int, str]] = {}
    for chunk in chunks:
        for raw_page in chunk.page_span:
            page_number = int(raw_page)
            if page_number <= 0:
                continue
            key = (chunk.doc_id, page_number)
            candidate = pages_by_key.setdefault(
                key,
                CandidatePage(
                    doc_id=chunk.doc_id,
                    page_number=page_number,
                    text=chunk.text,
                ),
            )
            text_rank = _suppression_text_rank(
                text=chunk.text,
                page_number=page_number,
                retrieval_score=float(chunk.retrieval_score),
                rerank_score=None if chunk.rerank_score is None else float(chunk.rerank_score),
            )
            current_text_rank = best_text_rank_by_key.get(key)
            if current_text_rank is None or text_rank > current_text_rank:
                candidate.text = chunk.text
                best_text_rank_by_key[key] = text_rank
            if chunk.chunk_id not in candidate.chunk_ids:
                candidate.chunk_ids.append(chunk.chunk_id)
            candidate.best_retrieval_score = max(candidate.best_retrieval_score, float(chunk.retrieval_score))
            if chunk.rerank_score is not None:
                if candidate.best_rerank_score is None:
                    candidate.best_rerank_score = float(chunk.rerank_score)
                else:
                    candidate.best_rerank_score = max(candidate.best_rerank_score, float(chunk.rerank_score))

    return sorted(
        pages_by_key.values(),
        key=lambda page: (
            -(page.best_rerank_score if page.best_rerank_score is not None else float("-inf")),
            -page.best_retrieval_score,
            page.doc_id,
            page.page_number,
        ),
    )


def prune_candidate_pages(raw_pages: list[CandidatePage], *, config: PageAttributionConfig) -> PassAResult:
    if not raw_pages:
        return PassAResult()
    if not config.pass_a_enabled:
        return PassAResult(selected_pages=list(raw_pages), suppressed_pages=[])

    strongest_page_by_doc: dict[str, CandidatePage] = {}
    for page in raw_pages:
        current = strongest_page_by_doc.get(page.doc_id)
        if current is None or _page_rank(page) > _page_rank(current):
            strongest_page_by_doc[page.doc_id] = page

    repeated_texts = Counter((page.doc_id, _normalized_text(page.text)) for page in raw_pages)
    strongest_non_boilerplate_by_doc: dict[str, CandidatePage] = {}
    for page in raw_pages:
        if _is_boilerplate_candidate(page, repeated_texts=repeated_texts, config=config):
            continue
        current = strongest_non_boilerplate_by_doc.get(page.doc_id)
        if current is None or _page_rank(page) > _page_rank(current):
            strongest_non_boilerplate_by_doc[page.doc_id] = page

    selected_pages: list[CandidatePage] = []
    suppressed_pages: list[CandidatePage] = []

    for page in raw_pages:
        strongest_page = strongest_page_by_doc[page.doc_id]
        preferred_anchor = strongest_non_boilerplate_by_doc.get(page.doc_id, strongest_page)
        allow_strongest_suppression = (
            page is strongest_page
            and page is not preferred_anchor
        )
        suppress = False
        if page is not strongest_page or allow_strongest_suppression:
            shares_chunk_with_anchor = _shares_chunk(page, preferred_anchor)
            if (
                _is_repeated_boilerplate_candidate(page, repeated_texts=repeated_texts, config=config)
                and not shares_chunk_with_anchor
            ):
                suppress = True
            elif _is_title_candidate(page, config=config):
                suppress = True

        if suppress:
            suppressed_pages.append(page)
        else:
            selected_pages.append(page)

    if not selected_pages:
        strongest_page = strongest_page_by_doc[raw_pages[0].doc_id]
        return PassAResult(selected_pages=[strongest_page], suppressed_pages=[])

    return PassAResult(selected_pages=selected_pages, suppressed_pages=suppressed_pages)


def finalize_page_attribution(
    *,
    answer: Any,
    answer_type: str,
    raw_retrieved_chunk_pages: list[PageReference],
    pass_a_pages: list[PageReference],
    solver_reported_pages: list[PageReference],
    supported_page_pairs: set[tuple[str, int]],
    answer_supported: bool,
    is_no_answer: bool,
    config: PageAttributionConfig,
) -> FinalizedPageAttribution:
    del answer, answer_type

    candidate_pairs = flatten_page_references(pass_a_pages or raw_retrieved_chunk_pages)
    accepted_solver_pairs = (
        candidate_pairs & flatten_page_references(solver_reported_pages)
        if config.allow_solver_page_narrowing
        else set()
    )
    accepted_solver_pages = group_page_reference_pairs(accepted_solver_pairs)

    if is_no_answer and config.emit_empty_pages_for_no_answer:
        return FinalizedPageAttribution(
            final_pages=[],
            accepted_solver_pages=accepted_solver_pages,
            validation_action="no_answer_empty",
            collapsed_answer=False,
        )

    if config.validation_mode == "strict_suppress" and not answer_supported:
        return FinalizedPageAttribution(
            final_pages=[],
            accepted_solver_pages=accepted_solver_pages,
            validation_action="collapsed_answer",
            collapsed_answer=True,
        )

    if accepted_solver_pairs:
        return FinalizedPageAttribution(
            final_pages=accepted_solver_pages,
            accepted_solver_pages=accepted_solver_pages,
            validation_action="solver_subset",
            collapsed_answer=False,
        )

    supported_pairs = candidate_pairs & supported_page_pairs if supported_page_pairs else set()
    if supported_pairs and supported_pairs != candidate_pairs:
        return FinalizedPageAttribution(
            final_pages=group_page_reference_pairs(supported_pairs),
            accepted_solver_pages=[],
            validation_action="trimmed_pages",
            collapsed_answer=False,
        )

    if answer_supported or (candidate_pairs and is_no_answer):
        return FinalizedPageAttribution(
            final_pages=group_page_reference_pairs(candidate_pairs),
            accepted_solver_pages=[],
            validation_action="preserved_pages" if answer_supported else "trimmed_pages",
            collapsed_answer=False,
        )

    return FinalizedPageAttribution(
        final_pages=[],
        accepted_solver_pages=[],
        validation_action="collapsed_answer",
        collapsed_answer=True,
    )


def group_page_reference_pairs(page_pairs: Iterable[tuple[str, int]]) -> list[PageReference]:
    pages_by_doc: OrderedDict[str, list[int]] = OrderedDict()
    seen: dict[str, set[int]] = {}
    for doc_id, page_number in sorted(page_pairs, key=lambda item: (item[0], item[1])):
        existing = pages_by_doc.setdefault(doc_id, [])
        seen_pages = seen.setdefault(doc_id, set())
        if page_number in seen_pages:
            continue
        seen_pages.add(page_number)
        existing.append(page_number)

    return [PageReference(doc_id=doc_id, page_numbers=page_numbers) for doc_id, page_numbers in pages_by_doc.items()]


def flatten_page_references(references: Iterable[PageReference]) -> set[tuple[str, int]]:
    flattened: set[tuple[str, int]] = set()
    for reference in references:
        for page_number in reference.page_numbers:
            flattened.add((reference.doc_id, int(page_number)))
    return flattened


def build_page_trace(
    *,
    raw_retrieved_chunk_pages: list[PageReference],
    pass_a_pages: list[PageReference],
    solver_reported_pages: list[PageReference],
    final_emitted_pages: list[PageReference],
    validation_action: str,
    collapsed_answer: bool,
) -> PageAttributionTrace:
    return PageAttributionTrace(
        raw_retrieved_chunk_pages=list(raw_retrieved_chunk_pages),
        pass_a_pages=list(pass_a_pages),
        solver_reported_pages=list(solver_reported_pages),
        final_emitted_pages=list(final_emitted_pages),
        validation_action=validation_action,
        collapsed_answer=collapsed_answer,
    )


def _page_rank(page: CandidatePage) -> tuple[float, float]:
    return (
        page.best_rerank_score if page.best_rerank_score is not None else float("-inf"),
        page.best_retrieval_score,
    )


def _is_title_candidate(page: CandidatePage, *, config: PageAttributionConfig) -> bool:
    return config.suppress_title_pages and _looks_like_title_page(page)


def _is_repeated_boilerplate_candidate(
    page: CandidatePage,
    *,
    repeated_texts: Counter[tuple[str, str]],
    config: PageAttributionConfig,
) -> bool:
    return (
        config.suppress_repeated_boilerplate
        and repeated_texts[(page.doc_id, _normalized_text(page.text))] > 1
    )


def _is_boilerplate_candidate(
    page: CandidatePage,
    *,
    repeated_texts: Counter[tuple[str, str]],
    config: PageAttributionConfig,
) -> bool:
    return _is_title_candidate(page, config=config) or _is_repeated_boilerplate_candidate(
        page,
        repeated_texts=repeated_texts,
        config=config,
    )


def _shares_chunk(left: CandidatePage, right: CandidatePage) -> bool:
    return bool(set(left.chunk_ids) & set(right.chunk_ids))


def _looks_like_title_page(page: CandidatePage) -> bool:
    if page.page_number != 1:
        return False
    normalized = _normalized_text(page.text)
    marker_count = len(_LEGAL_MARKER_PATTERN.findall(page.text))
    return marker_count <= 1 or "table of contents" in normalized


def _suppression_text_rank(
    *,
    text: str,
    page_number: int,
    retrieval_score: float,
    rerank_score: float | None,
) -> tuple[int, int, float, float, int, str]:
    """Prefer substantive text so suppression is stable for mixed-content pages."""

    normalized = _normalized_text(text)
    marker_count = len(_LEGAL_MARKER_PATTERN.findall(text))
    looks_like_title = page_number == 1 and (marker_count <= 1 or "table of contents" in normalized)
    return (
        0 if looks_like_title else 1,
        marker_count,
        rerank_score if rerank_score is not None else float("-inf"),
        retrieval_score,
        len(normalized),
        normalized,
    )


def _normalized_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()
