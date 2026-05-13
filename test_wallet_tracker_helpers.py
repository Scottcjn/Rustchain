import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).parent / "wallet-tracker" / "test_tracker.py"


def load_tracker_module():
    spec = importlib.util.spec_from_file_location("wallet_tracker_test_script", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_format_number_uses_plain_comma_and_million_suffixes():
    tracker = load_tracker_module()

    assert tracker.format_number(999) == "999"
    assert tracker.format_number(1_000) == "1,000"
    assert tracker.format_number(1_234_567) == "1.23M"


def test_calculate_gini_handles_empty_zero_and_equal_distributions():
    tracker = load_tracker_module()

    assert tracker.calculate_gini([]) == 0
    assert tracker.calculate_gini([0, 0, 0]) == 0
    assert tracker.calculate_gini([10, 10, 10]) == pytest.approx(0)


def test_calculate_gini_is_order_independent_for_unequal_balances():
    tracker = load_tracker_module()

    forward = tracker.calculate_gini([0, 10, 30, 60])
    reversed_order = tracker.calculate_gini([60, 30, 10, 0])

    assert forward == pytest.approx(reversed_order)
    assert forward > 0


def test_get_balance_returns_zero_balance_payload_on_request_failure(monkeypatch):
    tracker = load_tracker_module()

    def raise_request_error(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(tracker.requests, "get", raise_request_error)

    assert tracker.get_balance("miner-123") == {
        "miner_id": "miner-123",
        "balance_rtc": 0,
        "balance_i64": 0,
    }
