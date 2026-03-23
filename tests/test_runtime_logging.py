from __future__ import annotations

import json
import logging
from pathlib import Path

from src.common.config import AppConfig
from src.common.runtime_logging import configure_runtime_logging, get_logger, log_event, shutdown_runtime_logging


def test_runtime_logging_writes_structured_jsonl_records(tmp_path) -> None:
    config = AppConfig.model_validate(
        {
            "phase": "warmup",
            "logging": {
                "directory": str(tmp_path / "logs" / "project" / "runtime"),
                "console": False,
                "jsonl": True,
            },
        }
    )

    context = configure_runtime_logging(config, command="parse-corpus", phase=config.phase.value)
    try:
        log_event(
            get_logger("tests.runtime"),
            logging.INFO,
            "test.event",
            "Structured runtime logging test event.",
            stage="tests",
            question_id="q1",
            metrics={"count": 1},
        )
    finally:
        shutdown_runtime_logging()

    payloads = [
        json.loads(line)
        for line in context.log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert payloads[-1]["event"] == "test.event"
    assert payloads[-1]["component"] == "tests.runtime"
    assert payloads[-1]["stage"] == "tests"
    assert payloads[-1]["question_id"] == "q1"
    assert payloads[-1]["metrics"] == {"count": 1}
    assert payloads[-1]["run_id"] == context.run_id
    assert payloads[-1]["command"] == "parse-corpus"
    assert payloads[-1]["phase"] == "warmup"


def test_runtime_logging_skips_log_directory_when_jsonl_disabled(
    tmp_path,
    monkeypatch,
) -> None:
    config = AppConfig.model_validate(
        {
            "phase": "warmup",
            "logging": {
                "directory": str(tmp_path / "logs" / "project" / "runtime"),
                "console": True,
                "jsonl": False,
            },
        }
    )

    def fail_mkdir(self, parents=False, exist_ok=False) -> None:
        raise AssertionError("configure_runtime_logging should not create a log directory when jsonl is disabled")

    monkeypatch.setattr(Path, "mkdir", fail_mkdir)

    context = configure_runtime_logging(config, command="parse-corpus", phase=config.phase.value)
    try:
        assert context.log_path is None
    finally:
        shutdown_runtime_logging()
