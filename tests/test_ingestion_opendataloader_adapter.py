from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.common.config import AppConfig
from src.common.schemas import ParserRoute
from src.ingestion.opendataloader_adapter import (
    OpenDataLoaderExecutionError,
    build_opendataloader_sidecar,
    route_provenance,
)


def _mock_opendataloader_payload() -> dict[str, object]:
    return {
        "file name": "alpha.pdf",
        "number of pages": 1,
        "author": None,
        "title": "Alpha",
        "creation date": None,
        "modification date": None,
        "kids": [
            {
                "type": "heading",
                "id": 1,
                "page number": 1,
                "bounding box": [0.0, 0.0, 10.0, 10.0],
                "heading level": 1,
                "content": "Part 1",
            },
            {
                "type": "caption",
                "id": 9,
                "page number": 1,
                "bounding box": [10.0, 10.0, 20.0, 20.0],
                "content": "Table 1",
                "linked content id": 21,
            },
            {
                "type": "table",
                "id": 21,
                "page number": 1,
                "bounding box": [20.0, 20.0, 100.0, 80.0],
                "rows": [
                    {
                        "type": "table row",
                        "row number": 1,
                        "cells": [
                            {
                                "type": "table cell",
                                "page number": 1,
                                "bounding box": [20, 70, 40, 80],
                                "content": "Name",
                            },
                            {
                                "type": "table cell",
                                "page number": 1,
                                "bounding box": [40, 70, 60, 80],
                                "content": "Value",
                            },
                        ],
                    },
                    {
                        "type": "table row",
                        "row number": 2,
                        "cells": [
                            {
                                "type": "table cell",
                                "page number": 1,
                                "bounding box": [20, 60, 40, 70],
                                "content": "Fee",
                            },
                            {
                                "type": "table cell",
                                "page number": 1,
                                "bounding box": [40, 60, 60, 70],
                                "content": "10",
                            },
                        ],
                    },
                ],
            },
        ],
    }


def test_build_opendataloader_sidecar_adapts_executed_json_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "alpha.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 placeholder")
    config = AppConfig.model_validate({"ingestion": {"enable_ocr": False}})

    def fake_convert(*, pdf_path: Path, output_dir: Path, parser_route: ParserRoute, config: AppConfig) -> None:
        del config
        assert parser_route is ParserRoute.HYBRID
        assert pdf_path.name == "alpha.pdf"
        payload_path = output_dir / "alpha.json"
        payload_path.write_text(json.dumps(_mock_opendataloader_payload()), encoding="utf-8")

    monkeypatch.setattr("src.ingestion.opendataloader_adapter._run_opendataloader_convert", fake_convert)

    sidecar = build_opendataloader_sidecar(
        pdf_path=pdf_path,
        page_geometry={1: [0.0, 0.0, 595.0, 842.0]},
        parser_route=ParserRoute.HYBRID,
        config=config,
    )

    assert sidecar.parser_provenance == "opendataloader:hybrid"
    assert sidecar.diagnostics["adapter_mode"] == "executed"
    assert "opendataloader_convert_executed" in sidecar.route_decisions
    assert any(node.kind == "heading" for node in sidecar.nodes)
    assert any(node.kind == "caption" for node in sidecar.nodes)
    assert any(node.kind == "table" for node in sidecar.nodes)
    assert len(sidecar.tables) == 1
    table = sidecar.tables[0]
    assert table.table_id == "alpha-t21"
    assert table.raw_json is not None

    caption = next(node for node in sidecar.nodes if node.kind == "caption")
    assert caption.linked_content_id == table.table_id


def test_build_opendataloader_sidecar_raises_execution_error_when_convert_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "alpha.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 placeholder")
    config = AppConfig.model_validate({"ingestion": {"enable_ocr": False}})

    def fake_convert(**_kwargs) -> None:
        raise RuntimeError("convert failed")

    monkeypatch.setattr("src.ingestion.opendataloader_adapter._run_opendataloader_convert", fake_convert)

    with pytest.raises(OpenDataLoaderExecutionError):
        build_opendataloader_sidecar(
            pdf_path=pdf_path,
            page_geometry={1: [0.0, 0.0, 595.0, 842.0]},
            parser_route=ParserRoute.LOCAL_ONLY,
            config=config,
        )


def test_build_opendataloader_sidecar_preserves_route_decisions_and_appends_execution_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "alpha.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 placeholder")
    config = AppConfig.model_validate({"ingestion": {"enable_ocr": False}})

    def fake_convert(*, output_dir: Path, **_kwargs) -> None:
        payload_path = output_dir / "alpha.json"
        payload_path.write_text(json.dumps(_mock_opendataloader_payload()), encoding="utf-8")

    monkeypatch.setattr("src.ingestion.opendataloader_adapter._run_opendataloader_convert", fake_convert)

    sidecar = build_opendataloader_sidecar(
        pdf_path=pdf_path,
        page_geometry={1: [0.0, 0.0, 595.0, 842.0]},
        parser_route=ParserRoute.HYBRID,
        config=config,
        route_decisions=["hybrid_selected", "route_reused"],
    )

    assert sidecar.route_decisions == ["hybrid_selected", "route_reused", "opendataloader_convert_executed"]


def test_build_opendataloader_sidecar_rejects_baseline_fallback_route(tmp_path: Path) -> None:
    pdf_path = tmp_path / "alpha.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 placeholder")
    config = AppConfig.model_validate({"ingestion": {"enable_ocr": False}})

    with pytest.raises(ValueError, match="Baseline fallback route"):
        build_opendataloader_sidecar(
            pdf_path=pdf_path,
            page_geometry={1: [0.0, 0.0, 595.0, 842.0]},
            parser_route=ParserRoute.BASELINE_FALLBACK,
            config=config,
        )


def test_route_provenance_maps_structural_routes() -> None:
    assert route_provenance(ParserRoute.TAGGED) == "opendataloader:tagged"
    assert route_provenance(ParserRoute.HYBRID) == "opendataloader:hybrid"
    assert route_provenance(ParserRoute.LOCAL_ONLY) == "opendataloader:local_only"
