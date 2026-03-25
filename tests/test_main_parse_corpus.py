from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.main import main
from tests.support.config import latest_runtime_log, write_main_test_config
from tests.support.documents import write_pdf

pytestmark = pytest.mark.integration


def _disable_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.ingestion.service.build_ocr_engine", lambda _settings: None)
    monkeypatch.setattr("src.ingestion.pdf_parser.build_ocr_engine", lambda _settings: None)


def test_parse_corpus_writes_canonical_outputs(tmp_path: Path) -> None:
    config_path, env_path = write_main_test_config(tmp_path)
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    write_pdf(documents_dir / "alpha.pdf", page_count=1, page_texts=["DIFC LAW\nArticle 1\nA fine applies."])

    exit_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "parse-corpus",
        ]
    )

    assert exit_code == 0
    corpus_path = tmp_path / "data" / "warmup" / "corpus" / "corpus.jsonl"
    page_map_path = tmp_path / "data" / "warmup" / "corpus" / "page_map.json"
    manifest_path = tmp_path / "data" / "warmup" / "corpus" / "corpus_manifest.json"
    debug_path = tmp_path / "data" / "warmup" / "corpus" / "debug" / "alpha.md"
    assert corpus_path.exists()
    assert page_map_path.exists()
    assert manifest_path.exists()
    assert debug_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["document_count"] == 1
    assert manifest["failed_document_count"] == 0


def test_parse_corpus_dry_run_reports_planned_paths(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config_path, env_path = write_main_test_config(tmp_path)

    exit_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "parse-corpus",
            "--dry-run",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "command: parse-corpus" in output
    assert "dry_run: true" in output
    assert "corpus.jsonl" in output
    assert "page_map.json" in output
    assert "corpus_manifest.json" in output


def test_parse_corpus_dry_run_writes_runtime_log(tmp_path: Path) -> None:
    config_path, env_path = write_main_test_config(tmp_path)

    exit_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "parse-corpus",
            "--dry-run",
        ]
    )

    payloads = [
        json.loads(line)
        for line in latest_runtime_log(tmp_path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    events = {payload["event"] for payload in payloads}

    assert exit_code == 0
    assert "command.start" in events
    assert "parse.dry_run" in events
    assert "command.success" in events


def test_parse_corpus_requires_downloaded_documents(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config_path, env_path = write_main_test_config(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--config",
                str(config_path),
                "--env-file",
                str(env_path),
                "parse-corpus",
            ]
        )

    assert exc_info.value.code == 1
    assert "Documents directory does not exist" in capsys.readouterr().err


def test_parse_corpus_writes_canonical_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_ocr(monkeypatch)
    config_path, env_path = write_main_test_config(tmp_path)
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    write_pdf(
        documents_dir / "alpha.pdf",
        page_count=1,
        page_texts=["EMPLOYMENT LAW\nArticle 1\nThe law applies."],
    )

    exit_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "parse-corpus",
            "--force",
        ]
    )
    output = capsys.readouterr().out

    corpus_path = tmp_path / "data" / "warmup" / "corpus" / "corpus.jsonl"
    page_map_path = tmp_path / "data" / "warmup" / "corpus" / "page_map.json"
    manifest_path = tmp_path / "data" / "warmup" / "corpus" / "corpus_manifest.json"
    debug_path = tmp_path / "data" / "warmup" / "corpus" / "debug" / "alpha.md"

    assert exit_code == 0
    assert "parsed_document_count: 1" in output
    assert corpus_path.exists()
    assert page_map_path.exists()
    assert manifest_path.exists()
    assert debug_path.exists()
    corpus_rows = [json.loads(line) for line in corpus_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert corpus_rows[0]["doc_id"] == "alpha"
    assert corpus_rows[0]["page_number"] == 1


def test_parse_corpus_doc_id_subset_rebuilds_against_existing_full_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_ocr(monkeypatch)
    config_path, env_path = write_main_test_config(tmp_path)
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    write_pdf(documents_dir / "alpha.pdf", page_count=1, page_texts=["DIFC LAW NO. 1\nArticle 1"])
    write_pdf(documents_dir / "beta.pdf", page_count=1, page_texts=["DIFC LAW NO. 2\nArticle 2"])

    first_exit_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "parse-corpus",
            "--force",
        ]
    )
    second_exit_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "parse-corpus",
            "--doc-id",
            "beta",
        ]
    )

    corpus_path = tmp_path / "data" / "warmup" / "corpus" / "corpus.jsonl"
    corpus_rows = [json.loads(line) for line in corpus_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert first_exit_code == 0
    assert second_exit_code == 0
    assert [row["doc_id"] for row in corpus_rows] == ["beta"]


def test_parse_corpus_doc_id_subset_skips_when_subset_artifacts_are_complete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _disable_ocr(monkeypatch)
    config_path, env_path = write_main_test_config(tmp_path)
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    write_pdf(documents_dir / "alpha.pdf", page_count=1, page_texts=["DIFC LAW NO. 1\nArticle 1"])
    write_pdf(documents_dir / "beta.pdf", page_count=1, page_texts=["DIFC LAW NO. 2\nArticle 2"])

    first_exit_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "parse-corpus",
            "--doc-id",
            "beta",
            "--force",
        ]
    )
    second_exit_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "parse-corpus",
            "--doc-id",
            "beta",
        ]
    )
    output = capsys.readouterr().out

    assert first_exit_code == 0
    assert second_exit_code == 0
    assert "skipped_paths:" in output


def test_parse_corpus_rebuilds_when_debug_artifact_is_missing_without_force(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _disable_ocr(monkeypatch)
    config_path, env_path = write_main_test_config(tmp_path)
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    write_pdf(documents_dir / "alpha.pdf", page_count=1, page_texts=["DIFC LAW NO. 1\nArticle 1"])

    first_exit_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "parse-corpus",
            "--force",
        ]
    )
    debug_path = tmp_path / "data" / "warmup" / "corpus" / "debug" / "alpha.md"
    debug_path.unlink()

    second_exit_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "parse-corpus",
        ]
    )
    output = capsys.readouterr().out

    assert first_exit_code == 0
    assert second_exit_code == 0
    assert debug_path.exists()
    assert "written_paths:" in output


def test_parse_corpus_doc_id_subset_skips_when_selected_failure_manifest_is_complete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _disable_ocr(monkeypatch)
    config_path, env_path = write_main_test_config(tmp_path)
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    write_pdf(documents_dir / "alpha.pdf", page_count=1, page_texts=["DIFC LAW NO. 1\nArticle 1"])
    (documents_dir / "broken.pdf").write_bytes(b"%PDF-1.4 broken content")

    first_exit_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "parse-corpus",
            "--doc-id",
            "alpha",
            "--doc-id",
            "broken",
            "--force",
        ]
    )
    second_exit_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "parse-corpus",
            "--doc-id",
            "alpha",
            "--doc-id",
            "broken",
        ]
    )
    output = capsys.readouterr().out

    assert first_exit_code == 0
    assert second_exit_code == 0
    assert "skipped_paths:" in output


def test_parse_corpus_full_run_skips_when_failure_manifest_is_complete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _disable_ocr(monkeypatch)
    config_path, env_path = write_main_test_config(tmp_path)
    documents_dir = tmp_path / "data" / "warmup" / "documents" / "pdfs"
    write_pdf(documents_dir / "alpha.pdf", page_count=1, page_texts=["DIFC LAW NO. 1\nArticle 1"])
    (documents_dir / "broken.pdf").write_bytes(b"%PDF-1.4 broken content")

    first_exit_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "parse-corpus",
            "--force",
        ]
    )
    second_exit_code = main(
        [
            "--config",
            str(config_path),
            "--env-file",
            str(env_path),
            "parse-corpus",
        ]
    )
    output = capsys.readouterr().out

    assert first_exit_code == 0
    assert second_exit_code == 0
    assert "skipped_paths:" in output
