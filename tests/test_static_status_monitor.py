import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "static" / "status" / "monitor.py"


def load_monitor_module():
    spec = importlib.util.spec_from_file_location("static_status_monitor", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_check_nodes_records_success_and_failure_without_network(tmp_path, monkeypatch):
    monitor = load_monitor_module()
    data_file = tmp_path / "node_status.json"
    monkeypatch.setattr(monitor, "DATA_FILE", str(data_file))
    monkeypatch.setattr(
        monitor,
        "NODES",
        [
            {"name": "Node A", "url": "https://node-a/health", "location": "A"},
            {"name": "Node B", "url": "https://node-b/health", "location": "B"},
        ],
    )

    ok_response = Mock()
    ok_response.status_code = 200
    ok_response.json.return_value = {
        "version": "2.2.1",
        "active_miners": 17,
        "current_epoch": 42,
    }

    def fake_get(url, timeout, verify):
        if url == "https://node-a/health":
            return ok_response
        raise monitor.requests.exceptions.Timeout("timed out")

    get = Mock(side_effect=fake_get)
    monkeypatch.setattr(monitor.requests, "get", get)

    results = monitor.check_nodes()

    assert results[0] == {
        "name": "Node A",
        "url": "https://node-a/health",
        "location": "A",
        "status": "up",
        "latency_ms": results[0]["latency_ms"],
        "version": "2.2.1",
        "miners": 17,
        "epoch": 42,
        "timestamp": results[0]["timestamp"],
    }
    assert results[1]["status"] == "down"
    assert results[1]["error"] == "timed out"
    assert get.call_count == 2

    history = json.loads(data_file.read_text())
    assert len(history) == 1
    assert history[0]["nodes"] == results


def test_check_nodes_appends_history_and_keeps_recent_entries(tmp_path, monkeypatch):
    monitor = load_monitor_module()
    data_file = tmp_path / "node_status.json"
    old_history = [{"time": f"old-{i}", "nodes": []} for i in range(1440)]
    data_file.write_text(json.dumps(old_history))

    monkeypatch.setattr(monitor, "DATA_FILE", str(data_file))
    monkeypatch.setattr(
        monitor,
        "NODES",
        [{"name": "Node A", "url": "https://node-a/health", "location": "A"}],
    )

    response = Mock()
    response.status_code = 503
    monkeypatch.setattr(monitor.requests, "get", Mock(return_value=response))

    monitor.check_nodes()

    history = json.loads(data_file.read_text())
    assert len(history) == 1440
    assert history[0]["time"] == "old-1"
    assert history[-1]["nodes"][0]["status"] == "down"
    assert history[-1]["nodes"][0]["error"] == "HTTP 503"
