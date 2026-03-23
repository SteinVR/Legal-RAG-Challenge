from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import fitz
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "06_build_submission.sh"


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


def _write_questions(tmp_path: Path, questions: list[dict[str, str]]) -> None:
    questions_path = tmp_path / "data" / "warmup" / "questions" / "questions.json"
    questions_path.parent.mkdir(parents=True, exist_ok=True)
    questions_path.write_text(json.dumps(questions) + "\n", encoding="utf-8")


def _write_pdf(path: Path, *, page_texts: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    for page_text in page_texts:
        page = document.new_page()
        page.insert_text((72, 72), page_text)
    document.save(path)
    document.close()


def _clean_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("CODEX_OAUTH_TOKEN", None)
    env.pop("OPENAI_API_KEY", None)
    env.pop("CODEX_API_KEY", None)
    return env


def test_build_submission_script_preflight_allows_deterministic_only_runs_without_provider_creds(
    tmp_path: Path,
) -> None:
    config_path, env_path = _write_config(tmp_path)
    _write_questions(
        tmp_path,
        [{"id": "q-number", "question": "How many days?", "answer_type": "number"}],
    )
    _write_pdf(
        tmp_path / "data" / "warmup" / "documents" / "pdfs" / "alpha.pdf",
        page_texts=["Payment must be made within 10 days."],
    )

    result = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--config", str(config_path), "--env-file", str(env_path), "--preflight"],
        cwd=PROJECT_ROOT,
        env=_clean_env(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Provider required: 0" in result.stdout
    assert "=== Preflight OK ===" in result.stdout


def test_build_submission_script_preflight_rejects_free_text_runs_without_provider_creds(tmp_path: Path) -> None:
    config_path, env_path = _write_config(tmp_path)
    _write_questions(
        tmp_path,
        [{"id": "q-free", "question": "Summarize the order.", "answer_type": "free_text"}],
    )
    _write_pdf(
        tmp_path / "data" / "warmup" / "documents" / "pdfs" / "alpha.pdf",
        page_texts=["The tribunal dismissed the claim with costs."],
    )

    result = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--config", str(config_path), "--env-file", str(env_path), "--preflight"],
        cwd=PROJECT_ROOT,
        env=_clean_env(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Provider required: 1" in result.stdout
    assert "FAIL: no provider credential found" in result.stdout
