# SPDX-License-Identifier: MIT
"""Unit and end-to-end lifecycle tests for tools/catalog_provider/ against a fake catalog transport."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.catalog_provider.daemon import (
    AgentKey,
    CatalogClient,
    CatalogProviderDaemon,
    CodeReviewWorker,
    DocsLintWorker,
    ProviderConfig,
)


class FakeCatalogTransport:
    """In-memory fake /catalog transport simulating two distinct buyer agents and ledger confirmation."""

    def __init__(self) -> None:
        self.orders: Dict[str, Dict[str, Any]] = {}
        self.deliver_calls: list[Tuple[str, str]] = []
        self.used_hashes: set[str] = set()

    def add_requested_order(
        self,
        order_id: str,
        listing_id: str,
        provider_id: str,
        buyer_id: str,
        note: str,
        price_rtc: float = 2.0,
    ) -> None:
        self.orders[order_id] = {
            "id": order_id,
            "listing_id": listing_id,
            "provider": provider_id,
            "buyer": buyer_id,
            "note": note,
            "price_rtc": price_rtc,
            "status": "requested",
            "payment": {"state": "unpaid"},
        }

    def buyer_accept_and_confirm_payment(self, order_id: str, tx_hash: str) -> None:
        order = self.orders[order_id]
        order["status"] = "accepted"
        order["payment"] = {
            "state": "confirmed",
            "tx_hash": tx_hash,
            "memo": f"svc:{order_id}",
        }

    def __call__(
        self, method: str, path: str, body: bytes, headers: Dict[str, str]
    ) -> Tuple[int, Any]:
        # Verify signed headers are present on authenticated endpoints
        assert "X-Agent-Id" in headers
        assert "X-Agent-Signature" in headers

        if method == "GET" and path.startswith("/catalog/orders?"):
            req_orders = [o for o in self.orders.values() if o["status"] == "requested"]
            return 200, {"orders": req_orders}

        if method == "POST" and path.endswith("/deliver"):
            order_id = path.split("/")[3]
            payload = json.loads(body.decode("utf-8"))
            d_hash = payload["deliverable_hash"]
            if d_hash in self.used_hashes:
                return 409, {"error": "duplicate deliverable_hash"}
            self.used_hashes.add(d_hash)
            self.deliver_calls.append((order_id, d_hash))
            self.orders[order_id]["status"] = "delivered"
            self.orders[order_id]["deliverable_hash"] = d_hash
            return 200, self.orders[order_id]

        if method == "GET" and path.startswith("/catalog/orders/"):
            order_id = path.split("/")[3]
            return 200, self.orders[order_id]

        return 404, {"error": f"unhandled {method} {path}"}


def _make_agent(seed_byte: int) -> AgentKey:
    return AgentKey(Ed25519PrivateKey.from_private_bytes(bytes([seed_byte]) * 32))


def test_end_to_end_two_distinct_buyers_and_idempotent_restart(tmp_path: Path) -> None:
    provider = _make_agent(10)
    buyer_one = _make_agent(21)
    buyer_two = _make_agent(22)
    transport = FakeCatalogTransport()

    transport.add_requested_order(
        "ord_buyer1_0001",
        "lst_review_01",
        provider.agent_id,
        buyer_one.agent_id,
        "repo: Scottcjn/Rustchain",
    )
    transport.add_requested_order(
        "ord_buyer2_0002",
        "lst_review_01",
        provider.agent_id,
        buyer_two.agent_id,
        "repo: Scottcjn/rustchain-bounties",
    )

    config = ProviderConfig(
        state_dir=tmp_path / "state",
        listing_id="lst_review_01",
        category="review",
        max_concurrent_orders=5,
    )
    client = CatalogClient(transport, provider)
    daemon = CatalogProviderDaemon(client, CodeReviewWorker(), config)

    # Tick 1: both orders delivered
    res1 = daemon.tick()
    assert res1["delivered"] == 2
    assert len(transport.deliver_calls) == 2

    # Simulate process restart on the same state_dir: must NOT re-deliver
    daemon_restarted = CatalogProviderDaemon(client, CodeReviewWorker(), config)
    res_restart = daemon_restarted.tick()
    assert res_restart["delivered"] == 0
    assert len(transport.deliver_calls) == 2

    # Buyers accept and pay on ledger with svc:<order_id> memos
    transport.buyer_accept_and_confirm_payment("ord_buyer1_0001", "tx_confirmed_001")
    transport.buyer_accept_and_confirm_payment("ord_buyer2_0002", "tx_confirmed_002")

    res_paid = daemon_restarted.tick()
    assert res_paid["confirmed"] == 2

    status = json.loads(config.status_path.read_text(encoding="utf-8"))
    assert status["orders_delivered"] == 2
    assert status["orders_accepted"] == 2
    assert status["orders_paid"] == 2
    assert status["distinct_buyers"] == 2
    # Privacy check: no RTC volume totals or private key material in status.json
    raw_status = config.status_path.read_text(encoding="utf-8")
    assert "price_rtc" not in raw_status
    assert "total_rtc" not in raw_status
    assert (bytes([10]) * 32).hex() not in raw_status


def test_self_order_rejected_and_kill_switch_stops_daemon(tmp_path: Path) -> None:
    provider = _make_agent(15)
    transport = FakeCatalogTransport()
    # Self-order from provider to itself must be skipped
    transport.add_requested_order(
        "ord_self_0001",
        "lst_docs_01",
        provider.agent_id,
        provider.agent_id,
        "docs/WALLET_SETUP.md",
    )

    config = ProviderConfig(state_dir=tmp_path / "state_ks", category="docs")
    daemon = CatalogProviderDaemon(CatalogClient(transport, provider), DocsLintWorker(), config)
    res = daemon.tick()
    assert res["delivered"] == 0
    assert res["skipped"] == 1

    # Tripping kill switch halts all work
    (config.state_dir / "STOP").write_text("halt", encoding="utf-8")
    assert daemon.kill_switch_tripped() is True
    assert daemon.tick() == {"delivered": 0, "accepted": 0, "confirmed": 0, "skipped": 0}
