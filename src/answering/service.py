"""Answer routing and extraction-first solving."""

from __future__ import annotations

import logging
import math
import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from src.answering.page_attribution import PageAttributionTrace, build_page_trace
from src.common.runtime_logging import get_logger, log_event, questions_debug_enabled
from src.common.schemas import QuestionRecord
from src.evaluation.contracts import AnswerType, PageReference
from src.providers.base import FreeTextProvider
from src.retrieval.service import RetrievalResult

CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER = "There is no information on this question in the provided documents."
LOGGER = get_logger("answering.service")
SCHEMA_FIRST_ANSWER_TYPES: frozenset[AnswerType] = frozenset(
    {
        AnswerType.BOOLEAN,
        AnswerType.NUMBER,
        AnswerType.NAME,
        AnswerType.NAMES,
        AnswerType.DATE,
        AnswerType.FREE_TEXT,
    }
)
DEFAULT_REASONING_EFFORT_BY_TYPE: dict[str, str] = {
    AnswerType.BOOLEAN.value: "high",
    AnswerType.NUMBER.value: "medium",
    AnswerType.NAME.value: "high",
    AnswerType.NAMES.value: "high",
    AnswerType.DATE.value: "medium",
    AnswerType.FREE_TEXT.value: "medium",
}
DEFAULT_CONFIDENCE_THRESHOLD_BY_TYPE: dict[str, float] = {
    AnswerType.BOOLEAN.value: 0.7,
    AnswerType.NUMBER.value: 0.55,
    AnswerType.NAME.value: 0.75,
    AnswerType.NAMES.value: 0.75,
    AnswerType.DATE.value: 0.6,
    AnswerType.FREE_TEXT.value: 0.5,
}


class FreeTextGroundingValidationError(ValueError):
    """Raised when a generated free-text answer is unsupported by the evidence."""


_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "do",
    "does",
    "for",
    "how",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "when",
    "who",
}
_NUMBER_PATTERN = re.compile(r"(?<!\w)(?:[A-Z]{2,5}\s*)?[-+]?\d[\d,]*(?:\.\d+)?(?!\w)")
_DATE_PATTERN = re.compile(
    r"(?<!\d)(?P<day>\d{1,2})\s+(?P<month>"
    + "|".join(_MONTHS)
    + r")\s+(?P<year>\d{4})(?!\d)",
    re.IGNORECASE,
)
_MONTH_FIRST_DATE_PATTERN = re.compile(
    r"(?<!\d)(?P<month>"
    + "|".join(_MONTHS)
    + r")\s+(?P<day>\d{1,2})(?:,\s*|\s+)(?P<year>\d{4})(?!\d)",
    re.IGNORECASE,
)
_ISO_DATE_PATTERN = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_NAME_PATTERN = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b")
_UPPER_ENTITY_PATTERN = re.compile(r"\b[A-Z][A-Z0-9&'/-]*(?:\.?\s+[A-Z][A-Z0-9&'/-]*)+\.?\b")
_ENTITY_LIST_ITEM_PATTERN = re.compile(
    r"\b(?:[A-Z]{2,}[A-Z0-9&'/-]*|[A-Z][a-z][A-Za-z0-9&'/-]*)(?:\.?\s+[A-Z][A-Za-z0-9&'/-]*)*\.?\b"
)
_BOOLEAN_NEGATIVE = (
    "not permitted",
    "not allowed",
    "prohibited",
    "forbidden",
    "must not",
    "shall not",
    "cannot",
    "may not",
)
_BOOLEAN_POSITIVE = (
    "permitted",
    "allowed",
    "may",
    "can",
    "shall",
    "must",
)
_PERMISSION_QUESTION_HINTS = frozenset(
    {
        "allow",
        "allowed",
        "allows",
        "can",
        "forbid",
        "forbidden",
        "forbids",
        "may",
        "permit",
        "permitted",
        "permits",
        "prohibit",
        "prohibited",
        "prohibits",
    }
)
_OBLIGATION_QUESTION_HINTS = frozenset(
    {
        "must",
        "obligation",
        "obligations",
        "obliged",
        "require",
        "required",
        "requires",
        "shall",
    }
)
_BOOLEAN_NO_PERMISSION_PATTERN = re.compile(
    r"\bno\s+\w+(?:\s+\w+){0,4}\s+(?:is|are|was|were)\s+(?:permitted|allowed)\b",
    re.IGNORECASE,
)
_BOOLEAN_NO_MODAL_PATTERN = re.compile(
    r"\bno\s+\w+(?:\s+\w+){0,4}\s+(?:may|can|shall|must)\b",
    re.IGNORECASE,
)
_TEMPORAL_UNITS = ("day", "days", "week", "weeks", "month", "months", "year", "years", "hour", "hours")
_DURATION_QUESTION_HINTS = frozenset(_TEMPORAL_UNITS) | {
    "deadline",
    "duration",
    "period",
    "time",
    "within",
    "long",
    "response",
    "payment",
    "payable",
}
_AMOUNT_CUE_PATTERN = re.compile(r"\b(?:aed|usd|eur|fine|amount|price|cost|penalty|fee)\b", re.IGNORECASE)
_TEMPORAL_CUE_PATTERN = re.compile(
    r"\b(?:days?|weeks?|months?|years?|hours?|deadline|within|after|before)\b",
    re.IGNORECASE,
)
_LEGAL_OUTCOME_PATTERNS = {
    "dismiss": re.compile(r"\bdismiss(?:ed|es|ing)?\b"),
    "grant": re.compile(r"\bgrant(?:ed|s|ing)?\b"),
    "deny": re.compile(r"\bden(?:y|ied|ies|ying)\b"),
    "allow": re.compile(r"\ballow(?:ed|s|ing)?\b"),
    "prohibit": re.compile(r"\bprohibit(?:ed|s|ing)?\b"),
    "terminate": re.compile(r"\bterminat(?:e|ed|es|ing)\b"),
    "order": re.compile(r"\border(?:ed|s|ing)?\b"),
    "pay": re.compile(r"\bpay(?:able|ment|ments|ing|s)?\b"),
    "liable": re.compile(r"\bliab(?:ility|le)\b"),
}
_WORD_NUMBER_VALUES = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
_WORD_NUMBER_SCALES = {
    "hundred": 100,
    "thousand": 1000,
}
_WORD_NUMBER_TOKENS = frozenset(_WORD_NUMBER_VALUES) | frozenset(_WORD_NUMBER_SCALES) | {"and"}
_CONTRACT_ENTITY_PATTERN = re.compile(r"\b(?:contract|agreement)\b")
_LEGAL_ROLE_PATTERN = re.compile(
    r"\b(?:respondent|claimant|appellant|petitioner|defendant|plaintiff|party|parties|seller|buyer|"
    r"landlord|tenant|employer|employee|liquidator|lessor|lessee|borrower|lender|guarantor|"
    r"insured|insurer|contractor|subcontractor)\b",
    re.IGNORECASE,
)
_ROLE_ENTITY_EXTRACTOR = re.compile(
    r"\b(?:the\s+)?(?:respondent|claimant|appellant|petitioner|defendant|plaintiff|party|parties|seller|buyer|"
    r"landlord|tenant|employer|employee|liquidator|lessor|lessee|borrower|lender|guarantor|"
    r"insured|insurer|contractor|subcontractor)\b"
    r"\s*(?::|(?:is|was|are|were|means|named|identified\s+as|shall\s+be))\s*"
    r"(?P<entities>[^.;:\n]+)",
    re.IGNORECASE,
)
_SINGLE_TOKEN_ENTITY_EXCLUSIONS = {
    "The",
    "This",
    "That",
    "These",
    "Those",
    "Schedule",
    "Article",
    "Section",
    "Clause",
    "Agreement",
    "Contract",
}
_CASE_ID_PATTERN = re.compile(
    r"\bcase\s*(?:no\.?|number)?\s*(?P<case_id>\d{1,4}\s*/\s*\d{2,4})\b",
    re.IGNORECASE,
)
_STATUTE_ID_PATTERN = re.compile(
    r"\b(?P<statute>(?:[A-Z]{2,}\s+)?[A-Za-z]+(?:\s+[A-Za-z]+){0,3}\s+Law)\b"
)
_DOCUMENT_TITLE_CUE_PATTERN = re.compile(
    r"\b(?P<title>[A-Z][A-Za-z0-9'&/-]*(?:\s+[A-Z][A-Za-z0-9'&/-]*)*\s+"
    r"(?:Agreement|Contract|Deed|Order|Policy|Protocol|Arrangement|Lease))\b"
)
_MULTI_DOCUMENT_SIGNAL_PATTERN = re.compile(
    r"\b(across|between|both|related\s+matters?|related\s+cases?|multiple|versus|vs\.?)\b",
    re.IGNORECASE,
)


class _StructuredAnswerBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_answerable: bool
    relevant_pages: list[int] = Field(default_factory=list)
    reasoning_summary: str
    confidence: float | None = None

    @field_validator("relevant_pages", mode="before")
    @classmethod
    def _normalize_relevant_pages(cls, value: Any) -> list[int]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("relevant_pages must be a list of integers.")
        normalized: list[int] = []
        for raw_page in value:
            try:
                page_number = int(raw_page)
            except (TypeError, ValueError) as exc:
                raise ValueError("relevant_pages must contain integers.") from exc
            if page_number > 0:
                normalized.append(page_number)
        return sorted(set(normalized))

    @field_validator("reasoning_summary")
    @classmethod
    def _validate_reasoning_summary(cls, value: str) -> str:
        normalized = _normalize_whitespace(str(value))
        if not normalized:
            raise ValueError("reasoning_summary must be non-empty.")
        return normalized

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, value: float | None) -> float | None:
        if value is None:
            return value
        if not math.isfinite(value) or value < 0.0 or value > 1.0:
            raise ValueError("confidence must be finite and between 0 and 1.")
        return value


class BooleanAnswerSchema(_StructuredAnswerBase):
    final_answer: bool | None

    @model_validator(mode="after")
    def _validate_answerable_contract(self) -> "BooleanAnswerSchema":
        if self.is_answerable != (self.final_answer is not None):
            raise ValueError("boolean final_answer must be null iff is_answerable=false.")
        return self


class NumberAnswerSchema(_StructuredAnswerBase):
    final_answer: int | float | None

    @model_validator(mode="after")
    def _validate_answerable_contract(self) -> "NumberAnswerSchema":
        if self.is_answerable != (self.final_answer is not None):
            raise ValueError("number final_answer must be null iff is_answerable=false.")
        return self


class NameAnswerSchema(_StructuredAnswerBase):
    final_answer: str | None

    @model_validator(mode="after")
    def _validate_answerable_contract(self) -> "NameAnswerSchema":
        if self.is_answerable != (self.final_answer is not None):
            raise ValueError("name final_answer must be null iff is_answerable=false.")
        if self.final_answer is not None:
            normalized = _normalize_whitespace(self.final_answer)
            if not normalized:
                raise ValueError("name final_answer must be non-empty.")
            self.final_answer = normalized
        return self


class NamesAnswerSchema(_StructuredAnswerBase):
    final_answer: list[str] | None

    @model_validator(mode="after")
    def _validate_answerable_contract(self) -> "NamesAnswerSchema":
        if self.is_answerable != (self.final_answer is not None):
            raise ValueError("names final_answer must be null iff is_answerable=false.")
        if self.final_answer is not None:
            normalized: list[str] = []
            seen: set[str] = set()
            for item in self.final_answer:
                candidate = _normalize_whitespace(str(item))
                if not candidate:
                    continue
                key = candidate.casefold()
                if key in seen:
                    continue
                seen.add(key)
                normalized.append(candidate)
            if not normalized:
                raise ValueError("names final_answer must contain at least one non-empty name.")
            self.final_answer = normalized
        return self


class DateAnswerSchema(_StructuredAnswerBase):
    final_answer: str | None

    @model_validator(mode="after")
    def _validate_answerable_contract(self) -> "DateAnswerSchema":
        if self.is_answerable != (self.final_answer is not None):
            raise ValueError("date final_answer must be null iff is_answerable=false.")
        if self.final_answer is not None:
            normalized = _normalize_whitespace(self.final_answer)
            year, month, day = _parse_iso_date_parts(normalized)
            if _safe_iso_date(year=year, month=month, day=day) is None:
                raise ValueError("date final_answer must be ISO-8601 (YYYY-MM-DD).")
            self.final_answer = normalized
        return self


class FreeTextAnswerSchema(_StructuredAnswerBase):
    final_answer: str

    @model_validator(mode="after")
    def _validate_answerable_contract(self) -> "FreeTextAnswerSchema":
        normalized = _normalize_whitespace(self.final_answer)
        if not normalized:
            raise ValueError("free_text final_answer must be non-empty.")
        if len(normalized) > 280:
            raise ValueError("free_text final_answer must be at most 280 characters.")
        if not self.is_answerable and normalized != CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER:
            raise ValueError("free_text unanswerable output must be the canonical sentence.")
        self.final_answer = normalized
        return self


ANSWER_SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {
    AnswerType.BOOLEAN.value: BooleanAnswerSchema,
    AnswerType.NUMBER.value: NumberAnswerSchema,
    AnswerType.NAME.value: NameAnswerSchema,
    AnswerType.NAMES.value: NamesAnswerSchema,
    AnswerType.DATE.value: DateAnswerSchema,
    AnswerType.FREE_TEXT.value: FreeTextAnswerSchema,
}


@dataclass(frozen=True, slots=True)
class LegalEntityMetadata:
    entity_type: Literal["case_id", "statute_id"]
    raw_value: str
    normalized_value: str
    is_strong: bool


@dataclass(frozen=True, slots=True)
class QueryMetadata:
    legal_entities: tuple[LegalEntityMetadata, ...]
    document_title_cues: tuple[str, ...]
    likely_multi_document: bool


def extract_query_metadata(question_text: str) -> QueryMetadata:
    normalized_question = _normalize_whitespace(question_text)
    lowered_question = normalized_question.casefold()

    legal_entities: list[LegalEntityMetadata] = []
    seen_entities: set[tuple[str, str]] = set()

    for match in _CASE_ID_PATTERN.finditer(normalized_question):
        raw_value = _normalize_whitespace(match.group("case_id"))
        normalized_value = raw_value.replace(" ", "")
        entity_key = ("case_id", normalized_value.casefold())
        if entity_key in seen_entities:
            continue
        seen_entities.add(entity_key)
        legal_entities.append(
            LegalEntityMetadata(
                entity_type="case_id",
                raw_value=raw_value,
                normalized_value=normalized_value,
                is_strong=True,
            )
        )

    for match in _STATUTE_ID_PATTERN.finditer(normalized_question):
        raw_value = _normalize_whitespace(match.group("statute"))
        raw_value = re.sub(r"^(?:which|what|under|the)\s+", "", raw_value, flags=re.IGNORECASE)
        if not raw_value:
            continue
        normalized_value = raw_value.casefold()
        entity_key = ("statute_id", normalized_value)
        if entity_key in seen_entities:
            continue
        seen_entities.add(entity_key)
        legal_entities.append(
            LegalEntityMetadata(
                entity_type="statute_id",
                raw_value=raw_value,
                normalized_value=normalized_value,
                is_strong=True,
            )
        )

    document_title_cues: list[str] = []
    seen_titles: set[str] = set()
    for match in _DOCUMENT_TITLE_CUE_PATTERN.finditer(normalized_question):
        title = _normalize_whitespace(match.group("title"))
        key = title.casefold()
        if key in seen_titles:
            continue
        seen_titles.add(key)
        document_title_cues.append(title)

    case_entity_count = sum(1 for entity in legal_entities if entity.entity_type == "case_id")
    likely_multi_document = (
        case_entity_count >= 2
        or bool(_MULTI_DOCUMENT_SIGNAL_PATTERN.search(lowered_question))
        or lowered_question.count(" and ") >= 2
    )

    return QueryMetadata(
        legal_entities=tuple(legal_entities),
        document_title_cues=tuple(document_title_cues),
        likely_multi_document=likely_multi_document,
    )


class Retriever(Protocol):
    """Retrieval interface expected by the answering service."""

    def retrieve(
        self,
        question: QuestionRecord,
        *,
        query_metadata: QueryMetadata | None = None,
    ) -> RetrievalResult | list[dict[str, Any]]:
        """Return candidate evidence pages or a typed retrieval result."""


@dataclass(slots=True)
class AnswerResult:
    """Structured answer returned by the answering service."""

    question_id: str
    answer: Any
    confidence: float
    evidence_pages: list[PageReference]
    page_trace: PageAttributionTrace | None = None
    model_name: str | None = None


@dataclass(slots=True)
class _PageCandidate:
    doc_id: str
    page_numbers: tuple[int, ...]
    text: str
    include_page_numbers: bool = False

    @property
    def page_number(self) -> int:
        return self.page_numbers[0]


@dataclass(slots=True)
class _SolvedAnswer:
    answer: Any
    supporting_pages: list[_PageCandidate]


DeterministicExtractor = Callable[..., _SolvedAnswer | None]


class StructuredProvider(Protocol):
    def generate_structured(
        self,
        *,
        question: str,
        answer_type: str,
        evidence_pages: list[dict[str, Any]],
        answer_schema: type[BaseModel],
        reasoning_effort: str,
    ) -> Mapping[str, Any]:
        """Generate a schema-bound structured answer."""


class AnsweringService:
    """Extraction-first answer routing with grounded free-text fallback."""

    def __init__(
        self,
        *,
        retriever: Retriever,
        provider: FreeTextProvider,
        reasoning_effort_by_type: Mapping[str, str] | None = None,
        confidence_threshold_by_type: Mapping[str, float] | None = None,
    ) -> None:
        self._retriever = retriever
        self._provider = provider
        self._reasoning_effort_by_type = _normalize_reasoning_effort_map(reasoning_effort_by_type)
        self._confidence_threshold_by_type = _normalize_confidence_threshold_map(confidence_threshold_by_type)

    def answer_question(self, question: QuestionRecord) -> AnswerResult:
        query_metadata = extract_query_metadata(question.question)
        pages, retrieval_refs = _coerce_retrieval_payload(
            self._retriever.retrieve(question, query_metadata=query_metadata)
        )
        raw_retrieval_refs = list(retrieval_refs) if retrieval_refs else _group_page_references(pages)

        try:
            answer_type = AnswerType(str(question.answer_type))
        except ValueError as exc:
            raise ValueError(f"Unsupported answer_type: {question.answer_type}") from exc

        if not pages:
            if answer_type == AnswerType.FREE_TEXT:
                result = AnswerResult(
                    question_id=question.id,
                    answer=CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER,
                    confidence=0.0,
                    evidence_pages=[],
                )
            else:
                result = _empty_result(question_id=question.id)
        elif _supports_structured_provider(self._provider):
            result = self._answer_with_structured_solver(
                question=question,
                answer_type=answer_type,
                pages=pages,
                retrieval_refs=retrieval_refs,
            )
        elif answer_type == AnswerType.FREE_TEXT:
            result = self._answer_free_text(question=question, pages=pages, retrieval_refs=retrieval_refs)
        else:
            solved = self._solve_deterministic(question=question, answer_type=answer_type, pages=pages)
            if solved is None:
                result = _empty_result(question_id=question.id)
            else:
                result = AnswerResult(
                    question_id=question.id,
                    answer=solved.answer,
                    confidence=1.0,
                    evidence_pages=_group_page_references(solved.supporting_pages),
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
        if result.page_trace is None:
            solver_reported_pages = (
                list(result.evidence_pages)
                if _supports_structured_provider(self._provider) and answer_type != AnswerType.FREE_TEXT
                else []
            )
            result.page_trace = build_page_trace(
                raw_retrieved_chunk_pages=raw_retrieval_refs,
                pass_a_pages=raw_retrieval_refs,
                solver_reported_pages=solver_reported_pages,
                final_emitted_pages=list(result.evidence_pages),
                validation_action="preserved_pages",
                collapsed_answer=False,
            )
        return result

    def _answer_with_structured_solver(
        self,
        *,
        question: QuestionRecord,
        answer_type: AnswerType,
        pages: list[_PageCandidate],
        retrieval_refs: list[PageReference] | None,
    ) -> AnswerResult:
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
        base_refs = list(retrieval_refs) if retrieval_refs else _group_page_references(pages)
        relevant_pages = _normalize_relevant_page_list(getattr(validated_response, "relevant_pages", []))
        narrowed_pages = _narrow_page_candidates(pages=pages, relevant_pages=relevant_pages)
        narrowed_refs = _narrow_page_references(base_refs=base_refs, relevant_pages=relevant_pages)
        supporting_pages = narrowed_pages if narrowed_pages else pages
        supporting_refs = narrowed_refs if narrowed_refs else base_refs

        is_answerable = bool(getattr(validated_response, "is_answerable", False))
        final_answer = getattr(validated_response, "final_answer", None)
        if not is_answerable:
            if answer_type == AnswerType.FREE_TEXT:
                return AnswerResult(
                    question_id=question.id,
                    answer=CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER,
                    confidence=confidence,
                    evidence_pages=[],
                    model_name=provider_model_name,
                )
            return _empty_result(question_id=question.id, model_name=provider_model_name)

        if final_answer is None:
            return _empty_result(question_id=question.id, model_name=provider_model_name)

        threshold = self._confidence_threshold_by_type[answer_type.value]
        if confidence < threshold:
            if answer_type == AnswerType.FREE_TEXT:
                return AnswerResult(
                    question_id=question.id,
                    answer=CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER,
                    confidence=0.0,
                    evidence_pages=[],
                    model_name=provider_model_name,
                )
            return _empty_result(question_id=question.id, model_name=provider_model_name)

        if answer_type == AnswerType.FREE_TEXT:
            answer = _normalize_whitespace(str(final_answer))
            if len(answer) > 280:
                raise ValueError("free_text answers must be at most 280 characters.")
            _validate_free_text_grounding(answer=answer, pages=supporting_pages)
            return AnswerResult(
                question_id=question.id,
                answer=answer,
                confidence=confidence,
                evidence_pages=supporting_refs,
                model_name=provider_model_name,
            )

        if not _passes_typed_guardrails(
            answer_type=answer_type,
            question=question.question,
            proposed_answer=final_answer,
            pages=supporting_pages,
        ):
            return _empty_result(question_id=question.id, model_name=provider_model_name)

        return AnswerResult(
            question_id=question.id,
            answer=final_answer,
            confidence=confidence,
            evidence_pages=supporting_refs,
            model_name=provider_model_name,
        )

    def _solve_deterministic(
        self,
        *,
        question: QuestionRecord,
        answer_type: AnswerType,
        pages: list[_PageCandidate],
    ) -> _SolvedAnswer | None:
        question_tokens = _keyword_tokens(question.question)
        per_answer: dict[str, tuple[Any, list[_PageCandidate]]] = {}
        extractor = _get_deterministic_extractor(answer_type)

        for page in pages:
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
        retrieval_refs: list[PageReference] | None = None,
    ) -> AnswerResult:
        if not pages:
            return AnswerResult(
                question_id=question.id,
                answer=CANONICAL_UNANSWERABLE_FREE_TEXT_ANSWER,
                confidence=0.0,
                evidence_pages=[],
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

        _validate_free_text_grounding(answer=answer, pages=pages)

        confidence = _validate_provider_confidence(response.get("confidence", 0.0))
        return AnswerResult(
            question_id=question.id,
            answer=answer,
            confidence=confidence,
            evidence_pages=list(retrieval_refs) if retrieval_refs else _group_page_references(pages),
            model_name=_resolve_provider_model_name(self._provider),
        )


def _coerce_page(page: Mapping[str, Any]) -> _PageCandidate:
    page_number = int(page["page_number"])
    return _PageCandidate(
        doc_id=str(page["doc_id"]),
        page_numbers=(page_number,),
        text=str(page["text"]),
        include_page_numbers=False,
    )


def _coerce_retrieval_payload(
    retrieval_output: RetrievalResult | Iterable[Mapping[str, Any]],
) -> tuple[list[_PageCandidate], list[PageReference] | None]:
    if isinstance(retrieval_output, RetrievalResult):
        pages: list[_PageCandidate] = []
        for chunk in retrieval_output.evidence_chunks:
            page_numbers = tuple(sorted({int(page) for page in chunk.page_span if int(page) > 0}))
            if not page_numbers:
                continue
            pages.append(
                _PageCandidate(
                    doc_id=chunk.doc_id,
                    page_numbers=page_numbers,
                    text=chunk.text,
                    include_page_numbers=True,
                )
            )
        return pages, list(retrieval_output.retrieved_chunk_pages)

    if isinstance(retrieval_output, Mapping) or isinstance(retrieval_output, str | bytes):
        raise TypeError("Retriever must return a RetrievalResult or an iterable of page mappings.")

    return [_coerce_page(page) for page in retrieval_output], None


def _empty_result(*, question_id: str, model_name: str | None = None) -> AnswerResult:
    return AnswerResult(
        question_id=question_id,
        answer=None,
        confidence=0.0,
        evidence_pages=[],
        model_name=model_name,
    )


def _parse_iso_date_parts(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value)
    if match is None:
        raise ValueError("date must be ISO-8601 (YYYY-MM-DD).")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _supports_structured_provider(provider: FreeTextProvider) -> bool:
    supports_flag = getattr(provider, "supports_structured", None)
    if isinstance(supports_flag, bool):
        return supports_flag
    return callable(getattr(provider, "generate_structured", None))


def _resolve_provider_model_name(provider: Any) -> str | None:
    model_name = getattr(provider, "model", None)
    if isinstance(model_name, str):
        normalized = model_name.strip()
        if normalized:
            return normalized
    return None


def _normalize_reasoning_effort_map(reasoning_effort_by_type: Mapping[str, str] | None) -> dict[str, str]:
    normalized = dict(DEFAULT_REASONING_EFFORT_BY_TYPE)
    if reasoning_effort_by_type is None:
        return normalized
    for answer_type, raw_effort in reasoning_effort_by_type.items():
        key = str(answer_type).strip()
        if key not in normalized:
            continue
        effort = str(raw_effort).strip().lower()
        if effort in {"low", "medium", "high"}:
            normalized[key] = effort
    return normalized


def _normalize_confidence_threshold_map(
    confidence_threshold_by_type: Mapping[str, float] | None,
) -> dict[str, float]:
    normalized = dict(DEFAULT_CONFIDENCE_THRESHOLD_BY_TYPE)
    if confidence_threshold_by_type is None:
        return normalized
    for answer_type, raw_threshold in confidence_threshold_by_type.items():
        key = str(answer_type).strip()
        if key not in normalized:
            continue
        try:
            threshold = float(raw_threshold)
        except (TypeError, ValueError):
            continue
        if 0.0 <= threshold <= 1.0 and math.isfinite(threshold):
            normalized[key] = threshold
    return normalized


def _coerce_confidence(raw_confidence: Any, *, default: float) -> float:
    try:
        confidence = float(raw_confidence)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(confidence):
        return default
    if confidence < 0.0 or confidence > 1.0:
        return default
    return confidence


def _normalize_relevant_page_list(raw_relevant_pages: Any) -> list[int]:
    if not isinstance(raw_relevant_pages, list):
        return []
    relevant_pages: list[int] = []
    for raw_page in raw_relevant_pages:
        try:
            page_number = int(raw_page)
        except (TypeError, ValueError):
            continue
        if page_number > 0:
            relevant_pages.append(page_number)
    return sorted(set(relevant_pages))


def _narrow_page_candidates(*, pages: list[_PageCandidate], relevant_pages: list[int]) -> list[_PageCandidate]:
    if not relevant_pages:
        return []
    relevant_page_set = set(relevant_pages)
    narrowed: list[_PageCandidate] = []
    for page in pages:
        overlap = tuple(page_number for page_number in page.page_numbers if page_number in relevant_page_set)
        if not overlap:
            continue
        narrowed.append(
            _PageCandidate(
                doc_id=page.doc_id,
                page_numbers=overlap,
                text=page.text,
                include_page_numbers=page.include_page_numbers,
            )
        )
    return narrowed


def _narrow_page_references(*, base_refs: list[PageReference], relevant_pages: list[int]) -> list[PageReference]:
    if not relevant_pages:
        return []
    relevant_page_set = set(relevant_pages)
    narrowed: list[PageReference] = []
    for reference in base_refs:
        page_numbers: set[int] = set()
        for page in reference.page_numbers:
            page_int = int(page)
            if page_int in relevant_page_set:
                page_numbers.add(page_int)
        if not page_numbers:
            continue
        narrowed.append(PageReference(doc_id=reference.doc_id, page_numbers=sorted(page_numbers)))
    return narrowed


def _passes_typed_guardrails(
    *,
    answer_type: AnswerType,
    question: str,
    proposed_answer: Any,
    pages: list[_PageCandidate],
) -> bool:
    question_tokens = _keyword_tokens(question)
    if answer_type == AnswerType.BOOLEAN:
        return _matches_deterministic_evidence(
            extractor=_extract_boolean,
            question_tokens=question_tokens,
            pages=pages,
            proposed_answer=proposed_answer,
        )
    if answer_type == AnswerType.NUMBER:
        if _is_spurious_title_year_literal(proposed_answer=proposed_answer, pages=pages):
            return False
        return _matches_deterministic_evidence(
            extractor=_extract_number,
            question_tokens=question_tokens,
            pages=pages,
            proposed_answer=proposed_answer,
        )
    return True


def _matches_deterministic_evidence(
    *,
    extractor: DeterministicExtractor,
    question_tokens: set[str],
    pages: list[_PageCandidate],
    proposed_answer: Any,
) -> bool:
    seen_candidate = False
    for page in pages:
        solved = extractor(page=page, question_tokens=question_tokens)
        if solved is None:
            continue
        seen_candidate = True
        if _answers_equivalent(solved.answer, proposed_answer):
            return True
    return not seen_candidate


def _is_spurious_title_year_literal(*, proposed_answer: Any, pages: list[_PageCandidate]) -> bool:
    try:
        numeric_value = float(proposed_answer)
    except (TypeError, ValueError):
        return False

    if not numeric_value.is_integer():
        return False
    year = int(numeric_value)
    if not 1900 <= year <= 2100:
        return False

    for page in pages:
        for value, start, end in _extract_number_candidates(page.text):
            if int(value) != year:
                continue
            context = _context_window(page.text, start, end, radius=28).casefold()
            looks_like_case_literal = (
                "case" in context
                or "case no" in context
                or "case number" in context
            )
            has_amount_cue = bool(_AMOUNT_CUE_PATTERN.search(context))
            has_temporal_cue = bool(_TEMPORAL_CUE_PATTERN.search(context))
            if looks_like_case_literal and not has_amount_cue and not has_temporal_cue:
                return True
    return False


def _answers_equivalent(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left is right
    try:
        return math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-9)
    except (TypeError, ValueError):
        pass
    return _answer_key(left) == _answer_key(right)


def _parse_numeric_value(raw_value: str) -> float:
    numeric_text = raw_value.split()[-1]
    return float(numeric_text.replace(",", ""))


def _extract_number(*, page: _PageCandidate, question_tokens: set[str]) -> _SolvedAnswer | None:
    scored: list[tuple[float, float]] = []
    duration_intent = _is_duration_question(question_tokens)
    for value, start, end in _extract_number_candidates(page.text):
        sentence = _sentence_for_span(page.text, start, end)
        local_context = _context_window(page.text, start, end, radius=24)
        prefix = page.text[max(0, start - 20) : start]
        suffix = page.text[end : min(len(page.text), end + 16)]
        score = (2.0 * _score_context(context=local_context, question_tokens=question_tokens)) + _score_context(
            context=sentence,
            question_tokens=question_tokens,
        )
        has_amount_cue = bool(_AMOUNT_CUE_PATTERN.search(local_context))
        has_temporal_cue = bool(_TEMPORAL_CUE_PATTERN.search(local_context))
        if has_amount_cue:
            score += 1.5
        if has_temporal_cue:
            score += 1.5
        if duration_intent and has_temporal_cue:
            score += 2.0
        if duration_intent and re.match(
            r"^\s*(?:business\s+)?(?:day|days|week|weeks|month|months|year|years|hour|hours)\b",
            suffix,
            re.IGNORECASE,
        ):
            score += 3.0
        if duration_intent and has_amount_cue and not has_temporal_cue:
            score -= 2.0
        if duration_intent and _AMOUNT_CUE_PATTERN.search(prefix):
            score -= 3.0
        if not duration_intent and has_temporal_cue:
            score -= 1.0
        if score <= 0:
            continue
        scored.append((score, value))

    value = _unique_best_value(scored)
    if value is None:
        return None

    answer: int | float
    if value.is_integer():
        answer = int(value)
    else:
        answer = value
    return _SolvedAnswer(answer=answer, supporting_pages=[page])


def _extract_boolean(*, page: _PageCandidate, question_tokens: set[str]) -> _SolvedAnswer | None:
    candidates: list[tuple[float, bool]] = []
    permission_question = bool(question_tokens & _PERMISSION_QUESTION_HINTS)
    obligation_question = bool(question_tokens & _OBLIGATION_QUESTION_HINTS)
    if not permission_question and not obligation_question:
        permission_question = True
        obligation_question = True
    for sentence in _sentences(page.text):
        score = _score_context(context=sentence, question_tokens=question_tokens)
        if score <= 0:
            continue
        if permission_question and _contains_permission_negation(sentence):
            candidates.append((score + 1.0, False))
            continue
        if obligation_question and _contains_boolean_phrase(sentence, ("must not", "shall not")):
            candidates.append((score + 1.0, False))
            continue
        if permission_question and _contains_boolean_phrase(sentence, ("permitted", "allowed", "may", "can")):
            candidates.append((score, True))
            continue
        if obligation_question and _contains_boolean_phrase(sentence, ("must", "shall")):
            candidates.append((score, True))

    answer = _unique_best_value(candidates)
    if answer is None:
        return None

    return _SolvedAnswer(answer=answer, supporting_pages=[page])


def _extract_name(*, page: _PageCandidate, question_tokens: set[str]) -> _SolvedAnswer | None:
    candidates = _name_candidates(page=page, question_tokens=question_tokens)
    answer = _unique_best_value(candidates)
    if answer is None:
        return None
    return _SolvedAnswer(answer=answer, supporting_pages=[page])


def _extract_names(*, page: _PageCandidate, question_tokens: set[str]) -> _SolvedAnswer | None:
    candidates = _name_candidates(page=page, question_tokens=question_tokens)
    if not candidates:
        return None

    ordered_names: list[str] = []
    seen: set[str] = set()
    for _, candidate in candidates:
        key = candidate.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered_names.append(candidate)

    if not ordered_names:
        return None

    return _SolvedAnswer(answer=ordered_names, supporting_pages=[page])


def _extract_date(*, page: _PageCandidate, question_tokens: set[str]) -> _SolvedAnswer | None:
    scored: list[tuple[float, str]] = []
    for iso_value, start, end in _extract_date_candidates(page.text):
        context = _context_window(page.text, start, end)
        scored.append((_score_context(context=context, question_tokens=question_tokens), iso_value))

    answer = _unique_best_value(scored)
    if answer is None:
        return None

    return _SolvedAnswer(answer=answer, supporting_pages=[page])


def _name_candidates(*, page: _PageCandidate, question_tokens: set[str]) -> list[tuple[float, str]]:
    candidates: list[tuple[float, str]] = []
    for candidate, start, end in _entity_matches(page.text):
        context = _context_window(page.text, start, end)
        score = _score_context(context=context, question_tokens=question_tokens)
        if score <= 0:
            continue
        candidates.append((score, candidate))
    return candidates


def _validate_free_text_grounding(*, answer: str, pages: Iterable[_PageCandidate]) -> None:
    evidence_text = " ".join(page.text for page in pages)
    evidence_tokens = _keyword_tokens(evidence_text)
    evidence_numbers = _extract_numeric_values(evidence_text)
    answer_numbers = _extract_numeric_values(answer)
    unsupported_numbers = answer_numbers - evidence_numbers
    if unsupported_numbers:
        raise FreeTextGroundingValidationError(
            "free_text answer contradicts the evidence with unsupported numbers."
        )

    evidence_dates = set()
    for page in pages:
        evidence_dates.update(_extract_dates_from_text(page.text))

    answer_dates = _extract_dates_from_text(answer)
    missing_dates = answer_dates - evidence_dates
    if missing_dates:
        raise FreeTextGroundingValidationError(
            "free_text answer contradicts the evidence with unsupported dates."
        )

    evidence_names = _extract_names_from_text(evidence_text)
    answer_names = _extract_names_from_text(answer)
    unsupported_names = answer_names - evidence_names
    if unsupported_names:
        raise FreeTextGroundingValidationError(
            "free_text answer contradicts the evidence with unsupported names."
        )

    evidence_outcomes = _extract_outcomes(evidence_text)
    answer_outcomes = _extract_outcomes(answer)
    unsupported_outcomes = answer_outcomes - evidence_outcomes
    if unsupported_outcomes:
        raise FreeTextGroundingValidationError(
            "free_text answer contradicts the evidence with unsupported outcomes."
        )

    _validate_fact_polarity(answer=answer, evidence_text=evidence_text)

    for clause in _grounding_clauses(answer):
        clause_tokens = _keyword_tokens(clause)
        if not clause_tokens:
            continue
        unsupported_tokens = clause_tokens - evidence_tokens
        if len(unsupported_tokens) >= 2:
            raise FreeTextGroundingValidationError(
                "free_text answer contradicts the evidence with unsupported rationale or clauses."
            )


def _validate_provider_confidence(raw_confidence: Any) -> float:
    confidence = float(raw_confidence)
    if not math.isfinite(confidence) or confidence < 0.0 or confidence > 1.0:
        raise ValueError("Provider confidence must be finite and between 0.0 and 1.0.")
    return confidence


def _extract_numeric_values(text: str) -> set[float]:
    return {value for value, _, _ in _extract_number_candidates(text)}


def _extract_names_from_text(text: str) -> set[str]:
    return {candidate.casefold() for candidate, _, _ in _entity_matches(text)}


def _extract_outcomes(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    outcomes: set[str] = set()
    for label, pattern in _LEGAL_OUTCOME_PATTERNS.items():
        if pattern.search(normalized):
            outcomes.add(label)
    return outcomes


def _extract_dates_from_text(text: str) -> set[str]:
    return {iso_value for iso_value, _, _ in _extract_date_candidates(text)}


def _extract_date_candidates(text: str) -> list[tuple[str, int, int]]:
    candidates: list[tuple[str, int, int]] = []
    for match in _ISO_DATE_PATTERN.finditer(text):
        iso_value = _safe_iso_date(
            year=int(match.group(1)),
            month=int(match.group(2)),
            day=int(match.group(3)),
        )
        if iso_value is not None:
            candidates.append((iso_value, match.start(), match.end()))
    for match in _DATE_PATTERN.finditer(text):
        iso_value = _safe_iso_date_from_textual_match(match)
        if iso_value is None:
            continue
        candidates.append((iso_value, match.start(), match.end()))
    for match in _MONTH_FIRST_DATE_PATTERN.finditer(text):
        iso_value = _safe_iso_date_from_textual_match(match)
        if iso_value is None:
            continue
        candidates.append((iso_value, match.start(), match.end()))
    return candidates


def _extract_written_number_values(text: str) -> set[float]:
    return {value for value, _, _ in _extract_written_number_candidates(text)}


def _extract_number_candidates(text: str) -> list[tuple[float, int, int]]:
    candidates: list[tuple[float, int, int]] = []
    for match in _NUMBER_PATTERN.finditer(text):
        raw_value = match.group(0).strip()
        try:
            candidates.append((_parse_numeric_value(raw_value), match.start(), match.end()))
        except ValueError:
            continue
    candidates.extend(_extract_written_number_candidates(text))
    candidates.sort(key=lambda item: (item[1], item[2]))
    return candidates


def _extract_written_number_candidates(text: str) -> list[tuple[float, int, int]]:
    candidates: list[tuple[float, int, int]] = []
    word_matches = list(re.finditer(r"[A-Za-z]+(?:-[A-Za-z]+)?", text))
    index = 0
    while index < len(word_matches):
        token = word_matches[index].group(0).casefold()
        if token not in _WORD_NUMBER_TOKENS and _hyphenated_number_tokens(token) is None:
            index += 1
            continue

        start = word_matches[index].start()
        end = word_matches[index].end()
        sequence: list[str] = []
        cursor = index
        while cursor < len(word_matches):
            current = word_matches[cursor].group(0).casefold()
            if cursor > index and not re.fullmatch(r"[\s-]+", text[end : word_matches[cursor].start()]):
                break
            expanded = _hyphenated_number_tokens(current)
            if current in _WORD_NUMBER_TOKENS:
                sequence.append(current)
                end = word_matches[cursor].end()
                cursor += 1
                continue
            if expanded is not None:
                sequence.extend(expanded)
                end = word_matches[cursor].end()
                cursor += 1
                continue
            break

        parsed = _parse_written_number_sequence(sequence)
        if parsed is not None:
            candidates.append((float(parsed), start, end))
            index = cursor
            continue
        index += 1

    return candidates


def _hyphenated_number_tokens(token: str) -> list[str] | None:
    parts = token.split("-")
    if len(parts) < 2 or any(part not in _WORD_NUMBER_TOKENS for part in parts):
        return None
    return parts


def _parse_written_number_sequence(tokens: list[str]) -> int | None:
    total = 0
    current = 0
    seen_number = False
    for token in tokens:
        if token == "and":
            continue
        if token in _WORD_NUMBER_VALUES:
            current += _WORD_NUMBER_VALUES[token]
            seen_number = True
            continue
        if token == "hundred":
            if current == 0:
                current = 1
            current *= 100
            seen_number = True
            continue
        if token == "thousand":
            if current == 0:
                current = 1
            total += current * 1000
            current = 0
            seen_number = True
            continue
        return None
    if not seen_number:
        return None
    return total + current


def _safe_iso_date(*, year: int, month: int, day: int) -> str | None:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _safe_iso_date_from_textual_match(match: re.Match[str]) -> str | None:
    return _safe_iso_date(
        year=int(match.group("year")),
        month=_MONTHS[match.group("month").casefold()],
        day=int(match.group("day")),
    )


def _to_iso_date(*, day: int, month_name: str, year: int) -> str:
    month = _MONTHS[month_name.casefold()]
    return date(year, month, day).isoformat()


def _validate_fact_polarity(*, answer: str, evidence_text: str) -> None:
    answer_states = _extract_fact_states(answer)
    evidence_states = _extract_fact_states(evidence_text)
    for label, answer_values in answer_states.items():
        evidence_values = evidence_states.get(label)
        if not evidence_values:
            continue
        if answer_values.isdisjoint(evidence_values):
            raise FreeTextGroundingValidationError(
                "free_text answer contradicts the evidence with unsupported polarity or state."
            )


def _extract_fact_states(text: str) -> dict[str, set[str]]:
    facts: dict[str, set[str]] = defaultdict(set)
    for sentence in _sentences(text):
        lowered = sentence.casefold()
        for label, pattern in _LEGAL_OUTCOME_PATTERNS.items():
            for match in pattern.finditer(lowered):
                facts[label].add("negated" if _match_is_negated(lowered, match.start()) else "affirmed")
        for state in ("valid", "void"):
            for match in re.finditer(rf"\b{state}\b", lowered):
                if not _CONTRACT_ENTITY_PATTERN.search(_context_window(lowered, match.start(), match.end(), radius=24)):
                    continue
                facts["contract_status"].add(f"not_{state}" if _match_is_negated(lowered, match.start()) else state)
    return facts


def _match_is_negated(text: str, match_start: int) -> bool:
    prefix = text[max(0, match_start - 24) : match_start]
    return bool(
        re.search(
            r"(?:did\s+not|didn't|was\s+not|were\s+not|is\s+not|are\s+not|not|never)\s*$",
            prefix,
        )
    )


def _group_page_references(pages: Iterable[_PageCandidate]) -> list[PageReference]:
    grouped: dict[str, set[int]] = defaultdict(set)
    for page in pages:
        grouped[page.doc_id].update(page.page_numbers)

    return [
        PageReference(doc_id=doc_id, page_numbers=sorted(page_numbers))
        for doc_id, page_numbers in sorted(grouped.items())
    ]


def _dedupe_pages(pages: Iterable[_PageCandidate]) -> list[_PageCandidate]:
    seen: set[tuple[str, tuple[int, ...]]] = set()
    deduped: list[_PageCandidate] = []
    for page in pages:
        key = (page.doc_id, page.page_numbers)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(page)
    return deduped


def _provider_evidence_page(page: _PageCandidate) -> dict[str, Any]:
    return {
        "doc_id": page.doc_id,
        "page_number": page.page_number,
        "page_numbers": list(page.page_numbers),
        "text": page.text,
    }


def _contains_permission_negation(text: str) -> bool:
    return (
        _contains_boolean_phrase(text, _BOOLEAN_NEGATIVE)
        or bool(_BOOLEAN_NO_PERMISSION_PATTERN.search(text))
        or bool(_BOOLEAN_NO_MODAL_PATTERN.search(text))
    )


def _answer_key(answer: Any) -> str:
    if isinstance(answer, list):
        normalized_items = sorted(
            _normalize_whitespace(item).casefold() if isinstance(item, str) else str(item)
            for item in answer
        )
        return "|".join(normalized_items)
    if isinstance(answer, str):
        return _normalize_whitespace(answer).casefold()
    return str(answer)


def _is_duration_question(question_tokens: set[str]) -> bool:
    return bool(question_tokens.intersection(_DURATION_QUESTION_HINTS))


def _contains_boolean_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    return any(re.search(_phrase_pattern(phrase), text, re.IGNORECASE) for phrase in phrases)


def _phrase_pattern(phrase: str) -> str:
    tokens = [re.escape(token) for token in phrase.split()]
    return r"\b" + r"\s+".join(tokens) + r"\b"


def _keyword_tokens(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return {
        token
        for token in re.findall(r"[a-z0-9]+", normalized)
        if len(token) > 1 and token not in _STOPWORDS
    }


def _context_window(text: str, start: int, end: int, *, radius: int = 64) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return text[left:right]


def _sentence_for_span(text: str, start: int, end: int) -> str:
    sentence_start = text.rfind(".", 0, start)
    sentence_start = 0 if sentence_start == -1 else sentence_start + 1
    sentence_end = text.find(".", end)
    sentence_end = len(text) if sentence_end == -1 else sentence_end + 1
    return text[sentence_start:sentence_end]


def _score_context(*, context: str, question_tokens: set[str]) -> float:
    context_tokens = _keyword_tokens(context)
    if not question_tokens:
        return 0.0
    overlap = question_tokens & context_tokens
    return float(len(overlap))


def _sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", _normalize_whitespace(text))
    return [sentence for sentence in sentences if sentence]


def _grounding_clauses(text: str) -> list[str]:
    normalized = _normalize_whitespace(text)
    fragments = re.split(r"(?i)\b(?:because|since|due to|as|therefore|thus|but)\b|[;:]", normalized)
    return [fragment.strip(" ,.") for fragment in fragments if fragment.strip(" ,.")]


def _normalize_whitespace(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def _normalize_entity_candidate(value: str) -> str:
    normalized = _normalize_whitespace(value)
    return normalized.rstrip(".,;:")


def _entity_matches(text: str) -> list[tuple[str, int, int]]:
    matches: list[tuple[str, int, int]] = []
    seen_spans: set[tuple[int, int]] = set()
    for pattern in (_NAME_PATTERN, _UPPER_ENTITY_PATTERN):
        for match in pattern.finditer(text):
            candidate = _normalize_entity_candidate(match.group(0))
            if not candidate:
                continue
            span = (match.start(), match.end())
            if span in seen_spans:
                continue
            seen_spans.add(span)
            matches.append((candidate, match.start(), match.end()))

    for role_match in _ROLE_ENTITY_EXTRACTOR.finditer(text):
        entity_block = role_match.group("entities")
        block_start = role_match.start("entities")
        for item in _ENTITY_LIST_ITEM_PATTERN.finditer(entity_block):
            candidate = _normalize_entity_candidate(item.group(0))
            if not _is_safe_single_token_entity(candidate=candidate, context=text, start=block_start + item.start()):
                continue
            span = (block_start + item.start(), block_start + item.end())
            if span in seen_spans:
                continue
            seen_spans.add(span)
            matches.append((candidate, span[0], span[1]))

    matches.sort(key=lambda item: (item[1], item[2]))
    return matches


def _is_safe_single_token_entity(*, candidate: str, context: str, start: int) -> bool:
    parts = candidate.split()
    if len(parts) > 1:
        return True
    token = parts[0].rstrip(".")
    if token in _SINGLE_TOKEN_ENTITY_EXCLUSIONS:
        return False
    if len(token) < 3:
        return False
    prefix = context[max(0, start - 48) : start]
    return bool(_LEGAL_ROLE_PATTERN.search(prefix))


def _get_deterministic_extractor(answer_type: AnswerType) -> DeterministicExtractor:
    extractor = _DETERMINISTIC_EXTRACTORS.get(answer_type)
    if extractor is None:
        raise ValueError(f"Unsupported answer_type: {answer_type.value}")
    return extractor


def _unique_best_value(scored_values: Iterable[tuple[float, Any]]) -> Any | None:
    scored = list(scored_values)
    if not scored:
        return None

    best_score = max(score for score, _ in scored)
    best_values = {value for score, value in scored if score == best_score}
    if len(best_values) != 1:
        return None

    return next(iter(best_values))


_DETERMINISTIC_EXTRACTORS: dict[AnswerType, DeterministicExtractor] = {
    AnswerType.NUMBER: _extract_number,
    AnswerType.BOOLEAN: _extract_boolean,
    AnswerType.NAME: _extract_name,
    AnswerType.NAMES: _extract_names,
    AnswerType.DATE: _extract_date,
}
