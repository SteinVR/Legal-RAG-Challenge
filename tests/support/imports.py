from __future__ import annotations

import importlib
from typing import Any

import pytest


def load_module(import_path: str, *, feature: str) -> Any:
    try:
        return importlib.import_module(import_path)
    except ModuleNotFoundError as exc:
        pytest.fail(f"{feature} missing: expected `{import_path}`. {exc}")


def load_page_attribution_module() -> Any:
    return load_module("src.answering.page_attribution", feature="W4A page attribution contract")


def load_indexing_module() -> Any:
    return load_module("src.indexing.service", feature="W3A indexing service module")
