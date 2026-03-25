from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.operator_context import _build_context
from tests.support.config import write_app_config
from tests.support.documents import write_questions


def test_build_context_marks_free_text_question_sets_as_provider_required(tmp_path: Path) -> None:
    config_path, env_path = write_app_config(tmp_path)
    write_questions(
        tmp_path / "data" / "warmup" / "questions" / "questions.json",
        [{"id": "q-free", "question": "Summarize the order.", "answer_type": "free_text"}],
    )

    context = _build_context(config_path=config_path, env_file=env_path, phase_override=None)

    assert context["QUESTION_SET_REQUIRES_PROVIDER"] == "1"


@pytest.mark.parametrize("answer_type", ["boolean", "number", "name", "names", "date"])
def test_build_context_marks_schema_first_typed_question_sets_as_provider_required(
    tmp_path: Path,
    answer_type: str,
) -> None:
    config_path, env_path = write_app_config(tmp_path)
    write_questions(
        tmp_path / "data" / "warmup" / "questions" / "questions.json",
        [{"id": f"q-{answer_type}", "question": "Typed question", "answer_type": answer_type}],
    )

    context = _build_context(config_path=config_path, env_file=env_path, phase_override=None)

    assert context["QUESTION_SET_REQUIRES_PROVIDER"] == "1"
