# SPDX-License-Identifier: MIT
"""Unit tests for the simple RustChain Prometheus exporter."""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import Mock, patch


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "tools" / "prometheus" / "rustchain_exporter.py"


class FakeGauge:
    def __init__(self, *args, **kwargs):
        self._value = Mock()
        self._value.get.return_value = 0
        self.calls = []

    def labels(self, **labels):
        self.calls.append(labels)
        return self

    def set(self, value):
        self._value.get.return_value = value

    def clear(self):
        self.calls.clear()
        self._value.get.return_value = 0


def load_module():
    prometheus_stub = types.ModuleType("prometheus_client")
    prometheus_stub.Gauge = FakeGauge
    prometheus_stub.start_http_server = Mock()
    sys.modules["prometheus_client"] = prometheus_stub

    spec = importlib.util.spec_from_file_location("rustchain_prometheus_exporter", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_numeric_coercion_helpers_use_defaults_for_bad_values():
    module = load_module()

    assert module._to_float("12.5") == 12.5
    assert module._to_float(None, default=7.0) == 7.0
    assert module._to_float("bad", default=3.0) == 3.0
    assert module._to_int("9") == 9
    assert module._to_int(None, default=4) == 4
    assert module._to_int("bad", default=2) == 2


def test_fetch_json_returns_payload_and_handles_errors():
    module = load_module()
    response = Mock()
    response.json.return_value = {"ok": True}

    with patch.object(module.session, "get", return_value=response) as get:
        assert module.fetch_json("/health") == {"ok": True}

    get.assert_called_once_with(f"{module.NODE_URL}/health", timeout=module.REQUEST_TIMEOUT)

    with patch.object(module.session, "get", side_effect=RuntimeError("offline")):
        assert module.fetch_json("/health") is None


def test_collect_epoch_computes_progress_and_fallback_defaults():
    module = load_module()

    with patch.object(module, "fetch_json", return_value={
        "epoch": "3",
        "slot": "17",
        "blocks_per_epoch": "10",
        "seconds_per_slot": "30",
        "enrolled_miners": "4",
    }):
        result = module.collect_epoch()

    assert result == {
        "enrolled_miners": 4,
        "slot": 17,
        "slots_per_epoch": 10,
        "seconds_per_slot": 30.0,
    }
    assert module.rustchain_current_epoch._value.get() == 3
    assert module.rustchain_current_slot._value.get() == 17
    assert module.rustchain_epoch_slot_progress._value.get() == 0.7
    assert module.rustchain_epoch_seconds_remaining._value.get() == 90

    with patch.object(module, "fetch_json", return_value=None):
        assert module.collect_epoch() == {
            "enrolled_miners": 0,
            "slot": 0,
            "slots_per_epoch": 0,
            "seconds_per_slot": 600,
        }


def test_collect_miners_counts_recent_attestations_and_uses_fallback():
    module = load_module()

    with (
        patch.object(module, "fetch_json", return_value=[
            {"miner": "alice", "arch": "x86", "last_attest": 1_000},
            {"id": "bob", "device_arch": "arm", "last_attest_timestamp": 0},
            "bad-row",
        ]),
        patch.object(module.time, "time", return_value=2_000),
    ):
        module.collect_miners(fallback_enrolled=8)

    assert module.rustchain_active_miners_total._value.get() == 1
    assert module.rustchain_enrolled_miners_total._value.get() == 8

    with patch.object(module, "fetch_json", return_value=None):
        module.collect_miners(fallback_enrolled=5)

    assert module.rustchain_active_miners_total._value.get() == 0
    assert module.rustchain_enrolled_miners_total._value.get() == 5


def test_collect_hall_of_fame_fee_pool_and_stats_fallbacks():
    module = load_module()

    with patch.object(module, "fetch_json", side_effect=[
        {"stats": {
            "total_machines": "3",
            "total_attestations": "7",
            "oldest_year": "1998",
            "highest_rust_score": "9.5",
        }},
        {"total_fees": "12.25", "total_fee_events": "6"},
        {"top_balances": [{"address": "miner1", "balance": "4.5"}]},
    ]):
        module.collect_hall_of_fame()
        module.collect_fee_pool()
        module.collect_stats()

    assert module.rustchain_total_machines._value.get() == 3
    assert module.rustchain_total_attestations._value.get() == 7
    assert module.rustchain_oldest_machine_year._value.get() == 1998
    assert module.rustchain_highest_rust_score._value.get() == 9.5
    assert module.rustchain_total_fees_collected_rtc._value.get() == 12.25
    assert module.rustchain_fee_events_total._value.get() == 6


def test_collect_p2p_exports_health_metrics():
    module = load_module()
    module.P2P_NODE_URL = "https://p2p.rustchain.example"

    with (
        patch.object(module, "fetch_json", return_value={
            "running": True,
            "peer_count": "3",
            "attestation_count": "11",
            "settled_epochs": "4",
            "messages_per_second": "2.5",
            "messages_total": "99",
        }) as fetch_json,
        patch.object(module.time, "time", side_effect=[100.0, 100.25]),
    ):
        module.collect_p2p()

    fetch_json.assert_called_once_with("/p2p/health", module.P2P_NODE_URL)
    assert module.rustchain_p2p_up._value.get() == 1
    assert module.rustchain_p2p_peer_count._value.get() == 3
    assert module.rustchain_p2p_attestation_count._value.get() == 11
    assert module.rustchain_p2p_settled_epochs._value.get() == 4
    assert module.rustchain_p2p_message_rate_per_second._value.get() == 2.5
    assert module.rustchain_p2p_messages_total._value.get() == 99
    assert module.rustchain_p2p_health_latency_seconds._value.get() == 0.25


def test_collect_p2p_skips_when_endpoint_not_configured():
    module = load_module()

    with patch.object(module, "fetch_json") as fetch_json:
        module.collect_p2p()

    fetch_json.assert_not_called()
    assert module.P2P_NODE_URL == ""
    assert module.rustchain_p2p_up._value.get() == 0
    assert module.rustchain_p2p_peer_count._value.get() == 0
    assert module.rustchain_p2p_attestation_count._value.get() == 0
    assert module.rustchain_p2p_settled_epochs._value.get() == 0
    assert module.rustchain_p2p_message_rate_per_second._value.get() == 0
    assert module.rustchain_p2p_messages_total._value.get() == 0
    assert module.rustchain_p2p_health_latency_seconds._value.get() == 0


def test_collect_p2p_zeros_metrics_when_endpoint_unavailable():
    module = load_module()
    module.P2P_NODE_URL = "https://p2p.rustchain.example"

    with (
        patch.object(module, "fetch_json", return_value=None),
        patch.object(module.time, "time", side_effect=[100.0, 100.5]),
    ):
        module.collect_p2p()

    assert module.rustchain_p2p_up._value.get() == 0
    assert module.rustchain_p2p_peer_count._value.get() == 0
    assert module.rustchain_p2p_attestation_count._value.get() == 0
    assert module.rustchain_p2p_settled_epochs._value.get() == 0
    assert module.rustchain_p2p_message_rate_per_second._value.get() == 0
    assert module.rustchain_p2p_messages_total._value.get() == 0
    assert module.rustchain_p2p_health_latency_seconds._value.get() == 0.5
