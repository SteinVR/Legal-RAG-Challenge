from __future__ import annotations

from tests.support.submission import build_submission_parser


def test_build_submission_cli_exposes_runtime_path_arguments() -> None:
    command_name, parser = build_submission_parser()

    assert command_name in {"build-submission", "run-pipeline"}
    destinations = {action.dest for action in parser._actions}
    assert {"questions_path", "documents_dir", "output_dir"} <= destinations
