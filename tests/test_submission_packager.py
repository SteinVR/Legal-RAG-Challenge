from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from src.submission.packager import SubmissionPackager, _is_excluded


def test_code_archive_excludes_env_secret_files(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (project_root / ".env").write_text("COMPETITION_API_KEY=secret\n", encoding="utf-8")
    (project_root / ".env.local").write_text("CODEX_OAUTH_TOKEN=secret\n", encoding="utf-8")
    (project_root / "nested").mkdir(parents=True, exist_ok=True)
    (project_root / "nested" / ".env.production").write_text("OPENAI_API_KEY=secret\n", encoding="utf-8")

    archive_path = tmp_path / "code_archive.zip"
    packager = SubmissionPackager()
    packager.create_code_archive(output_path=archive_path, project_root=project_root)

    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())

    assert "main.py" in names
    assert ".env" not in names
    assert ".env.local" not in names
    assert "nested/.env.production" not in names


def test_code_archive_excludes_env_example_even_when_explicitly_included(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    src_dir = project_root / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (project_root / ".env.example").write_text("CODEX_OAUTH_TOKEN=template\n", encoding="utf-8")
    (project_root / ".env.production").write_text("CODEX_OAUTH_TOKEN=secret\n", encoding="utf-8")

    archive_path = tmp_path / "code_archive.zip"
    packager = SubmissionPackager()
    packager.create_code_archive(
        output_path=archive_path,
        project_root=project_root,
        include_paths={"src", ".env.example", ".env.production"},
    )

    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())

    assert "src/main.py" in names
    assert ".env.example" not in names
    assert ".env.production" not in names


def test_code_archive_exclusion_handles_paths_outside_project_root(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)
    external_file = tmp_path / "outside" / "python3.12"
    external_file.parent.mkdir(parents=True, exist_ok=True)
    external_file.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    assert _is_excluded(
        external_file.resolve(),
        root=project_root.resolve(),
        excluded_paths=set(),
    )


def test_code_archive_include_paths_keep_archive_under_limit_with_large_non_shipping_files(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    src_dir = project_root / "src"
    docs_dir = project_root / "docs"
    src_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "app.py").write_text("print('ok')\n", encoding="utf-8")

    large_non_shipping_file = docs_dir / "bundle.bin"
    with large_non_shipping_file.open("wb") as handle:
        handle.truncate((26 * 1024 * 1024) + 1)

    archive_path = tmp_path / "code_archive.zip"
    packager = SubmissionPackager()
    packager.create_code_archive(
        output_path=archive_path,
        project_root=project_root,
        include_paths={"src"},
    )

    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())

    assert "src/app.py" in names
    assert "docs/bundle.bin" not in names
    assert archive_path.stat().st_size <= 25 * 1024 * 1024
