from __future__ import annotations

from types import SimpleNamespace

import numpy

from src.ingestion.ocr_engine import _extract_ocr_lines_v3


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
