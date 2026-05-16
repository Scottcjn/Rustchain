import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "static" / "bridge" / "update_stats.py"


def load_update_stats_module():
    spec = importlib.util.spec_from_file_location("static_bridge_update_stats", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def response(status_code, payload):
    res = Mock()
    res.status_code = status_code
    res.json.return_value = payload
    return res


def test_get_bridge_stats_uses_max_locked_value_and_first_ledger(tmp_path, monkeypatch):
    stats = load_update_stats_module()
    data_file = tmp_path / "bridge_status.json"
    monkeypatch.setattr(stats, "DATA_FILE", str(data_file))
    monkeypatch.setattr(
        stats,
        "BRIDGE_NODES",
        [
            {"name": "Node 1", "url": "https://node-1/bridge/stats"},
            {"name": "Node 2", "url": "https://node-2/bridge/stats"},
        ],
    )
    monkeypatch.setattr(stats.os.path, "exists", Mock(return_value=False))

    def fake_get(url, timeout, verify):
        if url == "https://node-1/bridge/stats":
            return response(200, {
                "all_time": {"total_rtc_locked": 10},
                "by_chain": {"solana": {"bridged_count": 3}},
            })
        if url == "https://node-2/bridge/stats":
            return response(200, {
                "all_time": {"total_rtc_locked": 25},
                "by_chain": {"solana": {"bridged_count": 5}},
            })
        if url == "https://node-1/bridge/ledger?limit=10":
            return response(200, {"locks": [{"tx": "abc"}]})
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(stats.requests, "get", Mock(side_effect=fake_get))

    result = stats.get_bridge_stats()

    assert result["total_locked_rtc"] == 25
    assert result["recent_transactions"] == [{"tx": "abc"}]
    assert result["bridge_nodes"] == [
        {"name": "Node 1", "status": "up", "total_locked": 10, "completed_count": 3},
        {"name": "Node 2", "status": "up", "total_locked": 25, "completed_count": 5},
    ]
    assert json.loads(data_file.read_text()) == result


def test_get_bridge_stats_records_down_nodes_and_empty_ledger(tmp_path, monkeypatch):
    stats = load_update_stats_module()
    data_file = tmp_path / "bridge_status.json"
    monkeypatch.setattr(stats, "DATA_FILE", str(data_file))
    monkeypatch.setattr(
        stats,
        "BRIDGE_NODES",
        [{"name": "Node 1", "url": "https://node-1/bridge/stats"}],
    )
    monkeypatch.setattr(stats.os.path, "exists", Mock(return_value=False))
    monkeypatch.setattr(
        stats.requests,
        "get",
        Mock(side_effect=stats.requests.exceptions.Timeout("timed out")),
    )

    result = stats.get_bridge_stats()

    assert result["total_locked_rtc"] == 0
    assert result["recent_transactions"] == []
    assert result["bridge_nodes"] == [
        {"name": "Node 1", "status": "down", "error": "timed out"}
    ]
    assert json.loads(data_file.read_text()) == result
