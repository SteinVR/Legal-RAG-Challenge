from __future__ import annotations

import importlib
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from src.common.schemas import QuestionRecord


def load_answering_service() -> type[Any]:
    module = importlib.import_module("src.answering.service")
    return module.AnsweringService


def question_record(*args: str, text: str | None = None, answer_type: str | None = None, question_id: str = "q1") -> QuestionRecord:
    if args:
        if len(args) == 2:
            text, answer_type = args
        elif len(args) == 3:
            question_id, answer_type, text = args
        else:
            raise TypeError("question_record accepts either 2 or 3 positional arguments")
    if text is None or answer_type is None:
        raise TypeError("question_record requires text and answer_type")
    return QuestionRecord(id=question_id, question=text, answer_type=answer_type)


def page_payload(*, doc_id: str = "alpha", page_number: int, text: str) -> dict[str, Any]:
    return {
        "doc_id": doc_id,
        "page_number": page_number,
        "text": text,
    }


def result_field(result: Any, field: str) -> Any:
    if isinstance(result, Mapping):
        return result[field]
    return getattr(result, field)


def collect_ref_pages(normalized: dict[str, set[int]], ref: Any) -> None:
    if isinstance(ref, Mapping):
        doc_id = str(ref["doc_id"])
        if "page_numbers" in ref:
            normalized[doc_id].update(int(page) for page in ref["page_numbers"])
            return

        normalized[doc_id].add(int(ref["page_number"]))
        return

    doc_id = str(ref.doc_id)
    if hasattr(ref, "page_numbers"):
        normalized[doc_id].update(int(page) for page in ref.page_numbers)
        return

    normalized[doc_id].add(int(ref.page_number))


def grouped_refs(result: Any) -> list[tuple[str, list[int]]]:
    refs = result_field(result, "evidence_pages")
    normalized: dict[str, set[int]] = defaultdict(set)
    for ref in refs:
        collect_ref_pages(normalized, ref)

    return sorted((doc_id, sorted(page_numbers)) for doc_id, page_numbers in normalized.items())
