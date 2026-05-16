# SPDX-License-Identifier: MIT

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parent / "src" / "utils" / "data_processing.py"
SPEC = importlib.util.spec_from_file_location("data_processing", MODULE_PATH)
data_processing = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(data_processing)


def test_parse_json_input_returns_nested_objects():
    payload = '{"miner": "RTC123", "stats": {"blocks": 4, "active": true}}'

    assert data_processing.parse_json_input(payload) == {
        "miner": "RTC123",
        "stats": {"blocks": 4, "active": True},
    }


def test_parse_json_input_preserves_json_arrays():
    assert data_processing.parse_json_input('["g4", "g5", "power8"]') == [
        "g4",
        "g5",
        "power8",
    ]


def test_parse_json_input_wraps_decode_errors():
    with pytest.raises(ValueError) as exc_info:
        data_processing.parse_json_input('{"miner": "RTC123",}')

    message = str(exc_info.value)
    assert message.startswith("Invalid JSON input: ")
    assert "line 1 column" in message
