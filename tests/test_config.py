from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.common.config import AppConfig, ConfigError, default_config_path, load_app_config
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


def test_env_overrides_apply_to_ocr_quality_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPETITION_OCR_RENDER_DPI", "300")
    monkeypatch.setenv("COMPETITION_OCR_TEXT_DETECTION_LIMIT_SIDE_LEN", "1536")
    monkeypatch.setenv("COMPETITION_OCR_TEXT_RECOGNITION_BATCH_SIZE", "2")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"version": "v001"}), encoding="utf-8")

    config = load_app_config(config_path, env_file=tmp_path / ".env")

    assert config.ingestion.ocr_render_dpi == 300
    assert config.ingestion.ocr_text_detection_limit_side_len == 1536
    assert config.ingestion.ocr_text_recognition_batch_size == 2


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


def test_load_app_config_provides_page_attribution_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"version": "v001"}), encoding="utf-8")

    config = load_app_config(config_path, env_file=tmp_path / ".env")

    assert config.page_attribution.pass_a_enabled is True
    assert config.page_attribution.suppress_title_pages is True
    assert config.page_attribution.suppress_repeated_boilerplate is True
    assert config.page_attribution.validation_mode == "degrade_first"
    assert config.page_attribution.emit_empty_pages_for_no_answer is True
    assert config.page_attribution.allow_solver_page_narrowing is True


def test_env_overrides_apply_to_page_attribution_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPETITION_PASS_A_ENABLED", "false")
    monkeypatch.setenv("COMPETITION_PAGE_VALIDATION_MODE", "strict_suppress")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"version": "v001"}), encoding="utf-8")

    config = load_app_config(config_path, env_file=tmp_path / ".env")

    assert config.page_attribution.pass_a_enabled is False
    assert config.page_attribution.validation_mode == "strict_suppress"


def test_env_override_normalizes_page_validation_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPETITION_PAGE_VALIDATION_MODE", "  STRICT SUPPRESS  ")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"version": "v001"}), encoding="utf-8")

    config = load_app_config(config_path, env_file=tmp_path / ".env")

    assert config.page_attribution.validation_mode == "strict_suppress"


def test_env_override_rejects_invalid_page_validation_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPETITION_PAGE_VALIDATION_MODE", "strict-mode")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"version": "v001"}), encoding="utf-8")

    with pytest.raises(ConfigError, match="COMPETITION_PAGE_VALIDATION_MODE"):
        load_app_config(config_path, env_file=tmp_path / ".env")


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


def test_load_app_config_supports_ingestion_fail_fast_setting(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "version": "v001",
                "ingestion": {
                    "fail_fast_on_document_error": True,
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_app_config(config_path, env_file=tmp_path / ".env")

    assert config.ingestion.fail_fast_on_document_error is True


def test_load_app_config_supports_project_gpu_runtime_requirement(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "version": "v001",
                "runtime": {"require_gpu": True},
            }
        ),
        encoding="utf-8",
    )

    config = load_app_config(config_path, env_file=tmp_path / ".env")

    assert config.runtime.require_gpu is True


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


def test_load_app_config_reads_w4b_reasoning_effort_and_thresholds(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "version": "v001",
                "answering": {
                    "reasoning_effort_by_type": {
                        "boolean": "high",
                        "number": "medium",
                        "name": "high",
                        "names": "high",
                        "date": "medium",
                        "free_text": "medium",
                    },
                    "confidence_threshold_by_type": {
                        "boolean": 0.7,
                        "number": 0.55,
                        "name": 0.75,
                        "names": 0.75,
                        "date": 0.6,
                        "free_text": 0.5,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_app_config(config_path, env_file=tmp_path / ".env")

    assert config.answering.reasoning_effort_by_type == {
        "boolean": "high",
        "number": "medium",
        "name": "high",
        "names": "high",
        "date": "medium",
        "free_text": "medium",
    }
    assert config.answering.confidence_threshold_by_type["name"] == pytest.approx(0.75)


def test_default_baseline_config_declares_w4b_answering_defaults() -> None:
    payload = yaml.safe_load(default_config_path().read_text(encoding="utf-8"))
    answering = payload.get("answering")

    assert isinstance(answering, dict), "TASK-W4B baseline config missing `answering` section."
    assert answering.get("reasoning_effort_by_type") == {
        "boolean": "high",
        "number": "medium",
        "name": "high",
        "names": "high",
        "date": "medium",
        "free_text": "medium",
    }
    thresholds = answering.get("confidence_threshold_by_type")
    assert isinstance(thresholds, dict), "TASK-W4B config must expose per-type confidence thresholds."
    assert {"boolean", "number", "name", "names", "date", "free_text"} <= set(thresholds)
