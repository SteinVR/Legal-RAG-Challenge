from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def write_app_config(
    tmp_path: Path,
    *,
    phase: str = "warmup",
    include_provider_token: bool = False,
    debug_questions: bool = False,
    unanswerable_retrieval_policy: str | None = None,
    disable_ocr: bool = False,
) -> tuple[Path, Path]:
    config_path = tmp_path / "config.yaml"
    payload: dict[str, Any] = {
        "version": "v001",
        "phase": phase,
        "api": {
            "base_url": "https://platform.agentic-challenge.ai/api/v1",
            "api_key_env": "COMPETITION_API_KEY",
        },
        "storage": {"root_dir": str(tmp_path / "data")},
        "logging": {
            "directory": str(tmp_path / "logs" / "project" / "runtime"),
            "console": False,
            "debug_questions": debug_questions,
        },
    }
    if disable_ocr:
        payload["ingestion"] = {"enable_ocr": False}
    if unanswerable_retrieval_policy is not None:
        payload["evaluation"] = {"unanswerable_retrieval_policy": unanswerable_retrieval_policy}

    config_path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    env_lines = ["COMPETITION_API_KEY=test-key"]
    if include_provider_token:
        env_lines.append("CODEX_OAUTH_TOKEN=test-token")
    env_path = tmp_path / ".env"
    env_path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
    return config_path, env_path


def write_main_test_config(tmp_path: Path) -> tuple[Path, Path]:
    return write_app_config(tmp_path, disable_ocr=True)


def write_submission_test_config(
    tmp_path: Path,
    *,
    include_provider_token: bool = True,
    debug_questions: bool = False,
    unanswerable_retrieval_policy: str | None = None,
) -> tuple[Path, Path]:
    return write_app_config(
        tmp_path,
        include_provider_token=include_provider_token,
        debug_questions=debug_questions,
        unanswerable_retrieval_policy=unanswerable_retrieval_policy,
    )


def latest_runtime_log(tmp_path: Path, *, phase: str = "warmup") -> Path:
    log_files = sorted((tmp_path / "logs" / "project" / "runtime" / phase).glob("*.jsonl"))
    assert log_files
    return log_files[-1]
