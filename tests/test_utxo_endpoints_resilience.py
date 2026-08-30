#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Tests for UTXO Endpoints Safe Deserialization:
- Handling null/None registers_json and tokens_json without throwing TypeError
- Fallback to safe defaults on malformed JSON
- Valid JSON parsing verification
"""

import os
import sys
import types

# Provide lightweight mock for Flask if running in minimal test environment
if "flask" not in sys.modules:
    flask_mock = types.ModuleType("flask")
    flask_mock.Blueprint = lambda *a, **k: types.SimpleNamespace(route=lambda *a, **k: (lambda f: f))
    flask_mock.request = types.SimpleNamespace(args={})
    flask_mock.jsonify = lambda d, *a: d
    sys.modules["flask"] = flask_mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "node"))

from utxo_endpoints import _safe_json_loads


def test_safe_json_loads_handles_none_and_non_strings():
    assert _safe_json_loads(None, {}) == {}
    assert _safe_json_loads(None, []) == []
    assert _safe_json_loads(123, {}) == {}
    assert _safe_json_loads(True, {"default": 1}) == {"default": 1}


def test_safe_json_loads_handles_corrupt_json():
    assert _safe_json_loads("{malformed json", {}) == {}
    assert _safe_json_loads("[unclosed array", []) == []


def test_safe_json_loads_parses_valid_json():
    assert _safe_json_loads('{"R4": "0x123"}', {}) == {"R4": "0x123"}
    assert _safe_json_loads('[{"token_id": "tok_1", "amount": 100}]', []) == [{"token_id": "tok_1", "amount": 100}]
    assert _safe_json_loads('{}', None) == {}
    assert _safe_json_loads('[]', None) == []


if __name__ == "__main__":
    test_safe_json_loads_handles_none_and_non_strings()
    test_safe_json_loads_handles_corrupt_json()
    test_safe_json_loads_parses_valid_json()
    print("ALL UTXO RESILIENCE TESTS PASSED (3/3 test groups)")
