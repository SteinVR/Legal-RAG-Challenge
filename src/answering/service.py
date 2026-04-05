"""Extraction-first answering service orchestration."""

from __future__ import annotations

import logging

from src.common.runtime_logging import get_logger, log_event, questions_debug_enabled

from .service_helpers import *  # noqa: F401,F403
from .service_types import *  # noqa: F401,F403

LOGGER = get_logger("answering.service")

class AnsweringService:
    """Extraction-first answer routing with grounded free-text fallback."""

    def __init__(
        self,
        *,
        retriever: Retriever,
        provider: FreeTextProvider,
        reasoning_effort_by_type: Mapping[str, str] | None = None,
        confidence_threshold_by_type: Mapping[str, float] | None = None,
        page_attribution_config: PageAttributionConfig | None = None,
    ) -> None:
        """Execute `__init__`.

        Args:
            retriever: Input parameter.
            provider: Input parameter.
            reasoning_effort_by_type: Input parameter.
            confidence_threshold_by_type: Input parameter.
            page_attribution_config: Input parameter.

        Returns:
            None: This initializer does not return a value.
        """
        self._retriever = retriever
        self._provider = provider
        self._reasoning_effort_by_type = _normalize_reasoning_effort_map(reasoning_effort_by_type)
        self._confidence_threshold_by_type = _normalize_confidence_threshold_map(confidence_threshold_by_type)
        self._page_attribution_config = page_attribution_config or PageAttributionConfig()

    def answer_question(self, question: QuestionRecord) -> AnswerResult:
        """Execute `answer_question`.

        Args:
            question: Input parameter.

        Returns:
            Any: The computed result of the function.
        """
        query_metadata = extract_query_metadata(question.question)
        retrieval_output = self._retriever.retrieve(question, query_metadata=query_metadata)
        pages, retrieval_refs = _coerce_retrieval_payload(retrieval_output)
        raw_retrieval_refs = list(retrieval_refs) if retrieval_refs else _group_page_references(pages)
        pass_a_config = _effective_page_attribution_config(
            base_config=self._page_attribution_config,
            question_text=question.question,
        )
        pass_a_pages = _pass_a_pages_from_retrieval_payload(
            retrieval_output=retrieval_output,
            pages=pages,
            config=pass_a_config,
        )
        pass_a_refs = _group_page_references(pass_a_pages)

        try:
            answer_type = AnswerType(str(question.answer_type))
        except ValueError as exc:
            raise ValueError(f"Unsupported answer_type: {question.answer_type}") from exc

        if not pass_a_pages:
            if answer_type == AnswerType.FREE_TEXT:
                result = AnswerResult(
                    question_id=question.id,
                    answer=CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER,
                    confidence=0.0,
                    evidence_pages=[],
                    page_trace=build_page_trace(
                        raw_retrieved_chunk_pages=raw_retrieval_refs,
                        pass_a_pages=pass_a_refs,
                        solver_reported_pages=[],
                        final_emitted_pages=[],
                        validation_action="no_answer_empty",
                        collapsed_answer=False,
                    ),
                )
            else:
                result = _empty_result(
                    question_id=question.id,
                    page_trace=build_page_trace(
                        raw_retrieved_chunk_pages=raw_retrieval_refs,
                        pass_a_pages=pass_a_refs,
                        solver_reported_pages=[],
                        final_emitted_pages=[],
                        validation_action="no_answer_empty",
                        collapsed_answer=False,
                    ),
                )
        elif _supports_structured_provider(self._provider):
            result = self._answer_with_structured_solver(
                question=question,
                answer_type=answer_type,
                pages=pass_a_pages,
                raw_retrieval_refs=raw_retrieval_refs,
                pass_a_refs=pass_a_refs,
            )
            # Structured no-answer on free_text is intentionally treated as a
            # soft miss because the legacy generator often recovers it.
            if (
                answer_type == AnswerType.FREE_TEXT
                and result.answer == CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER
                and pass_a_pages
            ):
                result = self._answer_free_text(
                    question=question,
                    pages=pass_a_pages,
                    raw_retrieval_refs=raw_retrieval_refs,
                    pass_a_refs=pass_a_refs,
                )
        elif answer_type == AnswerType.FREE_TEXT:
            result = self._answer_free_text(
                question=question,
                pages=pass_a_pages,
                raw_retrieval_refs=raw_retrieval_refs,
                pass_a_refs=pass_a_refs,
            )
        else:
            solved = self._solve_deterministic(question=question, answer_type=answer_type, pages=pass_a_pages)
            if solved is None:
                result = _empty_result(
                    question_id=question.id,
                    page_trace=build_page_trace(
                        raw_retrieved_chunk_pages=raw_retrieval_refs,
                        pass_a_pages=pass_a_refs,
                        solver_reported_pages=[],
                        final_emitted_pages=[],
                        validation_action="no_answer_empty",
                        collapsed_answer=False,
                    ),
                )
            else:
                supported_refs = _group_page_references(solved.supporting_pages)
                finalized = finalize_page_attribution(
                    answer=solved.answer,
                    answer_type=answer_type.value,
                    raw_retrieved_chunk_pages=raw_retrieval_refs,
                    pass_a_pages=pass_a_refs,
                    solver_reported_pages=[],
                    supported_page_pairs=flatten_page_references(supported_refs),
                    answer_supported=True,
                    is_no_answer=False,
                    config=self._page_attribution_config,
                )
                result = AnswerResult(
                    question_id=question.id,
                    answer=solved.answer,
                    confidence=1.0,
                    evidence_pages=finalized.final_pages,
                    page_trace=build_page_trace(
                        raw_retrieved_chunk_pages=raw_retrieval_refs,
                        pass_a_pages=pass_a_refs,
                        solver_reported_pages=[],
                        final_emitted_pages=finalized.final_pages,
                        validation_action=finalized.validation_action,
                        collapsed_answer=finalized.collapsed_answer,
                    ),
                )

        if questions_debug_enabled():
            log_event(
                LOGGER,
                logging.DEBUG,
                "answer.complete",
                "Answering completed for question.",
                stage="answering",
                question_id=question.id,
                answer_type=question.answer_type,
                evidence_page_count=len(result.evidence_pages),
                answered=result.answer is not None,
                confidence=result.confidence,
            )
        return result

    def _answer_with_structured_solver(
        self,
        *,
        question: QuestionRecord,
        answer_type: AnswerType,
        pages: list[_PageCandidate],
        raw_retrieval_refs: list[PageReference],
        pass_a_refs: list[PageReference],
    ) -> AnswerResult:
        """Execute `_answer_with_structured_solver`.

        Args:
            question: Input parameter.
            answer_type: Input parameter.
            pages: Input parameter.
            raw_retrieval_refs: Input parameter.
            pass_a_refs: Input parameter.

        Returns:
            Any: The computed result of the function.
        """
        provider = cast(StructuredProvider, self._provider)
        answer_schema = ANSWER_SCHEMA_REGISTRY[answer_type.value]
        reasoning_effort = self._reasoning_effort_by_type[answer_type.value]
        evidence_pages = [_provider_evidence_page(page) for page in pages]
        response = provider.generate_structured(
            question=question.question,
            answer_type=answer_type.value,
            evidence_pages=evidence_pages,
            answer_schema=answer_schema,
            reasoning_effort=reasoning_effort,
        )
        try:
            validated_response = answer_schema.model_validate(dict(response))
        except ValidationError as exc:
            raise ValueError(
                f"Structured provider response failed schema validation for answer_type={answer_type.value}."
            ) from exc

        confidence = _coerce_confidence(response.get("confidence", 0.0), default=0.0)
        provider_model_name = _resolve_provider_model_name(self._provider)
        base_refs = list(pass_a_refs)
        relevant_pages = _normalize_relevant_page_list(getattr(validated_response, "relevant_pages", []))
        relevant_pages = _prefer_issue_date_relevant_pages(
            question_text=question.question,
            answer_type=answer_type,
            pages=pages,
            relevant_pages=relevant_pages,
        )
        supporting_pages = pages
        supporting_refs = base_refs
        narrowed_refs: list[PageReference] = []
        if relevant_pages:
            allowed_pairs = _safe_relevant_page_pairs(pages=pages, relevant_pages=relevant_pages)
            if allowed_pairs:
                supporting_pages = _filter_pages_by_pairs(pages, allowed_pairs, require_full_span=True)
                narrowed_refs = _group_page_references(supporting_pages)
                supporting_refs = narrowed_refs
        supported_page_pairs = flatten_page_references(supporting_refs)

        is_answerable = bool(getattr(validated_response, "is_answerable", False))
        final_answer = getattr(validated_response, "final_answer", None)
        if final_answer is not None and answer_type == AnswerType.NAME:
            final_answer = _clean_verbose_name_answer(str(final_answer))
        if not is_answerable:
            finalized = finalize_page_attribution(
                answer=final_answer,
                answer_type=answer_type.value,
                raw_retrieved_chunk_pages=raw_retrieval_refs,
                pass_a_pages=pass_a_refs,
                solver_reported_pages=narrowed_refs,
                supported_page_pairs=set(),
                answer_supported=False,
                is_no_answer=True,
                config=self._page_attribution_config,
            )
            if answer_type == AnswerType.FREE_TEXT:
                return AnswerResult(
                    question_id=question.id,
                    answer=CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER,
                    confidence=confidence,
                    evidence_pages=finalized.final_pages,
                    page_trace=build_page_trace(
                        raw_retrieved_chunk_pages=raw_retrieval_refs,
                        pass_a_pages=pass_a_refs,
                        solver_reported_pages=narrowed_refs,
                        final_emitted_pages=finalized.final_pages,
                        validation_action=finalized.validation_action,
                        collapsed_answer=finalized.collapsed_answer,
                    ),
                    model_name=provider_model_name,
                )
            return _empty_result(
                question_id=question.id,
                model_name=provider_model_name,
                page_trace=build_page_trace(
                    raw_retrieved_chunk_pages=raw_retrieval_refs,
                    pass_a_pages=pass_a_refs,
                    solver_reported_pages=narrowed_refs,
                    final_emitted_pages=finalized.final_pages,
                    validation_action=finalized.validation_action,
                    collapsed_answer=finalized.collapsed_answer,
                ),
            )

        if final_answer is None:
            return _empty_result(
                question_id=question.id,
                model_name=provider_model_name,
                page_trace=build_page_trace(
                    raw_retrieved_chunk_pages=raw_retrieval_refs,
                    pass_a_pages=pass_a_refs,
                    solver_reported_pages=narrowed_refs,
                    final_emitted_pages=[],
                    validation_action="collapsed_answer",
                    collapsed_answer=True,
                ),
            )

        threshold = self._confidence_threshold_by_type[answer_type.value]
        if confidence < threshold:
            finalized = finalize_page_attribution(
                answer=final_answer,
                answer_type=answer_type.value,
                raw_retrieved_chunk_pages=raw_retrieval_refs,
                pass_a_pages=pass_a_refs,
                solver_reported_pages=narrowed_refs,
                supported_page_pairs=set(),
                answer_supported=False,
                is_no_answer=True,
                config=self._page_attribution_config,
            )
            if answer_type == AnswerType.FREE_TEXT:
                return AnswerResult(
                    question_id=question.id,
                    answer=CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER,
                    confidence=0.0,
                    evidence_pages=finalized.final_pages,
                    page_trace=build_page_trace(
                        raw_retrieved_chunk_pages=raw_retrieval_refs,
                        pass_a_pages=pass_a_refs,
                        solver_reported_pages=narrowed_refs,
                        final_emitted_pages=finalized.final_pages,
                        validation_action=finalized.validation_action,
                        collapsed_answer=finalized.collapsed_answer,
                    ),
                    model_name=provider_model_name,
                )
            return _empty_result(
                question_id=question.id,
                model_name=provider_model_name,
                page_trace=build_page_trace(
                    raw_retrieved_chunk_pages=raw_retrieval_refs,
                    pass_a_pages=pass_a_refs,
                    solver_reported_pages=narrowed_refs,
                    final_emitted_pages=finalized.final_pages,
                    validation_action=finalized.validation_action,
                    collapsed_answer=finalized.collapsed_answer,
                ),
            )

        if answer_type == AnswerType.FREE_TEXT:
            answer = _normalize_whitespace(str(final_answer))
            if len(answer) > 280:
                raise ValueError("free_text answers must be at most 280 characters.")
            supported_page_pairs = _supported_page_pairs_for_free_text(answer=answer, pages=supporting_pages)
            answer_supported = bool(supported_page_pairs)
            finalized = finalize_page_attribution(
                answer=answer,
                answer_type=answer_type.value,
                raw_retrieved_chunk_pages=raw_retrieval_refs,
                pass_a_pages=pass_a_refs,
                solver_reported_pages=narrowed_refs,
                supported_page_pairs=supported_page_pairs,
                answer_supported=answer_supported,
                is_no_answer=False,
                config=self._page_attribution_config,
            )
            return AnswerResult(
                question_id=question.id,
                answer=CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER if finalized.collapsed_answer else answer,
                confidence=confidence,
                evidence_pages=finalized.final_pages,
                page_trace=build_page_trace(
                    raw_retrieved_chunk_pages=raw_retrieval_refs,
                    pass_a_pages=pass_a_refs,
                    solver_reported_pages=narrowed_refs,
                    final_emitted_pages=finalized.final_pages,
                    validation_action=finalized.validation_action,
                    collapsed_answer=finalized.collapsed_answer,
                ),
                model_name=provider_model_name,
            )

        answer_supported = bool(supporting_pages) and _passes_typed_guardrails(
            answer_type=answer_type,
            question=question.question,
            proposed_answer=final_answer,
            pages=supporting_pages,
        )
        finalized = finalize_page_attribution(
            answer=final_answer,
            answer_type=answer_type.value,
            raw_retrieved_chunk_pages=raw_retrieval_refs,
            pass_a_pages=pass_a_refs,
            solver_reported_pages=narrowed_refs,
            supported_page_pairs=supported_page_pairs if answer_supported else set(),
            answer_supported=answer_supported,
            is_no_answer=False,
            config=self._page_attribution_config,
        )
        if finalized.collapsed_answer:
            return _empty_result(
                question_id=question.id,
                model_name=provider_model_name,
                page_trace=build_page_trace(
                    raw_retrieved_chunk_pages=raw_retrieval_refs,
                    pass_a_pages=pass_a_refs,
                    solver_reported_pages=narrowed_refs,
                    final_emitted_pages=finalized.final_pages,
                    validation_action=finalized.validation_action,
                    collapsed_answer=finalized.collapsed_answer,
                ),
            )

        return AnswerResult(
            question_id=question.id,
            answer=final_answer,
            confidence=confidence,
            evidence_pages=finalized.final_pages,
            page_trace=build_page_trace(
                raw_retrieved_chunk_pages=raw_retrieval_refs,
                pass_a_pages=pass_a_refs,
                solver_reported_pages=narrowed_refs,
                final_emitted_pages=finalized.final_pages,
                validation_action=finalized.validation_action,
                collapsed_answer=finalized.collapsed_answer,
            ),
            model_name=provider_model_name,
        )

    def _solve_deterministic(
        self,
        *,
        question: QuestionRecord,
        answer_type: AnswerType,
        pages: list[_PageCandidate],
    ) -> _SolvedAnswer | None:
        """Execute `_solve_deterministic`.

        Args:
            question: Input parameter.
            answer_type: Input parameter.
            pages: Input parameter.

        Returns:
            Any: The computed result of the function.
        """
        question_tokens = _keyword_tokens(question.question)
        per_answer: dict[str, tuple[Any, list[_PageCandidate]]] = {}
        extractor = _get_deterministic_extractor(answer_type)
        prefer_law_number = answer_type == AnswerType.NUMBER and _is_law_number_question(question.question)

        for page in pages:
            if answer_type == AnswerType.NUMBER:
                candidate = extractor(
                    page=page,
                    question_tokens=question_tokens,
                    prefer_law_number=prefer_law_number,
                )
            else:
                candidate = extractor(page=page, question_tokens=question_tokens)

            if candidate is None:
                continue

            key = _answer_key(candidate.answer)
            stored = per_answer.get(key)
            if stored is None:
                per_answer[key] = (candidate.answer, list(candidate.supporting_pages))
                continue

            _, existing_pages = stored
            existing_pages.extend(candidate.supporting_pages)

        if len(per_answer) != 1:
            return None

        answer, supporting_pages = next(iter(per_answer.values()))
        return _SolvedAnswer(answer=answer, supporting_pages=_dedupe_pages(supporting_pages))

    def _answer_free_text(
        self,
        *,
        question: QuestionRecord,
        pages: list[_PageCandidate],
        raw_retrieval_refs: list[PageReference],
        pass_a_refs: list[PageReference],
    ) -> AnswerResult:
        """Execute `_answer_free_text`.

        Args:
            question: Input parameter.
            pages: Input parameter.
            raw_retrieval_refs: Input parameter.
            pass_a_refs: Input parameter.

        Returns:
            Any: The computed result of the function.
        """
        if not pages:
            return AnswerResult(
                question_id=question.id,
                answer=CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER,
                confidence=0.0,
                evidence_pages=[],
                page_trace=build_page_trace(
                    raw_retrieved_chunk_pages=raw_retrieval_refs,
                    pass_a_pages=pass_a_refs,
                    solver_reported_pages=[],
                    final_emitted_pages=[],
                    validation_action="no_answer_empty",
                    collapsed_answer=False,
                ),
            )

        evidence_pages = [
            _provider_evidence_page(page)
            for page in pages
        ]
        response = self._provider.generate(
            question=question.question,
            evidence_pages=evidence_pages,
            max_chars=280,
        )

        answer = _normalize_whitespace(str(response.get("answer", "")))
        if not answer:
            raise ValueError("Provider returned an empty free_text answer.")
        if len(answer) > 280:
            raise ValueError("free_text answers must be at most 280 characters.")

        confidence = _validate_provider_confidence(response.get("confidence", 0.0))
        supported_page_pairs = _supported_page_pairs_for_free_text(answer=answer, pages=pages)
        answer_supported = bool(supported_page_pairs)
        finalized = finalize_page_attribution(
            answer=answer,
            answer_type=AnswerType.FREE_TEXT.value,
            raw_retrieved_chunk_pages=raw_retrieval_refs,
            pass_a_pages=pass_a_refs,
            solver_reported_pages=[],
            supported_page_pairs=supported_page_pairs,
            answer_supported=answer_supported,
            is_no_answer=False,
            config=self._page_attribution_config,
        )
        return AnswerResult(
            question_id=question.id,
            answer=CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER if finalized.collapsed_answer else answer,
            confidence=confidence,
            evidence_pages=finalized.final_pages,
            page_trace=build_page_trace(
                raw_retrieved_chunk_pages=raw_retrieval_refs,
                pass_a_pages=pass_a_refs,
                solver_reported_pages=[],
                final_emitted_pages=finalized.final_pages,
                validation_action=finalized.validation_action,
                collapsed_answer=finalized.collapsed_answer,
            ),
            model_name=_resolve_provider_model_name(self._provider),
        )
