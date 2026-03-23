from __future__ import annotations

import json
from pathlib import Path

import yaml

from tools.operator_context import _build_context


def _write_config(tmp_path: Path) -> tuple[Path, Path]:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "version": "v001",
                "phase": "warmup",
                "api": {
                    "base_url": "https://platform.agentic-challenge.ai/api/v1",
                    "api_key_env": "COMPETITION_API_KEY",
                },
                "storage": {"root_dir": str(tmp_path / "data")},
            }
        ),
        encoding="utf-8",
    )
    env_path = tmp_path / ".env"
    env_path.write_text("COMPETITION_API_KEY=test-key\n", encoding="utf-8")
    return config_path, env_path


def _write_questions(tmp_path: Path, questions: list[dict[str, str]]) -> Path:
    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    questions_path.parent.mkdir(parents=True, exist_ok=True)
    questions_path.write_text(json.dumps(questions) + "\n", encoding="utf-8")
    return questions_path


def test_build_context_marks_free_text_question_sets_as_provider_required(tmp_path: Path) -> None:
    config_path, env_path = _write_config(tmp_path)
    _write_questions(
        tmp_path,
        [{"id": "q-free", "question": "Summarize the order.", "answer_type": "free_text"}],
    )

    context = _build_context(config_path=config_path, env_file=env_path, phase_override=None)

    assert context["QUESTION_SET_REQUIRES_PROVIDER"] == "1"


def test_build_context_marks_deterministic_only_question_sets_as_not_provider_required(tmp_path: Path) -> None:
    config_path, env_path = _write_config(tmp_path)
    _write_questions(
        tmp_path,
        [{"id": "q-number", "question": "How many days?", "answer_type": "number"}],
    )

    context = _build_context(config_path=config_path, env_file=env_path, phase_override=None)

    assert context["QUESTION_SET_REQUIRES_PROVIDER"] == "0"
