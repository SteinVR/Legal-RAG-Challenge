from __future__ import annotations

from src.answering.service import (
    _PageCandidate,
    _extract_number,
    _is_law_number_question,
    _keyword_tokens,
)


def test_law_number_shortcut_is_not_used_for_duration_questions() -> None:
    question = "Within how many days under DIFC Law No. 5 must the notice be filed?"
    page = _PageCandidate(
        doc_id="doc-1",
        page_numbers=(1,),
        text="Under DIFC Law No. 5, the notice must be filed within 30 days.",
    )

    result = _extract_number(
        page=page,
        question_tokens=_keyword_tokens(question),
        prefer_law_number=_is_law_number_question(question),
    )

    assert result is not None
    assert result.answer == 30


def test_law_number_shortcut_is_reserved_for_identity_questions() -> None:
    question = "What is the DIFC Law No. referenced in the provision?"
    page = _PageCandidate(
        doc_id="doc-1",
        page_numbers=(1,),
        text="Under DIFC Law No. 5, the notice must be filed within 30 days.",
    )

    result = _extract_number(
        page=page,
        question_tokens=_keyword_tokens(question),
        prefer_law_number=_is_law_number_question(question),
    )

    assert result is not None
    assert result.answer == 5
