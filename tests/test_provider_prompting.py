"""Regression checks for provider prompt assembly."""

from __future__ import annotations

from src.providers.codex_provider import _STRUCTURED_SYSTEM_PROMPT, _build_structured_user_prompt


def test_structured_prompt_keeps_instructions_in_system_and_task_payload_in_user() -> None:
    """Ensure the user prompt contains only the task payload and retrieved evidence."""

    user_prompt = _build_structured_user_prompt(
        question="How many days are allowed to file the notice?",
        answer_type="number",
        evidence_pages=[
            {
                "doc_id": "synthetic_law",
                "page_number": 2,
                "page_numbers": [2],
                "text": "Under Article 8 of the law, the notice must be filed within 30 days.",
            }
        ],
    )

    assert "Selection contract:" not in user_prompt
    assert "Self-review gate" not in user_prompt
    assert "Answer type: number" in user_prompt
    assert "Question: How many days are allowed to file the notice?" in user_prompt
    assert "Evidence:\n[1] doc_id=synthetic_law; pages=2;" in user_prompt

    assert "You are the answering specialist in a legal RAG pipeline" in _STRUCTURED_SYSTEM_PROMPT
    assert "Final self-review:" in _STRUCTURED_SYSTEM_PROMPT
    assert "relevant_evidence_indices" in _STRUCTURED_SYSTEM_PROMPT
    assert "{canonical_unanswerable_free_text}" not in _STRUCTURED_SYSTEM_PROMPT
    assert "There is no information on this question in the provided documents." in _STRUCTURED_SYSTEM_PROMPT
