"""Configuration loading from YAML with environment-aware overrides."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .schemas import Phase

DEFAULT_BASE_URL = "https://platform.agentic-challenge.ai/api/v1"
DEFAULT_ENV_FILE = Path(".env")
ENV_VAR_PATTERN = re.compile(r"\$(\w+)|\$\{([^}]+)\}")


class ConfigError(ValueError):
    """Raised when the project configuration is invalid or incomplete."""


class ApiSettings(BaseModel):
    """Remote API settings."""

    model_config = ConfigDict(extra="forbid")

    base_url: str = DEFAULT_BASE_URL
    api_key_env: str = "COMPETITION_API_KEY"
    api_key: str | None = Field(default=None, exclude=True, repr=False)
    timeout_seconds: float = 120.0
    user_agent: str = "agentic-rag-challenge/0.1.0"

    @field_validator("base_url")
    @classmethod
    def normalize_base_url(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("timeout_seconds")
    @classmethod
    def ensure_positive_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("api.timeout_seconds must be positive.")
        return value


class StorageSettings(BaseModel):
    """Phase-local storage layout."""

    model_config = ConfigDict(extra="forbid")

    root_dir: Path = Path("data")
    questions_dirname: str = "questions"
    questions_filename: str = "questions.json"
    documents_dirname: str = "documents"
    documents_archive_name: str = "documents.zip"
    extracted_documents_dirname: str = "pdfs"
    manifests_dirname: str = "manifests"
    manifest_filename: str = "sync_manifest.json"
    corpus_dirname: str = "corpus"
    corpus_filename: str = "corpus.jsonl"
    page_map_filename: str = "page_map.json"
    corpus_manifest_filename: str = "corpus_manifest.json"
    debug_dirname: str = "debug"


class DownloadSettings(BaseModel):
    """Download-time behavior for the local sync flow."""

    model_config = ConfigDict(extra="forbid")

    extract_documents: bool = True
    overwrite: bool = False
    chunk_size_bytes: int = 1_048_576

    @field_validator("chunk_size_bytes")
    @classmethod
    def ensure_positive_chunk_size(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("download.chunk_size_bytes must be positive.")
        return value


class EvaluationSettings(BaseModel):
    """Local evaluator/runtime policy toggles."""

    model_config = ConfigDict(extra="forbid")

    unanswerable_retrieval_policy: Literal["allow_empty", "require_non_empty"] = "allow_empty"


class IngestionSettings(BaseModel):
    """Configurable policies for the corpus parsing stage."""

    model_config = ConfigDict(extra="forbid")

    enable_ocr: bool = True
    ocr_unavailable_policy: Literal["error", "degraded"] = "degraded"
    extractable_text_min_chars: int = 50
    suspicious_text_max_chars: int = 200
    large_image_area_ratio: float = 0.25
    scan_image_area_ratio: float = 0.70
    text_completeness_target_chars: int = 1500
    encoding_bad_char_threshold: float = 0.05

    @field_validator("extractable_text_min_chars", "suspicious_text_max_chars", "text_completeness_target_chars")
    @classmethod
    def ensure_positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("ingestion integer thresholds must be positive.")
        return value

    @field_validator("large_image_area_ratio", "scan_image_area_ratio", "encoding_bad_char_threshold")
    @classmethod
    def ensure_ratio(cls, value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError("ingestion ratio thresholds must be between 0 and 1.")
        return value


class PageAttributionSettings(BaseModel):
    """Configurable two-pass page attribution behavior."""

    model_config = ConfigDict(extra="forbid")

    pass_a_enabled: bool = True
    suppress_title_pages: bool = True
    suppress_repeated_boilerplate: bool = True
    validation_mode: Literal["degrade_first", "strict_suppress"] = "degrade_first"
    emit_empty_pages_for_no_answer: bool = True
    allow_solver_page_narrowing: bool = True

    @field_validator("validation_mode", mode="before")
    @classmethod
    def normalize_validation_mode(cls, value: Any) -> Any:
        if isinstance(value, str):
            return _parse_page_validation_mode(value)
        return value


class LoggingSettings(BaseModel):
    """Runtime logging configuration."""

    model_config = ConfigDict(extra="forbid")

    directory: Path = Path("logs/project/runtime")
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    console: bool = True
    jsonl: bool = True
    debug_documents: bool = False
    debug_questions: bool = False

    @field_validator("level", mode="before")
    @classmethod
    def normalize_level(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().upper()
        return value


class AppConfig(BaseModel):
    """Complete configuration for the W1A foundation layer."""

    model_config = ConfigDict(extra="forbid")

    version: str = "v001"
    phase: Phase = Phase.WARMUP
    api: ApiSettings = Field(default_factory=ApiSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    download: DownloadSettings = Field(default_factory=DownloadSettings)
    evaluation: EvaluationSettings = Field(default_factory=EvaluationSettings)
    ingestion: IngestionSettings = Field(default_factory=IngestionSettings)
    page_attribution: PageAttributionSettings = Field(default_factory=PageAttributionSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    def resolve_api_key(self) -> str:
        """Return the competition API key from the configured environment variable."""

        api_key = (self.api.api_key or "").strip()
        if not api_key:
            api_key = os.getenv(self.api.api_key_env, "").strip()
        if not api_key and self.api.api_key_env != "EVAL_API_KEY":
            api_key = os.getenv("EVAL_API_KEY", "").strip()
        if not api_key:
            raise ConfigError(
                f"Competition API key is not set. Export {self.api.api_key_env} or EVAL_API_KEY, "
                "or add it to your .env file."
            )
        return api_key


def default_config_path(module_file: str | Path | None = None) -> Path:
    common_module = Path(module_file).resolve() if module_file is not None else Path(__file__).resolve()
    package_root = common_module.parents[1]
    repo_root = package_root.parent
    repo_config = repo_root / "configs" / "baseline" / "v001" / "config.yaml"
    if repo_config.exists():
        return repo_config

    return package_root / "resources" / "configs" / "baseline" / "v001" / "config.yaml"


DEFAULT_CONFIG_PATH = default_config_path()


def load_app_config(
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    *,
    env_file: str | Path = DEFAULT_ENV_FILE,
    phase_override: str | Phase | None = None,
) -> AppConfig:
    """Load YAML config, apply environment expansion, and then merge env overrides."""

    path = Path(config_path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    file_env = _read_env_file(env_file)
    effective_env = _effective_env(file_env)
    raw_data = _read_yaml(path)
    config = AppConfig.model_validate(_expand_env_vars(raw_data, effective_env))
    config = _apply_env_overrides(config, effective_env)
    config = _apply_resolved_api_key(config, effective_env)

    if phase_override is not None:
        config = config.model_copy(update={"phase": Phase(str(phase_override).lower())})

    return config


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}

    if not isinstance(loaded, Mapping):
        raise ConfigError(f"Config file must contain a YAML mapping at the root: {path}")

    return dict(loaded)


def _read_env_file(env_file: str | Path) -> dict[str, str]:
    env_path = Path(env_file)
    if not env_path.exists():
        return {}

    return {key: value for key, value in dotenv_values(env_path).items() if value is not None}


def _effective_env(file_env: Mapping[str, str]) -> dict[str, str]:
    env = dict(file_env)
    env.update(os.environ)
    return env


def _expand_env_vars(value: Any, env: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return ENV_VAR_PATTERN.sub(_build_env_replacer(env), value)
    if isinstance(value, list):
        return [_expand_env_vars(item, env) for item in value]
    if isinstance(value, Mapping):
        return {key: _expand_env_vars(item, env) for key, item in value.items()}
    return value


def _build_env_replacer(env: Mapping[str, str]):
    def replace(match: re.Match[str]) -> str:
        variable_name = match.group(1) or match.group(2) or ""
        return env.get(variable_name, match.group(0))

    return replace


def _apply_env_overrides(config: AppConfig, env: Mapping[str, str]) -> AppConfig:
    phase_override = env.get("COMPETITION_PHASE")
    base_url_override = env.get("COMPETITION_BASE_URL") or env.get("EVAL_BASE_URL")
    data_root_override = env.get("COMPETITION_DATA_ROOT")
    timeout_override = env.get("COMPETITION_TIMEOUT_SECONDS")
    extract_override = env.get("COMPETITION_EXTRACT_DOCUMENTS")
    overwrite_override = env.get("COMPETITION_OVERWRITE_DOWNLOADS")
    unanswerable_policy_override = env.get("COMPETITION_UNANSWERABLE_RETRIEVAL_POLICY")
    enable_ocr_override = env.get("COMPETITION_ENABLE_OCR")
    ocr_unavailable_policy_override = env.get("COMPETITION_OCR_UNAVAILABLE_POLICY")
    pass_a_enabled_override = env.get("COMPETITION_PASS_A_ENABLED")
    page_validation_mode_override = env.get("COMPETITION_PAGE_VALIDATION_MODE")
    log_level_override = env.get("COMPETITION_LOG_LEVEL")
    log_directory_override = env.get("COMPETITION_LOG_DIRECTORY")
    debug_documents_override = env.get("COMPETITION_DEBUG_DOCUMENTS")
    debug_questions_override = env.get("COMPETITION_DEBUG_QUESTIONS")

    if phase_override:
        config = config.model_copy(update={"phase": Phase(phase_override.strip().lower())})

    if base_url_override:
        config = config.model_copy(
            update={"api": config.api.model_copy(update={"base_url": base_url_override.strip()})}
        )

    if data_root_override:
        config = config.model_copy(
            update={"storage": config.storage.model_copy(update={"root_dir": Path(data_root_override.strip())})}
        )

    if timeout_override:
        config = config.model_copy(
            update={"api": config.api.model_copy(update={"timeout_seconds": float(timeout_override.strip())})}
        )

    if extract_override:
        config = config.model_copy(
            update={
                "download": config.download.model_copy(update={"extract_documents": _parse_bool(extract_override)})
            }
        )

    if overwrite_override:
        config = config.model_copy(
            update={"download": config.download.model_copy(update={"overwrite": _parse_bool(overwrite_override)})}
        )

    if unanswerable_policy_override:
        config = config.model_copy(
            update={
                "evaluation": config.evaluation.model_copy(
                    update={"unanswerable_retrieval_policy": unanswerable_policy_override.strip()}
                )
            }
        )

    if enable_ocr_override:
        config = config.model_copy(
            update={"ingestion": config.ingestion.model_copy(update={"enable_ocr": _parse_bool(enable_ocr_override)})}
        )

    if ocr_unavailable_policy_override:
        config = config.model_copy(
            update={
                "ingestion": config.ingestion.model_copy(
                    update={"ocr_unavailable_policy": ocr_unavailable_policy_override.strip()}
                )
            }
        )

    if pass_a_enabled_override:
        config = config.model_copy(
            update={
                "page_attribution": config.page_attribution.model_copy(
                    update={"pass_a_enabled": _parse_bool(pass_a_enabled_override)}
                )
            }
        )

    if page_validation_mode_override:
        config = config.model_copy(
            update={
                "page_attribution": config.page_attribution.model_copy(
                    update={"validation_mode": _parse_page_validation_mode(page_validation_mode_override)}
                )
            }
        )

    if log_level_override:
        config = config.model_copy(
            update={"logging": config.logging.model_copy(update={"level": log_level_override.strip().upper()})}
        )

    if log_directory_override:
        config = config.model_copy(
            update={"logging": config.logging.model_copy(update={"directory": Path(log_directory_override.strip())})}
        )

    if debug_documents_override:
        config = config.model_copy(
            update={
                "logging": config.logging.model_copy(update={"debug_documents": _parse_bool(debug_documents_override)})
            }
        )

    if debug_questions_override:
        config = config.model_copy(
            update={
                "logging": config.logging.model_copy(update={"debug_questions": _parse_bool(debug_questions_override)})
            }
        )

    return config


def _apply_resolved_api_key(config: AppConfig, env: Mapping[str, str]) -> AppConfig:
    api_key = env.get(config.api.api_key_env, "").strip()
    if not api_key and config.api.api_key_env != "EVAL_API_KEY":
        api_key = env.get("EVAL_API_KEY", "").strip()
    if not api_key:
        return config

    return config.model_copy(update={"api": config.api.model_copy(update={"api_key": api_key})})


def _parse_bool(raw_value: str) -> bool:
    normalized = raw_value.strip().lower()
    truthy = {"1", "true", "yes", "on"}
    falsy = {"0", "false", "no", "off"}

    if normalized in truthy:
        return True
    if normalized in falsy:
        return False

    raise ConfigError(f"Expected a boolean-like environment override, got: {raw_value!r}")


def _parse_page_validation_mode(raw_value: str) -> str:
    normalized = re.sub(r"[\s-]+", "_", raw_value.strip().lower())
    allowed_values = {"degrade_first", "strict_suppress"}
    if normalized in allowed_values:
        return normalized

    raise ConfigError(
        "Invalid COMPETITION_PAGE_VALIDATION_MODE override. "
        f"Expected one of {sorted(allowed_values)}, got: {raw_value!r}"
    )


def load_config(
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    env_file: str | Path = DEFAULT_ENV_FILE,
    phase_override: str | Phase | None = None,
) -> AppConfig:
    return load_app_config(config_path, env_file=env_file, phase_override=phase_override)


def resolve_api_key(config: AppConfig) -> str:
    return config.resolve_api_key()


def materialize_phase_paths(config: AppConfig, *, create: bool = False):
    from src.submission.sync import PhasePaths

    paths = PhasePaths.from_config(config)
    if create:
        paths.ensure_directories()
    return paths
