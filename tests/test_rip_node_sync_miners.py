# SPDX-License-Identifier: MIT
"""Regression tests for RIP node sync miner payload normalization."""

from node import rip_node_sync


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_fetch_peer_attestations_accepts_current_miners_envelope(monkeypatch):
    calls = []

    def fake_get(url, timeout):
        calls.append((url, timeout))
        if url.endswith("/api/attestations"):
            return FakeResponse(404, {"error": "not found"})
        return FakeResponse(200, {
            "miners": [
                {"miner_id": "alice", "device_arch": "G4"},
                {"id": "bob", "device_arch": "x86"},
                {"device_arch": "missing-id"},
            ],
            "pagination": {"total": 3, "limit": 100, "offset": 0},
        })

    monkeypatch.setattr(rip_node_sync.requests, "get", fake_get)

    assert rip_node_sync.fetch_peer_attestations("https://peer.example") == [
        {"miner_id": "alice", "device_arch": "G4", "miner": "alice"},
        {"id": "bob", "device_arch": "x86", "miner": "bob"},
    ]
    assert calls == [
        ("https://peer.example/api/attestations", 10),
        ("https://peer.example/api/miners", 10),
    ]


def test_fetch_peer_attestations_accepts_legacy_list_payload(monkeypatch):
    def fake_get(url, timeout):
        if url.endswith("/api/attestations"):
            return FakeResponse(200, [{"miner": "carol", "device_arch": "POWER8"}])
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(rip_node_sync.requests, "get", fake_get)

    assert rip_node_sync.fetch_peer_attestations("https://peer.example") == [
        {"miner": "carol", "device_arch": "POWER8"},
    ]
