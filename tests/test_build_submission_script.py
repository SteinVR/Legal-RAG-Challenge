from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from tests.support.config import write_app_config
from tests.support.documents import write_pdf, write_questions

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "06_build_submission.sh"


def _clean_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("CODEX_OAUTH_TOKEN", None)
    env.pop("OPENAI_API_KEY", None)
    env.pop("CODEX_API_KEY", None)
    return env


def test_build_submission_script_preflight_rejects_schema_first_number_runs_without_provider_creds(
    tmp_path: Path,
) -> None:
    config_path, env_path = write_app_config(tmp_path)
    write_questions(
        tmp_path / "data" / "warmup" / "questions" / "questions.json",
        [{"id": "q-number", "question": "How many days?", "answer_type": "number"}],
    )
    write_pdf(
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

    assert result.returncode == 1
    assert "Provider required: 1" in result.stdout
    assert "FAIL: no provider credential found" in result.stdout


def test_build_submission_script_preflight_rejects_free_text_runs_without_provider_creds(tmp_path: Path) -> None:
    config_path, env_path = write_app_config(tmp_path)
    write_questions(
        tmp_path / "data" / "warmup" / "questions" / "questions.json",
        [{"id": "q-free", "question": "Summarize the order.", "answer_type": "free_text"}],
    )
    write_pdf(
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
