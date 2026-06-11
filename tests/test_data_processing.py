"""Unit tests for JSON data processing helpers.

SPDX-License-Identifier: Apache-2.0

Extended by alex (OpenClaw AI Agent) for Bounty #2787.
Adds comprehensive coverage while preserving existing tests.
"""

import json

import pytest

from src.utils.data_processing import parse_json_input


# === Original tests (preserved) ===

def test_parse_json_input_returns_object_payload():
    payload = parse_json_input('{"miner": "rtc-node-1", "score": 42}')

    assert payload == {"miner": "rtc-node-1", "score": 42}


def test_parse_json_input_preserves_non_object_json_values():
    payload = parse_json_input('[{"epoch": 7}, {"epoch": 8}]')

    assert payload == [{"epoch": 7}, {"epoch": 8}]


def test_parse_json_input_wraps_decode_errors():
    with pytest.raises(ValueError, match="Invalid JSON input"):
        parse_json_input('{"miner": "rtc-node-1",')


# === Extended tests by alex ===

def test_parse_json_string_value():
    """Should parse a bare JSON string."""
    payload = parse_json_input('"Proof of Antiquity"')
    assert payload == "Proof of Antiquity"


def test_parse_json_number_value():
    """Should parse a bare JSON number."""
    payload = parse_json_input("42")
    assert payload == 42
    assert isinstance(payload, int)


def test_parse_json_boolean_true():
    """Should parse JSON true."""
    payload = parse_json_input("true")
    assert payload is True


def test_parse_json_null():
    """Should parse JSON null."""
    payload = parse_json_input("null")
    assert payload is None


def test_parse_deeply_nested_structure():
    """Should handle nested PoA config format."""
    data = {
        "chain": "RustChain",
        "consensus": {
            "type": "PoA",
            "layers": ["oscillator", "cache", "simd", "thermal"]
        },
        "architectures": ["PowerPC", "SPARC", "MIPS"]
    }
    payload = parse_json_input(json.dumps(data))
    assert payload["chain"] == "RustChain"
    assert payload["consensus"]["type"] == "PoA"
    assert len(payload["consensus"]["layers"]) == 4


def test_parse_empty_object():
    """Should parse empty JSON object."""
    payload = parse_json_input("{}")
    assert payload == {}


def test_parse_empty_array():
    """Should parse empty JSON array."""
    payload = parse_json_input("[]")
    assert payload == []


def test_whitespace_handling():
    """Should handle leading/trailing whitespace."""
    payload = parse_json_input('   {"key": "value"}   ')
    assert payload == {"key": "value"}


def test_unicode_content():
    """Should handle Unicode (Chinese, emoji)."""
    payload = parse_json_input('{"msg": "复古硬件", "icon": "🖥️"}')
    assert payload["msg"] == "复古硬件"
    assert payload["icon"] == "🖥️"


def test_large_json_structure():
    """Should handle 1000-node JSON efficiently."""
    data = {"nodes": [{"id": i, "arch": "PowerPC"} for i in range(1000)]}
    payload = parse_json_input(json.dumps(data))
    assert len(payload["nodes"]) == 1000
    assert payload["nodes"][999]["id"] == 999


def test_malformed_json_variants():
    """Should raise ValueError for various malformed inputs."""
    bad_inputs = [
        '{"unclosed": "string}',
        "[1, 2,",
        "just_plain_text",
    ]
    for inp in bad_inputs:
        with pytest.raises(ValueError, match="Invalid JSON input"):
            parse_json_input(inp)


def test_empty_string_raises_error():
    """Should raise ValueError for empty string."""
    with pytest.raises(ValueError, match="Invalid JSON input"):
        parse_json_input("")
