from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

import fitz
import numpy
import pytest

from src.common.config import AppConfig
from src.ingestion.ocr_engine import OcrUnavailableError, PaddleOcrEngine, _extract_ocr_lines_v3


def test_extract_ocr_lines_v3_accepts_numpy_dt_polys_from_object_results() -> None:
    result = SimpleNamespace(
        dt_polys=numpy.array(
            [
                [[0, 0], [10, 0], [10, 4], [0, 4]],
                [[0, 8], [12, 8], [12, 12], [0, 12]],
            ]
        ),
        rec_texts=["First line", "Second line"],
    )

    lines = _extract_ocr_lines_v3([result])

    assert [line.text for line in lines] == ["First line", "Second line"]
    assert lines[0].bbox == (0.0, 0.0, 10.0, 4.0)
    assert lines[1].bbox == (0.0, 8.0, 12.0, 12.0)


def test_extract_ocr_lines_v3_supports_mapping_results_when_attributes_are_missing() -> None:
    lines = _extract_ocr_lines_v3(
        [
            {
                "dt_polys": [[[1, 2], [5, 2], [5, 6], [1, 6]]],
                "rec_texts": ["Clause 1"],
            }
        ]
    )

    assert [line.text for line in lines] == ["Clause 1"]
    assert lines[0].bbox == (1.0, 2.0, 5.0, 6.0)


def test_paddle_ocr_engine_builds_gpu_client_with_local_cached_models(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    det_dir = tmp_path / "PP-OCRv5_server_det"
    rec_dir = tmp_path / "en_PP-OCRv5_mobile_rec"
    det_dir.mkdir()
    rec_dir.mkdir()

    settings = AppConfig.model_validate(
        {
            "ingestion": {
                "ocr_device": "gpu:0",
                "ocr_model_root_dir": str(tmp_path),
            }
        }
    ).ingestion
    engine = PaddleOcrEngine(settings)

    captured: dict[str, object] = {}

    class RecordingPaddleOCR:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def predict(self, image):
            del image
            return []

    monkeypatch.setattr("src.ingestion.ocr_engine._cuda_device_count", lambda: 1)
    monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(PaddleOCR=RecordingPaddleOCR))

    engine._get_client()

    assert captured["device"] == "gpu:0"
    assert captured["enable_hpi"] is False
    assert captured["use_doc_orientation_classify"] is False
    assert captured["use_doc_unwarping"] is False
    assert captured["use_textline_orientation"] is False
    assert captured["text_det_limit_side_len"] == 736
    assert captured["text_detection_model_name"] == "PP-OCRv5_server_det"
    assert captured["text_detection_model_dir"] == str(det_dir)
    assert captured["text_recognition_batch_size"] == 1
    assert captured["text_recognition_model_name"] == "en_PP-OCRv5_mobile_rec"
    assert captured["text_recognition_model_dir"] == str(rec_dir)


def test_paddle_ocr_engine_prefers_model_names_declared_in_cached_model_configs(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    det_dir = tmp_path / "PP-OCRv5_server_det"
    rec_dir = tmp_path / "en_PP-OCRv5_mobile_rec"
    det_dir.mkdir()
    rec_dir.mkdir()
    (det_dir / "config.json").write_text(json.dumps({"Global": {"model_name": "det-from-config"}}), encoding="utf-8")
    (rec_dir / "config.json").write_text(json.dumps({"Global": {"model_name": "rec-from-config"}}), encoding="utf-8")

    settings = AppConfig.model_validate(
        {
            "ingestion": {
                "ocr_device": "gpu:0",
                "ocr_model_root_dir": str(tmp_path),
            }
        }
    ).ingestion
    engine = PaddleOcrEngine(settings)

    captured: dict[str, object] = {}

    class RecordingPaddleOCR:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def predict(self, image):
            del image
            return []

    monkeypatch.setattr("src.ingestion.ocr_engine._cuda_device_count", lambda: 1)
    monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(PaddleOCR=RecordingPaddleOCR))

    engine._get_client()

    assert captured["text_detection_model_name"] == "det-from-config"
    assert captured["text_recognition_model_name"] == "rec-from-config"


def test_paddle_ocr_engine_sets_offline_model_source_guard_before_initialization(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    det_dir = tmp_path / "PP-OCRv5_server_det"
    rec_dir = tmp_path / "en_PP-OCRv5_mobile_rec"
    det_dir.mkdir()
    rec_dir.mkdir()

    settings = AppConfig.model_validate(
        {
            "ingestion": {
                "ocr_device": "gpu:0",
                "ocr_model_root_dir": str(tmp_path),
            }
        }
    ).ingestion
    engine = PaddleOcrEngine(settings)

    class RecordingPaddleOCR:
        def __init__(self, **kwargs):
            del kwargs

        def predict(self, image):
            del image
            return []

    monkeypatch.setattr("src.ingestion.ocr_engine._cuda_device_count", lambda: 1)
    monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(PaddleOCR=RecordingPaddleOCR))
    monkeypatch.delenv("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", raising=False)

    engine._get_client()

    assert os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] == "True"


def test_paddle_ocr_engine_raises_when_gpu_requested_but_no_cuda_devices_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = AppConfig.model_validate({"ingestion": {"ocr_device": "gpu:0"}}).ingestion
    engine = PaddleOcrEngine(settings)

    monkeypatch.setattr("src.ingestion.ocr_engine._cuda_device_count", lambda: 0)

    with pytest.raises(OcrUnavailableError, match="GPU"):
        engine._get_client()


def test_paddle_ocr_engine_wraps_runtime_predict_failures_as_unavailable(
    tmp_path,
) -> None:
    pdf_path = tmp_path / "ocr.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "OCR")
    document.save(pdf_path)
    document.close()

    settings = AppConfig.model_validate({"ingestion": {"ocr_device": "gpu:0"}}).ingestion
    engine = PaddleOcrEngine(settings)

    class FailingClient:
        def predict(self, image):
            del image
            raise NotImplementedError("onednn failure")

    engine._ocr_client = FailingClient()

    with fitz.open(pdf_path) as document:
        with pytest.raises(OcrUnavailableError, match="OCR runtime failed"):
            engine.extract_page(document[0])
