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
SUPPORTED_ANSWER_TYPES = frozenset({"boolean", "number", "name", "names", "date", "free_text"})
DEFAULT_REASONING_EFFORT_BY_TYPE: dict[str, str] = {
    "boolean": "high",
    "number": "medium",
    "name": "high",
    "names": "high",
    "date": "medium",
    "free_text": "medium",
}
DEFAULT_CONFIDENCE_THRESHOLD_BY_TYPE: dict[str, float] = {
    "boolean": 0.7,
    "number": 0.55,
    "name": 0.75,
    "names": 0.75,
    "date": 0.6,
    "free_text": 0.5,
}


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
    ocr_device: str = "gpu:0"
    ocr_enable_hpi: bool = False
    ocr_enable_mkldnn: bool = False
    ocr_cpu_threads: int = 8
    ocr_model_root_dir: Path = Field(default_factory=lambda: Path.home() / ".paddlex" / "official_models")
    ocr_text_detection_model_dir: Path | None = None
    ocr_text_recognition_model_dir: Path | None = None
    extractable_text_min_chars: int = 50
    suspicious_text_max_chars: int = 200
    large_image_area_ratio: float = 0.25
    scan_image_area_ratio: float = 0.70
    text_completeness_target_chars: int = 1500
    encoding_bad_char_threshold: float = 0.05
    enable_semantic_table_blocks: bool = False
    opendataloader_table_method: Literal["default", "cluster"] = "cluster"
    opendataloader_reading_order: Literal["off", "xycut"] = "xycut"
    opendataloader_hybrid_backend: Literal["off", "docling-fast"] = "docling-fast"
    opendataloader_hybrid_mode: Literal["auto", "full"] = "auto"
    opendataloader_hybrid_fallback: bool = True
    opendataloader_hybrid_url: str | None = None
    opendataloader_hybrid_timeout_ms: int = 30_000

    @field_validator(
        "extractable_text_min_chars",
        "suspicious_text_max_chars",
        "text_completeness_target_chars",
        "ocr_cpu_threads",
    )
    @classmethod
    def ensure_positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("ingestion integer thresholds must be positive.")
        return value

    @field_validator("opendataloader_hybrid_timeout_ms")
    @classmethod
    def ensure_positive_timeout_ms(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("ingestion opendataloader_hybrid_timeout_ms must be positive.")
        return value

    @field_validator("large_image_area_ratio", "scan_image_area_ratio", "encoding_bad_char_threshold")
    @classmethod
    def ensure_ratio(cls, value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError("ingestion ratio thresholds must be between 0 and 1.")
        return value

    @field_validator("ocr_device")
    @classmethod
    def ensure_non_empty_ocr_device(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("ingestion.ocr_device must be non-empty.")
        return normalized

    @field_validator(
        "ocr_model_root_dir",
        "ocr_text_detection_model_dir",
        "ocr_text_recognition_model_dir",
        mode="before",
    )
    @classmethod
    def normalize_optional_paths(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return Path(str(value)).expanduser()


class AnsweringSettings(BaseModel):
    """Schema-first answering defaults and confidence controls."""

    model_config = ConfigDict(extra="forbid")

    reasoning_effort_by_type: dict[str, Literal["low", "medium", "high"]] = Field(
        default_factory=lambda: dict(DEFAULT_REASONING_EFFORT_BY_TYPE)
    )
    confidence_threshold_by_type: dict[str, float] = Field(
        default_factory=lambda: dict(DEFAULT_CONFIDENCE_THRESHOLD_BY_TYPE)
    )

    @field_validator("reasoning_effort_by_type")
    @classmethod
    def ensure_reasoning_effort_coverage(
        cls,
        value: dict[str, Literal["low", "medium", "high"]],
    ) -> dict[str, Literal["low", "medium", "high"]]:
        missing = SUPPORTED_ANSWER_TYPES - set(value)
        if missing:
            missing_list = ", ".join(sorted(missing))
            raise ValueError(f"answering.reasoning_effort_by_type missing keys: {missing_list}")
        return value

    @field_validator("confidence_threshold_by_type")
    @classmethod
    def ensure_threshold_coverage_and_range(cls, value: dict[str, float]) -> dict[str, float]:
        missing = SUPPORTED_ANSWER_TYPES - set(value)
        if missing:
            missing_list = ", ".join(sorted(missing))
            raise ValueError(f"answering.confidence_threshold_by_type missing keys: {missing_list}")
        for answer_type, threshold in value.items():
            if answer_type not in SUPPORTED_ANSWER_TYPES:
                continue
            if not 0 <= threshold <= 1:
                raise ValueError(
                    f"answering.confidence_threshold_by_type[{answer_type!r}] must be between 0 and 1."
                )
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


class IndexingSettings(BaseModel):
    """Chunking and indexing controls."""

    model_config = ConfigDict(extra="forbid")

    token_chunk_size: int = 300
    token_chunk_overlap: int = 50
    enabled_chunk_families: list[str] = Field(
        default_factory=lambda: ["page", "section", "clause", "microchunk", "table"]
    )

    @field_validator("token_chunk_size")
    @classmethod
    def ensure_positive_chunk_size(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("indexing.token_chunk_size must be positive.")
        return value

    @field_validator("token_chunk_overlap")
    @classmethod
    def ensure_non_negative_chunk_overlap(cls, value: int) -> int:
        if value < 0:
            raise ValueError("indexing.token_chunk_overlap must be non-negative.")
        return value

    @field_validator("enabled_chunk_families")
    @classmethod
    def ensure_non_empty_chunk_families(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            name = str(item).strip()
            if not name or name in seen:
                continue
            normalized.append(name)
            seen.add(name)
        if not normalized:
            raise ValueError("indexing.enabled_chunk_families must include at least one family.")
        return normalized


class RetrievalSettings(BaseModel):
    """Retrieval-stage budgets and optional context expansion controls."""

    model_config = ConfigDict(extra="forbid")

    candidate_budget: int = 10
    rerank_budget: int = 5
    default_evidence_budget: int = 3
    evidence_budget_by_answer_type: dict[str, int] = Field(default_factory=dict)
    question_class_budgets: dict[str, "QuestionClassBudgetSettings"] = Field(default_factory=dict)
    min_rerank_score: float = 0.0
    parent_page_expansion_enabled: bool = False
    parent_page_expansion_limit: int = 0

    @field_validator("candidate_budget", "rerank_budget", "default_evidence_budget", "parent_page_expansion_limit")
    @classmethod
    def ensure_non_negative_int(cls, value: int) -> int:
        if value < 0:
            raise ValueError("retrieval integer settings must be non-negative.")
        return value

    @field_validator("min_rerank_score")
    @classmethod
    def ensure_non_negative_score(cls, value: float) -> float:
        if value < 0:
            raise ValueError("retrieval.min_rerank_score must be non-negative.")
        return value

    @field_validator("evidence_budget_by_answer_type")
    @classmethod
    def ensure_non_negative_budgets(cls, value: dict[str, int]) -> dict[str, int]:
        normalized: dict[str, int] = {}
        for answer_type, budget in value.items():
            key = str(answer_type).strip()
            if not key:
                continue
            budget_value = int(budget)
            if budget_value < 0:
                raise ValueError("retrieval.evidence_budget_by_answer_type budgets must be non-negative.")
            normalized[key] = budget_value
        return normalized

    @field_validator("question_class_budgets")
    @classmethod
    def ensure_normalized_question_class_budgets(
        cls,
        value: dict[str, "QuestionClassBudgetSettings"],
    ) -> dict[str, "QuestionClassBudgetSettings"]:
        normalized: dict[str, QuestionClassBudgetSettings] = {}
        for question_class, budget in value.items():
            key = str(question_class).strip()
            if not key:
                continue
            normalized[key] = budget
        return normalized


class QuestionClassBudgetSettings(BaseModel):
    """Question-class-specific retrieval budgets."""

    model_config = ConfigDict(extra="forbid")

    candidate_budget: int
    rerank_budget: int
    evidence_budget: int

    @field_validator("candidate_budget", "rerank_budget", "evidence_budget")
    @classmethod
    def ensure_non_negative_budget(cls, value: int) -> int:
        if value < 0:
            raise ValueError("question-class budgets must be non-negative.")
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
    answering: AnsweringSettings = Field(default_factory=AnsweringSettings)
    page_attribution: PageAttributionSettings = Field(default_factory=PageAttributionSettings)
    indexing: IndexingSettings = Field(default_factory=IndexingSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
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
    ocr_device_override = env.get("COMPETITION_OCR_DEVICE")
    ocr_enable_hpi_override = env.get("COMPETITION_OCR_ENABLE_HPI")
    ocr_enable_mkldnn_override = env.get("COMPETITION_OCR_ENABLE_MKLDNN")
    ocr_cpu_threads_override = env.get("COMPETITION_OCR_CPU_THREADS")
    ocr_model_root_dir_override = env.get("COMPETITION_OCR_MODEL_ROOT_DIR")
    ocr_text_detection_model_dir_override = env.get("COMPETITION_OCR_TEXT_DETECTION_MODEL_DIR")
    ocr_text_recognition_model_dir_override = env.get("COMPETITION_OCR_TEXT_RECOGNITION_MODEL_DIR")
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

    ingestion_updates: dict[str, Any] = {}
    if enable_ocr_override:
        ingestion_updates["enable_ocr"] = _parse_bool(enable_ocr_override)
    if ocr_unavailable_policy_override:
        ingestion_updates["ocr_unavailable_policy"] = ocr_unavailable_policy_override.strip()
    if ocr_device_override:
        ingestion_updates["ocr_device"] = ocr_device_override.strip()
    if ocr_enable_hpi_override:
        ingestion_updates["ocr_enable_hpi"] = _parse_bool(ocr_enable_hpi_override)
    if ocr_enable_mkldnn_override:
        ingestion_updates["ocr_enable_mkldnn"] = _parse_bool(ocr_enable_mkldnn_override)
    if ocr_cpu_threads_override:
        ingestion_updates["ocr_cpu_threads"] = int(ocr_cpu_threads_override)
    if ocr_model_root_dir_override:
        ingestion_updates["ocr_model_root_dir"] = Path(ocr_model_root_dir_override.strip()).expanduser()
    if ocr_text_detection_model_dir_override:
        ingestion_updates["ocr_text_detection_model_dir"] = Path(
            ocr_text_detection_model_dir_override.strip()
        ).expanduser()
    if ocr_text_recognition_model_dir_override:
        ingestion_updates["ocr_text_recognition_model_dir"] = Path(
            ocr_text_recognition_model_dir_override.strip()
        ).expanduser()

    if ingestion_updates:
        config = config.model_copy(update={"ingestion": config.ingestion.model_copy(update=ingestion_updates)})

    page_attribution_updates: dict[str, Any] = {}
    if pass_a_enabled_override:
        page_attribution_updates["pass_a_enabled"] = _parse_bool(pass_a_enabled_override)
    if page_validation_mode_override:
        page_attribution_updates["validation_mode"] = _parse_page_validation_mode(page_validation_mode_override)
    if page_attribution_updates:
        config = config.model_copy(
            update={"page_attribution": config.page_attribution.model_copy(update=page_attribution_updates)}
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
