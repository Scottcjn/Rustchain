# SPDX-License-Identifier: MIT
"""Regression tests for ledger verifier miner pagination."""

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "monitoring" / "ledger_verify.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ledger_verify", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_query_node_fetches_paginated_miners_before_hashing(monkeypatch):
    module = load_module()
    fetched_urls = []
    page_one = [{"miner_id": "alice"}, {"miner_id": "bob"}]
    page_two = [{"miner_id": "carol"}]

    def fake_fetch(url):
        fetched_urls.append(url)
        if url == "https://node.example/health":
            return {"version": "1.0"}
        if url == "https://node.example/epoch":
            return {"epoch": 7, "slot": 3, "enrolled_miners": 3}
        if url == "https://node.example/api/stats":
            return {"total_balance": 42, "total_miners": 3}
        if url == f"https://node.example/wallet/balance?miner_id={module.SPOT_CHECK_WALLET}":
            return {"balance": 10}
        if url == "https://node.example/api/miners":
            return {
                "miners": page_one,
                "pagination": {"limit": 2, "offset": 0, "total": 3},
            }
        if url == "https://node.example/api/miners?limit=2&offset=2":
            return {
                "miners": page_two,
                "pagination": {"limit": 2, "offset": 2, "total": 3},
            }
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(module, "fetch", fake_fetch)

    snapshot = module.query_node({
        "name": "Example",
        "url": "https://node.example",
        "id": "node-a",
    })

    all_miners = page_one + page_two
    assert snapshot["active_miner_count"] == 3
    assert snapshot["merkle_root"] == module.compute_merkle_root(all_miners)
    assert snapshot["raw_data"]["miners_sample"] == all_miners
    assert "https://node.example/api/miners?limit=2&offset=2" in fetched_urls


def test_fetch_miners_keeps_legacy_list_shape(monkeypatch):
    module = load_module()
    miners = [{"miner_id": "alice"}, {"miner_id": "bob"}]
    fetched_urls = []

    def fake_fetch(url):
        fetched_urls.append(url)
        return miners

    monkeypatch.setattr(module, "fetch", fake_fetch)

    assert module.fetch_miners("https://node.example") == (miners, None)
    assert fetched_urls == ["https://node.example/api/miners"]


def _fake_fetch_with_balance(module, balance_payload):
    """Return a fake fetch that serves a minimal reachable node and the given
    spot-check balance payload."""
    balance_url = f"https://node.example/wallet/balance?miner_id={module.SPOT_CHECK_WALLET}"

    def fake_fetch(url):
        if url == "https://node.example/health":
            return {"version": "1.0"}
        if url == balance_url:
            return balance_payload
        if url == "https://node.example/api/miners":
            return {"miners": []}
        # epoch / stats absent — not needed for this test
        return None

    return fake_fetch


def test_query_node_preserves_zero_spot_balance(monkeypatch):
    """A spot-check balance of 0 must be kept, not coerced to None. Coercing it
    would drop the node from compare_nodes' balance set and hide a real
    0-vs-nonzero mismatch."""
    module = load_module()
    monkeypatch.setattr(module, "fetch",
                        _fake_fetch_with_balance(module, {"balance": 0}))

    snapshot = module.query_node({
        "name": "Zero", "url": "https://node.example", "id": "node-zero",
    })
    assert snapshot["spot_balance"] == 0

    # End-to-end: node reporting 0 vs peers reporting 5000 must be flagged.
    peer = {"node_id": "node-peer", "reachable": True, "spot_balance": 5000}
    compared = module.compare_nodes([snapshot, peer])
    assert compared["balance_match"] is False
    assert any("BALANCE MISMATCH" in m for m in compared["mismatches"])


def test_query_node_falls_back_to_rtc_balance_when_balance_absent(monkeypatch):
    """When the `balance` key is missing entirely, fall back to `rtc_balance`."""
    module = load_module()
    monkeypatch.setattr(module, "fetch",
                        _fake_fetch_with_balance(module, {"rtc_balance": 123}))

    snapshot = module.query_node({
        "name": "Legacy", "url": "https://node.example", "id": "node-legacy",
    })
    assert snapshot["spot_balance"] == 123
