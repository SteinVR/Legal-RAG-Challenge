from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.common.config import AppConfig, default_config_path, load_app_config
from src.submission.sync import PhasePaths


def test_load_app_config_reads_api_key_from_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COMPETITION_API_KEY", raising=False)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump({"version": "v001", "storage": {"root_dir": str(tmp_path / "data")}}),
        encoding="utf-8",
    )
    env_file = tmp_path / ".env"
    env_file.write_text("COMPETITION_API_KEY=from-dotenv\n", encoding="utf-8")

    config = load_app_config(config_path, env_file=env_file)

    assert config.resolve_api_key() == "from-dotenv"


def test_shell_environment_overrides_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPETITION_API_KEY", "from-shell")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"version": "v001"}), encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text("COMPETITION_API_KEY=from-dotenv\n", encoding="utf-8")

    config = load_app_config(config_path, env_file=env_file)

    assert config.resolve_api_key() == "from-shell"


def test_phase_paths_include_corpus_artifacts(tmp_path: Path) -> None:
    config = AppConfig.model_validate({"phase": "warmup", "storage": {"root_dir": str(tmp_path)}})

    paths = PhasePaths.from_config(config)
    paths.ensure_directories()
    paths.ensure_corpus_directories()

    assert paths.questions_path == tmp_path / "warmup" / "questions" / "questions.json"
    assert paths.corpus_path == tmp_path / "warmup" / "corpus" / "corpus.jsonl"
    assert paths.page_map_path == tmp_path / "warmup" / "corpus" / "page_map.json"
    assert paths.corpus_manifest_path == tmp_path / "warmup" / "corpus" / "corpus_manifest.json"
    assert paths.debug_dir.exists()


def test_env_overrides_apply_to_ingestion_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPETITION_ENABLE_OCR", "false")
    monkeypatch.setenv("COMPETITION_OCR_UNAVAILABLE_POLICY", "error")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"version": "v001"}), encoding="utf-8")

    config = load_app_config(config_path, env_file=tmp_path / ".env")

    assert config.ingestion.enable_ocr is False
    assert config.ingestion.ocr_unavailable_policy == "error"


def test_env_overrides_apply_to_logging_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPETITION_LOG_LEVEL", "debug")
    monkeypatch.setenv("COMPETITION_LOG_DIRECTORY", str(tmp_path / "runtime-logs"))
    monkeypatch.setenv("COMPETITION_DEBUG_DOCUMENTS", "true")
    monkeypatch.setenv("COMPETITION_DEBUG_QUESTIONS", "true")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"version": "v001"}), encoding="utf-8")

    config = load_app_config(config_path, env_file=tmp_path / ".env")

    assert config.logging.level == "DEBUG"
    assert config.logging.directory == tmp_path / "runtime-logs"
    assert config.logging.debug_documents is True
    assert config.logging.debug_questions is True


def test_load_app_config_accepts_lowercase_logging_level_from_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump({"version": "v001", "logging": {"level": "debug"}}),
        encoding="utf-8",
    )

    config = load_app_config(config_path, env_file=tmp_path / ".env")

    assert config.logging.level == "DEBUG"


def test_load_app_config_supports_w4d_indexing_and_retrieval_settings(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "version": "v001",
                "indexing": {
                    "token_chunk_size": 280,
                    "token_chunk_overlap": 40,
                    "enabled_chunk_families": ["page", "clause", "microchunk"],
                },
                "retrieval": {
                    "candidate_budget": 12,
                    "rerank_budget": 6,
                    "default_evidence_budget": 4,
                    "parent_page_expansion_enabled": True,
                    "parent_page_expansion_limit": 2,
                    "question_class_budgets": {
                        "cross_case": {
                            "candidate_budget": 16,
                            "rerank_budget": 8,
                            "evidence_budget": 5,
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_app_config(config_path, env_file=tmp_path / ".env")

    assert config.indexing.token_chunk_size == 280
    assert config.indexing.token_chunk_overlap == 40
    assert config.indexing.enabled_chunk_families == ["page", "clause", "microchunk"]
    assert config.retrieval.candidate_budget == 12
    assert config.retrieval.rerank_budget == 6
    assert config.retrieval.default_evidence_budget == 4
    assert config.retrieval.parent_page_expansion_enabled is True
    assert config.retrieval.parent_page_expansion_limit == 2
    assert config.retrieval.question_class_budgets["cross_case"].candidate_budget == 16
    assert config.retrieval.question_class_budgets["cross_case"].rerank_budget == 8
    assert config.retrieval.question_class_budgets["cross_case"].evidence_budget == 5


def test_load_app_config_supports_gpu_ocr_runtime_settings(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "version": "v001",
                "ingestion": {
                    "ocr_device": "gpu:0",
                    "ocr_enable_hpi": False,
                    "ocr_model_root_dir": str(tmp_path / "models"),
                    "ocr_text_detection_model_dir": str(tmp_path / "models" / "PP-OCRv5_server_det"),
                    "ocr_text_recognition_model_dir": str(tmp_path / "models" / "en_PP-OCRv5_mobile_rec"),
                    "ocr_enable_mkldnn": False,
                    "ocr_cpu_threads": 6,
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_app_config(config_path, env_file=tmp_path / ".env")

    assert config.ingestion.ocr_device == "gpu:0"
    assert config.ingestion.ocr_enable_hpi is False
    assert config.ingestion.ocr_model_root_dir == tmp_path / "models"
    assert config.ingestion.ocr_text_detection_model_dir == tmp_path / "models" / "PP-OCRv5_server_det"
    assert config.ingestion.ocr_text_recognition_model_dir == tmp_path / "models" / "en_PP-OCRv5_mobile_rec"
    assert config.ingestion.ocr_enable_mkldnn is False
    assert config.ingestion.ocr_cpu_threads == 6


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
