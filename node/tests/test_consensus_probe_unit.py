# SPDX-License-Identifier: MIT
import pytest

from node.consensus_probe import (
    NodeSnapshot,
    collect_snapshot,
    detect_divergence,
    run_probe,
)


def snapshot(**overrides):
    data = {
        "node": "https://node-a.example",
        "ok": True,
        "version": "1.0.0",
        "enrolled_miners": 3,
        "miners_count": 3,
        "total_balance": 42.0,
        "error": None,
    }
    data.update(overrides)
    return NodeSnapshot(**data)


def test_collect_snapshot_reads_expected_endpoints():
    calls = []
    payloads = {
        "https://node.example/health": {"ok": True, "version": "2.1.0"},
        "https://node.example/epoch": {"enrolled_miners": 5},
        "https://node.example/api/stats": {"total_balance": 12.5},
        "https://node.example/api/miners": [{"id": "a"}, {"id": "b"}],
    }

    def fetcher(url, timeout):
        calls.append((url, timeout))
        return payloads[url]

    result = collect_snapshot("https://node.example/", timeout_s=4, fetcher=fetcher)

    assert result == NodeSnapshot(
        node="https://node.example/",
        ok=True,
        version="2.1.0",
        enrolled_miners=5,
        miners_count=2,
        total_balance=12.5,
        error=None,
    )
    assert calls == [
        ("https://node.example/health", 4),
        ("https://node.example/epoch", 4),
        ("https://node.example/api/stats", 4),
        ("https://node.example/api/miners", 4),
    ]


def test_collect_snapshot_reports_fetch_errors():
    def failing_fetcher(url, timeout):
        raise RuntimeError("boom")

    result = collect_snapshot("https://down.example", fetcher=failing_fetcher)

    assert result.node == "https://down.example"
    assert result.ok is False
    assert result.error == "boom"
    assert result.version is None
    assert result.miners_count is None


def test_detect_divergence_flags_unreachable_and_insufficient_nodes():
    issues = detect_divergence([snapshot(error="timeout", ok=False)])

    assert issues == ["unreachable_nodes:https://node-a.example", "insufficient_healthy_nodes"]


def test_detect_divergence_flags_version_and_state_mismatches():
    issues = detect_divergence([
        snapshot(node="a", version="1.0.0", enrolled_miners=3, miners_count=3, total_balance=10.0),
        snapshot(node="b", version="1.1.0", enrolled_miners=4, miners_count=5, total_balance=12.0),
    ])

    assert "version_mismatch:1.0.0,1.1.0" in issues
    assert "divergence_enrolled_miners" in issues
    assert "divergence_miners_count" in issues
    assert "divergence_total_balance" in issues


def test_detect_divergence_respects_balance_tolerance():
    issues = detect_divergence([
        snapshot(node="a", total_balance=10.0),
        snapshot(node="b", total_balance=10.05),
    ], balance_tolerance=0.1)

    assert issues == []


def test_run_probe_returns_success_report(monkeypatch):
    def fake_collect(node, timeout_s=8):
        return snapshot(node=node)

    monkeypatch.setattr("node.consensus_probe.collect_snapshot", fake_collect)

    code, report = run_probe(["a", "b"], timeout_s=2)

    assert code == 0
    assert report["issues"] == []
    assert [node["node"] for node in report["nodes"]] == ["a", "b"]
    assert report["timestamp_utc"].endswith("Z")


def test_run_probe_returns_divergence_exit_code(monkeypatch):
    snapshots = [snapshot(node="a", version="1.0.0"), snapshot(node="b", version="2.0.0")]

    def fake_collect(node, timeout_s=8):
        return snapshots.pop(0)

    monkeypatch.setattr("node.consensus_probe.collect_snapshot", fake_collect)

    code, report = run_probe(["a", "b"])

    assert code == 2
    assert report["issues"] == ["version_mismatch:1.0.0,2.0.0"]
