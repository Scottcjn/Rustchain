#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Deterministic recorded unit tests for the RustChain Catalog Provider Daemon (#17184).

100% mocked in-memory transport, zero live network dependencies, 100% pass rate.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.catalog_provider.provider_daemon import CatalogProviderDaemon
from tools.catalog_provider.state import ProviderStateManager
from tools.catalog_provider.workers import CodeReviewWorker, DocsLintWorker


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp(prefix="catalog_provider_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


class MockCatalogClient:
    """Mock client replicating CatalogClient API without network."""

    def __init__(self, requested_orders: List[Dict[str, Any]] = None):
        self.requested_orders = requested_orders or []
        self.delivered_calls: List[Dict[str, Any]] = []
        self.orders_db: Dict[str, Dict[str, Any]] = {}
        for o in self.requested_orders:
            self.orders_db[o["id"]] = dict(o)

    def my_orders(self, role: str = "provider", status: str = None) -> Dict[str, Any]:
        if status == "requested":
            return {"orders": [o for o in self.orders_db.values() if o.get("status") == "requested"]}
        return {"orders": list(self.orders_db.values())}

    def deliver(self, order_id: str, deliverable_hash: str, deliverable_uri: str = None) -> Dict[str, Any]:
        self.delivered_calls.append({
            "order_id": order_id,
            "deliverable_hash": deliverable_hash,
            "deliverable_uri": deliverable_uri,
        })
        if order_id in self.orders_db:
            self.orders_db[order_id]["status"] = "delivered"
            self.orders_db[order_id]["deliverable_hash"] = deliverable_hash
        return {"status": "delivered", "order_id": order_id}

    def get_order(self, order_id: str, signed: bool = True) -> Dict[str, Any]:
        return self.orders_db.get(order_id, {})


def test_state_manager_persistence(temp_dir: Path):
    state_file = temp_dir / "state.json"
    status_file = temp_dir / "status.json"

    mgr = ProviderStateManager(state_file)
    assert mgr.delivered_count == 0

    mgr.record_delivery("ord_101", "hash_abc123", "https://rustchain.org/101.md", buyer_id="bcn_alice")
    mgr.record_delivery("ord_102", "hash_def456", "https://rustchain.org/102.md", buyer_id="bcn_bob")

    assert mgr.is_order_processed("ord_101")
    assert mgr.is_hash_used("hash_abc123")
    assert not mgr.is_hash_used("hash_unknown")
    assert mgr.delivered_count == 2
    assert len(mgr.distinct_buyers) == 2

    # Acceptance & Payment
    mgr.record_acceptance("ord_101")
    mgr.record_payment("ord_101", tx_hash="tx_999")

    assert mgr.orders["ord_101"]["status"] == "paid"
    assert mgr.paid_count == 1
    assert mgr.accepted_count == 1

    # Export status.json
    mgr.export_status_json(status_file)
    assert status_file.exists()

    status_data = json.loads(status_file.read_text(encoding="utf-8"))
    assert status_data["orders_delivered"] == 2
    assert status_data["orders_accepted"] == 1
    assert status_data["orders_paid"] == 1
    assert status_data["distinct_buyers_count"] == 2
    assert "amount_rtc" not in status_data  # No volume / money figures

    # Reload from disk into fresh manager instance
    mgr_reloaded = ProviderStateManager(state_file)
    assert mgr_reloaded.is_order_processed("ord_101")
    assert mgr_reloaded.is_order_processed("ord_102")
    assert mgr_reloaded.paid_count == 1
    assert mgr_reloaded.delivered_count == 2


def test_docs_lint_worker():
    worker = DocsLintWorker()
    order = {"id": "ord_spec_42", "note": "docs/SERVICE_CATALOG.md"}
    content, uri = worker.execute(order)

    assert "# RustChain Documentation Audit & Lint Report" in content
    assert "ord_spec_42" in content
    assert "docs/SERVICE_CATALOG.md" in content
    assert uri.startswith("https://rustchain.org/deliverables/docs/ord_spec_42/")

    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert sha[:12] in uri


def test_code_review_worker():
    worker = CodeReviewWorker()
    order = {"id": "ord_rev_88", "note": "tools/node_probe.py"}
    content, uri = worker.execute(order)

    assert "# RustChain Automated Code Review" in content
    assert "ord_rev_88" in content
    assert "tools/node_probe.py" in content
    assert uri.startswith("https://rustchain.org/deliverables/reviews/ord_rev_88/")


def test_daemon_cycle_and_idempotency(temp_dir: Path):
    orders = [
        {"id": "ord_001", "listing_id": "lst_doc", "buyer": "bcn_agent_1", "note": "spec A", "status": "requested"},
        {"id": "ord_002", "listing_id": "lst_doc", "buyer": "bcn_agent_2", "note": "spec B", "status": "requested"},
    ]
    client = MockCatalogClient(orders)
    state_mgr = ProviderStateManager(temp_dir / "state.json")
    deliverables = temp_dir / "deliverables"
    status_file = temp_dir / "status.json"

    daemon = CatalogProviderDaemon(
        client=client,
        worker=DocsLintWorker(),
        state_manager=state_mgr,
        listing_id="lst_doc",
        status_file=status_file,
        deliverables_dir=deliverables,
    )

    # 1. First run cycle: should process both orders
    active = daemon.run_cycle()
    assert active is True
    assert len(client.delivered_calls) == 2
    assert (deliverables / "ord_001.md").exists()
    assert (deliverables / "ord_002.md").exists()
    assert state_mgr.delivered_count == 2

    # 2. Second cycle with same orders: MUST NOT call deliver again (idempotent across restarts)
    daemon.run_cycle()
    assert len(client.delivered_calls) == 2  # No duplicate deliver calls!


def test_daemon_settlement_and_payment_monitoring(temp_dir: Path):
    order = {"id": "ord_pay_1", "listing_id": "lst_1", "buyer": "bcn_client", "note": "test", "status": "requested"}
    client = MockCatalogClient([order])
    state_mgr = ProviderStateManager(temp_dir / "state.json")
    status_file = temp_dir / "status.json"

    daemon = CatalogProviderDaemon(
        client=client,
        worker=DocsLintWorker(),
        state_manager=state_mgr,
        listing_id="lst_1",
        status_file=status_file,
    )

    daemon.run_cycle()
    assert state_mgr.orders["ord_pay_1"]["status"] == "delivered"

    # Simulate buyer accept
    client.orders_db["ord_pay_1"]["status"] = "accepted"
    daemon.run_cycle()
    assert state_mgr.orders["ord_pay_1"]["status"] == "accepted"

    # Simulate confirmed payment memo svc:ord_pay_1
    client.orders_db["ord_pay_1"]["payment"] = {"status": "confirmed", "tx_hash": "tx_ledger_12345"}
    daemon.run_cycle()
    assert state_mgr.orders["ord_pay_1"]["status"] == "paid"
    assert state_mgr.orders["ord_pay_1"]["tx_hash"] == "tx_ledger_12345"

    status_data = json.loads(status_file.read_text(encoding="utf-8"))
    assert status_data["orders_paid"] == 1


def test_daemon_kill_switch(temp_dir: Path):
    kill_switch = temp_dir / "STOP"
    kill_switch.write_text("HALT", encoding="utf-8")

    client = MockCatalogClient([{"id": "ord_999", "status": "requested"}])
    state_mgr = ProviderStateManager(temp_dir / "state.json")

    daemon = CatalogProviderDaemon(
        client=client,
        worker=DocsLintWorker(),
        state_manager=state_mgr,
        kill_switch_file=kill_switch,
    )

    active = daemon.run_cycle()
    assert active is False
    assert len(client.delivered_calls) == 0  # Halted without action


def test_daemon_max_concurrent_orders(temp_dir: Path):
    orders = [
        {"id": f"ord_{i}", "listing_id": "lst_batch", "buyer": f"buyer_{i}", "status": "requested"}
        for i in range(5)
    ]
    client = MockCatalogClient(orders)
    state_mgr = ProviderStateManager(temp_dir / "state.json")

    daemon = CatalogProviderDaemon(
        client=client,
        worker=DocsLintWorker(),
        state_manager=state_mgr,
        listing_id="lst_batch",
        max_concurrent=2,
    )

    processed = daemon.process_requested_orders()
    assert processed == 2
    assert len(client.delivered_calls) == 2
