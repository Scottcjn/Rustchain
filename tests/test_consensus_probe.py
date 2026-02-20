from types import SimpleNamespace

import requests

import consensus_probe as cp


def _response(payload):
    return SimpleNamespace(
        json=lambda: payload,
        raise_for_status=lambda: None,
    )


def test_detect_divergence_flags_split_state():
    snapshots = [
        cp.NodeSnapshot(
            node="n1",
            ok=True,
            version="2.2.1-rip200",
            enrolled_miners=49,
            miners_count=40,
            total_balance=215303.907415,
            error=None,
        ),
        cp.NodeSnapshot(
            node="n2",
            ok=True,
            version="2.2.1-rip200",
            enrolled_miners=0,
            miners_count=0,
            total_balance=50332000.0,
            error=None,
        ),
    ]

    issues = cp.detect_divergence(snapshots, balance_tolerance=1e-6)

    assert "divergence_enrolled_miners" in issues
    assert "divergence_miners_count" in issues
    assert "divergence_total_balance" in issues


def test_detect_divergence_ignores_tiny_balance_jitter():
    snapshots = [
        cp.NodeSnapshot("n1", True, "2.2.1-rip200", 10, 10, 100.0000001, None),
        cp.NodeSnapshot("n2", True, "2.2.1-rip200", 10, 10, 100.0000002, None),
    ]

    issues = cp.detect_divergence(snapshots, balance_tolerance=1e-5)

    assert "divergence_total_balance" not in issues


def test_collect_snapshot_success():
    payloads = {
        "/health": {"ok": True, "version": "2.2.1-rip200"},
        "/epoch": {"enrolled_miners": 12},
        "/api/stats": {"total_balance": 123.45},
        "/api/miners": [{"miner": "a"}, {"miner": "b"}],
    }

    def fake_fetcher(url, timeout):
        for endpoint, payload in payloads.items():
            if url.endswith(endpoint):
                return _response(payload)
        raise AssertionError(f"unexpected url {url}")

    snap = cp.collect_snapshot("http://node", timeout_s=3, fetcher=fake_fetcher)

    assert snap.error is None
    assert snap.ok is True
    assert snap.version == "2.2.1-rip200"
    assert snap.enrolled_miners == 12
    assert snap.miners_count == 2
    assert snap.total_balance == 123.45


def test_collect_snapshot_error():
    def failing_fetcher(url, timeout):
        raise requests.RequestException("boom")

    snap = cp.collect_snapshot("http://node", timeout_s=3, fetcher=failing_fetcher)

    assert snap.ok is False
    assert snap.error is not None
