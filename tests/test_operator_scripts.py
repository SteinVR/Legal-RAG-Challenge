from __future__ import annotations

from pathlib import Path


def test_00_check_env_supports_shared_root_runtime_and_env_contract() -> None:
    script = Path("scripts/00_check_env.sh").read_text(encoding="utf-8")

    assert "git -C \"$PROJECT_ROOT\" rev-parse --path-format=absolute --git-common-dir" in script
    assert "elif [ -x \"$COMMON_ROOT/.venv/bin/python\" ]" in script
    assert "elif [ -f \"$COMMON_ROOT/.env\" ]" in script
    assert "echo \"Common root: $COMMON_ROOT\"" in script


def test_02_download_models_verify_contract_covers_retrieval_gpu_smoke_and_ocr_gpu_init() -> None:
    script = Path("scripts/02_download_models.sh").read_text(encoding="utf-8")

    assert "load_app_config" in script
    assert "SentenceTransformer(" in script
    assert "if not torch.cuda.is_available():" in script
    assert "verify_ocr_cache" in script
    assert 'device="gpu:0"' in script
    assert "OCR GPU init OK" in script


def test_02_download_models_download_contract_provisions_ocr_cache_and_accepts_config_overrides() -> None:
    script = Path("scripts/02_download_models.sh").read_text(encoding="utf-8")

    assert "--config PATH" in script
    assert "--env-file PATH" in script
    assert "ensure_ocr_cache" in script
    assert "PaddleOCR(" in script
    assert 'device="cpu"' in script
