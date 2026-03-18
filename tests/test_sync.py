from __future__ import annotations

import json
from pathlib import Path

from src.common.config import AppConfig
from src.submission.sync import PhaseSyncService


def test_download_documents_no_extract_removes_stale_pdfs(tmp_path: Path) -> None:
    config = AppConfig.model_validate({"phase": "warmup", "storage": {"root_dir": tmp_path}})
    service = PhaseSyncService(config)
    service.paths.ensure_directories()

    service.paths.documents_archive_path.write_bytes(b"zip-bytes")
    service.paths.documents_extract_dir.mkdir(parents=True, exist_ok=True)
    (service.paths.documents_extract_dir / "stale.pdf").write_bytes(b"%PDF-1.4 stale")

    result = service.download_documents(
        client=None,
        dry_run=False,
        overwrite=False,
        extract_documents=False,
    )

    manifest = json.loads(service.paths.manifest_path.read_text(encoding="utf-8"))
    assert not service.paths.documents_extract_dir.exists()
    assert result.extracted_pdf_count is None
    assert "extracted_pdfs" not in manifest["artifacts"]
