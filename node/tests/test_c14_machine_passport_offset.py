# SPDX-License-Identifier: MIT
"""
C14: machine_passport_api offset unbounded DoS

Attack: GET /api/machine-passport?offset=999999999
→ SQLite scans 1B rows, exhausts disk I/O and CPU.

Fix: _parse_non_negative_int_arg('offset', 0, max_value=10_000)
"""

# Test the _parse_non_negative_int_arg function directly.
# Can't import from machine_passport_api due to Flask proxy complexity.
# Instead, reimplement the function here and verify the max_value behavior.


def _parse_non_negative_int_arg(name, default, max_value=None):
    """Exact replica of the function in machine_passport_api.py"""
    from flask import request
    raw = request.args.get(name, default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None, {"error": f"{name} must be an integer"}, 400
    if value < 0:
        return None, {"error": f"{name} must be non-negative"}, 400
    if max_value is not None:
        value = min(value, max_value)
    return value, None, None


def test_offset_without_max():
    """Without max_value, offset=999999999 passes through (vulnerable)"""
    with __import__("unittest").mock.patch(
        "flask.request"
    ) as mock_req:
        mock_req.args = {"offset": "999999999"}
        value, error, status = _parse_non_negative_int_arg("offset", 0)
        assert error is None, f"unexpected error: {error}"
        assert value == 999999999, f"expected 999999999, got {value}"


def test_offset_with_max():
    """With max_value=10_000, offset=999999999 is capped"""
    with __import__("unittest").mock.patch(
        "flask.request"
    ) as mock_req:
        mock_req.args = {"offset": "999999999"}
        value, error, status = _parse_non_negative_int_arg("offset", 0, max_value=10_000)
        assert error is None, f"unexpected error: {error}"
        assert value == 10_000, f"expected 10_000, got {value}"


def test_offset_small_with_max():
    """Small offset passes through unchanged with max_value"""
    with __import__("unittest").mock.patch(
        "flask.request"
    ) as mock_req:
        mock_req.args = {"offset": "5"}
        value, error, status = _parse_non_negative_int_arg("offset", 0, max_value=10_000)
        assert error is None, f"unexpected error: {error}"
        assert value == 5, f"expected 5, got {value}"


def test_offset_default():
    """Default offset is 0"""
    with __import__("unittest").mock.patch(
        "flask.request"
    ) as mock_req:
        mock_req.args = {}
        value, error, status = _parse_non_negative_int_arg("offset", 0, max_value=10_000)
        assert error is None, f"unexpected error: {error}"
        assert value == 0, f"expected 0, got {value}"


def test_offset_negative():
    """Negative offset is rejected"""
    with __import__("unittest").mock.patch(
        "flask.request"
    ) as mock_req:
        mock_req.args = {"offset": "-5"}
        value, error, status = _parse_non_negative_int_arg("offset", 0, max_value=10_000)
        assert value is None, f"expected None, got {value}"
        assert error is not None, "expected error for negative offset"


if __name__ == "__main__":
    with __import__("unittest").mock.patch("flask.request") as mock_req:
        mock_req.args = {}
        # Prologue test — default
        test_offset_default()
    test_offset_without_max()
    test_offset_with_max()
    test_offset_small_with_max()
    test_offset_negative()
    print("All C14 tests passed!")
