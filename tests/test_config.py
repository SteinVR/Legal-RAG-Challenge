from __future__ import annotations

from pathlib import Path

import pytest

from src.common.config import AppConfig, default_config_path, load_config, materialize_phase_paths, resolve_api_key


def test_load_config_reads_api_key_from_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COMPETITION_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("COMPETITION_API_KEY=from-dotenv\n", encoding="utf-8")

    config = load_config("configs/baseline/v001/config.yaml", env_file=env_file)

    assert resolve_api_key(config) == "from-dotenv"


def test_shell_environment_overrides_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPETITION_API_KEY", "from-shell")
    env_file = tmp_path / ".env"
    env_file.write_text("COMPETITION_API_KEY=from-dotenv\n", encoding="utf-8")

    config = load_config("configs/baseline/v001/config.yaml", env_file=env_file)

    assert resolve_api_key(config) == "from-shell"


def test_load_config_does_not_reuse_previous_env_file_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("COMPETITION_API_KEY", raising=False)
    monkeypatch.delenv("EVAL_API_KEY", raising=False)

    first_env = tmp_path / "first.env"
    second_env = tmp_path / "second.env"
    first_env.write_text("COMPETITION_API_KEY=first-key\n", encoding="utf-8")
    second_env.write_text("COMPETITION_API_KEY=second-key\n", encoding="utf-8")

    first_config = load_config("configs/baseline/v001/config.yaml", env_file=first_env)
    second_config = load_config("configs/baseline/v001/config.yaml", env_file=second_env)

    assert resolve_api_key(first_config) == "first-key"
    assert resolve_api_key(second_config) == "second-key"


def test_resolve_api_key_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COMPETITION_API_KEY", raising=False)
    monkeypatch.delenv("EVAL_API_KEY", raising=False)
    config = AppConfig()

    with pytest.raises(ValueError, match="Competition API key is not set"):
        resolve_api_key(config)


def test_materialize_phase_paths_are_phase_scoped(tmp_path: Path) -> None:
    warmup_config = AppConfig.model_validate({"phase": "warmup", "storage": {"root_dir": tmp_path}})
    final_config = AppConfig.model_validate({"phase": "final", "storage": {"root_dir": tmp_path}})

    warmup_paths = materialize_phase_paths(warmup_config, create=True)
    final_paths = materialize_phase_paths(final_config, create=True)

    assert warmup_paths.questions_path == tmp_path / "warmup" / "questions" / "questions.json"
    assert final_paths.documents_archive_path == tmp_path / "final" / "documents" / "documents.zip"
    assert warmup_paths.phase_dir.exists()
    assert final_paths.phase_dir.exists()


def test_default_config_path_falls_back_to_packaged_resource(tmp_path: Path) -> None:
    module_file = tmp_path / "site-packages" / "src" / "common" / "config.py"
    module_file.parent.mkdir(parents=True, exist_ok=True)
    module_file.write_text("# test", encoding="utf-8")

    packaged_config = (
        tmp_path / "site-packages" / "src" / "resources" / "configs" / "baseline" / "v001" / "config.yaml"
    )
    packaged_config.parent.mkdir(parents=True, exist_ok=True)
    packaged_config.write_text("phase: warmup\n", encoding="utf-8")

    assert default_config_path(module_file) == packaged_config
