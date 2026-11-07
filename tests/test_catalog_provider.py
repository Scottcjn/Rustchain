# SPDX-License-Identifier: MIT
"""Tests for tools/catalog_provider/ against the real catalog blueprint and node ledger.

Mirrors the fake transport harness in ``tests/test_catalog_cli.py``:
- Catalog requests go to ``node/service_catalog.py``'s real Flask blueprint with
  real Ed25519 request verification and Beacon Atlas ``relay_agents`` lookup.
- Signed transfers go to ``POST /wallet/transfer/signed`` on ``integrated_node``
  sharing the same SQLite ledger database.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from flask import Flask

import service_catalog
from tools.catalog_provider import (
    CodeReviewWorker,
    DocsLintWorker,
    KillSwitchActive,
    ProviderConfig,
    ProviderDaemon,
    WorkResult,
    Worker,
    load_catalog_cli,
)
from tools.catalog_provider.daemon import main as provider_main

ROOT = Path(__file__).resolve().parents[1]
integrated_node = __import__("sys").modules["integrated_node"]
cli = load_catalog_cli()


def _init_node_db(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL);
            CREATE TABLE pending_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL,
                epoch INTEGER NOT NULL, from_miner TEXT NOT NULL, to_miner TEXT NOT NULL,
                amount_i64 INTEGER NOT NULL, reason TEXT, status TEXT DEFAULT 'pending',
                created_at INTEGER NOT NULL, confirms_at INTEGER NOT NULL, tx_hash TEXT,
                voided_by TEXT, voided_reason TEXT, confirmed_at INTEGER
            );
            CREATE TABLE transfer_nonces (
                from_address TEXT NOT NULL, nonce TEXT NOT NULL, used_at INTEGER NOT NULL,
                PRIMARY KEY (from_address, nonce)
            );
            CREATE UNIQUE INDEX idx_pending_ledger_tx_hash ON pending_ledger(tx_hash);
            """
        )


class CatalogNet:
    """In-process node + catalog blueprint sharing one SQLite database."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        self.db = str(tmp_path / f"{uuid.uuid4().hex}.sqlite3")
        self.atlas = str(tmp_path / "beacon_atlas.db")
        self.tmp = tmp_path
        _init_node_db(self.db)
        with sqlite3.connect(self.atlas) as conn:
            conn.execute(
                "CREATE TABLE relay_agents (agent_id TEXT PRIMARY KEY, "
                "pubkey_hex TEXT, name TEXT, status TEXT)"
            )
        monkeypatch.setattr(integrated_node, "DB_PATH", self.db)
        monkeypatch.setattr(integrated_node, "BEACON_ATLAS_DB", self.atlas)
        monkeypatch.setattr(integrated_node, "current_slot", lambda: 12345)
        monkeypatch.setenv("RC_CHAIN_ID", integrated_node.CHAIN_ID)
        monkeypatch.setenv("CATALOG_PROVIDER_OFFLINE", "1")
        integrated_node.app.config["TESTING"] = True

        catalog_app = Flask("catalog_provider_test")
        assert service_catalog.register_service_catalog(
            catalog_app, self.db, atlas_db_path=self.atlas
        )
        self.catalog = catalog_app.test_client()
        self.node = integrated_node.app.test_client()
        self.requests = []

        # Create a sample repo directory for workers to inspect locally
        self.sample_repo = tmp_path / "sample_repo"
        self.sample_repo.mkdir(parents=True, exist_ok=True)
        (self.sample_repo / "app.py").write_text(
            "def add(a, items=[]):\n"
            "    try:\n"
            "        return a + len(items)  # TODO: validate types\n"
            "    except:\n"
            "        pass\n",
            encoding="utf-8",
        )
        (self.sample_repo / "README.md").write_text(
            "# Sample Repo\n\nSee [missing doc](docs/MISSING.md) and [app](app.py).\n",
            encoding="utf-8",
        )

    def transport(self, method: str, path: str, body: bytes, headers: Dict[str, str]):
        self.requests.append((method, path))
        client = self.catalog if path.startswith("/catalog") else self.node
        resp = client.open(path, method=method, data=body or None, headers=headers)
        return resp.status_code, resp.get_json(silent=True)

    def agent(self, seed: int, register: bool = True, status: str = "active"):
        key = cli.AgentKey(Ed25519PrivateKey.from_private_bytes(bytes([seed]) * 32))
        if register:
            with sqlite3.connect(self.atlas) as conn:
                conn.execute(
                    "INSERT INTO relay_agents VALUES (?, ?, ?, ?)",
                    (key.agent_id, key.public_key, f"agent{seed}", status),
                )
        return key

    def key_file(self, agent: Any, seed: int) -> str:
        path = self.tmp / f"agent{seed}.key"
        path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "agent_id": agent.agent_id,
                    "public_key_hex": agent.public_key,
                    "encrypted": False,
                    "private_key_hex": (bytes([seed]) * 32).hex(),
                }
            ),
            encoding="utf-8",
        )
        return str(path)

    def client(self, agent: Any):
        return cli.CatalogClient(self.transport, agent)

    def fund(self, address: str, rtc: float = 100.0) -> None:
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO balances VALUES (?, ?)",
                (address, int(rtc * 1_000_000)),
            )

    def confirm_payment(self, order_id: str) -> None:
        """Simulate the 24h pending window settling to confirmed on the ledger."""
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                "UPDATE pending_ledger SET status = 'confirmed', confirmed_at = 1794040600 "
                "WHERE reason = ?",
                (f"signed_transfer:svc:{order_id}",),
            )


@pytest.fixture
def net(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CatalogNet:
    return CatalogNet(tmp_path, monkeypatch)


def test_unattended_end_to_end_two_buyers_order_deliver_accept_pay_confirm(
    net: CatalogNet, tmp_path: Path
):
    """Full lifecycle: two distinct buyer agents order -> daemon fulfills & delivers
    -> buyers accept & pay -> ledger confirms -> daemon watches payment and writes
    status.json with counts only (no RTC volume fields)."""
    provider = net.agent(1)
    buyer_a = net.agent(2)
    buyer_b = net.agent(3)
    net.fund(buyer_a.agent_id, 50)
    net.fund(buyer_b.agent_id, 50)

    provider_client = net.client(provider)
    listing = provider_client.offer(
        "Automated repo code review",
        "review",
        "1.5",
        description="Static AST review with file and line references.",
        unit="per repo",
        turnaround_hours=24,
    )

    order_a = net.client(buyer_a).order(
        listing["id"], note=f"repo: {net.sample_repo}"
    )
    order_b = net.client(buyer_b).order(
        listing["id"], note=f"repo: {net.sample_repo}"
    )

    state_dir = tmp_path / "provider_state"
    config = ProviderConfig(
        state_dir=state_dir,
        category="review",
        listing_id=listing["id"],
        deliverable_base_uri="https://example.org/reviews",
    )
    worker = CodeReviewWorker(repo_root=net.sample_repo)
    daemon = ProviderDaemon(client=provider_client, worker=worker, config=config)

    # Tick 1: daemon polls requested orders, runs worker, delivers both
    tick1 = daemon.run_once()
    assert set(tick1["delivered_order_ids"]) == {order_a["id"], order_b["id"]}
    assert tick1["confirmed_order_ids"] == []
    assert tick1["status"]["orders_delivered"] == 2
    assert tick1["status"]["orders_accepted"] == 0
    assert tick1["status"]["orders_paid"] == 0
    assert tick1["status"]["distinct_buyers_delivered"] == 2

    # Verify deliverables exist on disk and match server-side deliverable_hash
    for oid in (order_a["id"], order_b["id"]):
        srv_order = provider_client.get_order(oid, signed=True)
        assert srv_order["status"] == "delivered"
        assert srv_order["deliverable_uri"].startswith(
            f"https://example.org/reviews/{oid}/"
        )
        local_rec = daemon.state["orders"][oid]
        assert Path(local_rec["deliverable_path"]).exists()
        text = Path(local_rec["deliverable_path"]).read_text(encoding="utf-8")
        assert "app.py:1" in text  # mutable default finding
        assert "app.py:4" in text  # bare except finding
        assert srv_order["deliverable_hash"] == local_rec["deliverable_hash"]

    # Both buyers accept and pay from their own wallets with memo svc:<order_id>
    for buyer_key, order_obj in ((buyer_a, order_a), (buyer_b, order_b)):
        b_client = net.client(buyer_key)
        accepted = b_client.accept(order_obj["id"])
        assert accepted["status"] == "accepted"
        built = b_client.build_payment(order_obj["id"])
        sent = b_client.send_payment(built["body"])
        assert sent["ok"] is True

    # Tick 2 (while payments are still 'pending'): accepted is tracked, paid is still 0
    tick2 = daemon.run_once()
    assert tick2["delivered_order_ids"] == []
    assert tick2["confirmed_order_ids"] == []
    assert tick2["status"]["orders_accepted"] == 2
    assert tick2["status"]["distinct_buyers_accepted"] == 2
    assert tick2["status"]["orders_paid"] == 0

    # Confirm both transfers on the node ledger
    net.confirm_payment(order_a["id"])
    net.confirm_payment(order_b["id"])

    # Tick 3: payment watcher detects confirmed payments and updates status.json
    tick3 = daemon.run_once()
    assert set(tick3["confirmed_order_ids"]) == {order_a["id"], order_b["id"]}

    status_json = json.loads(config.status_file.read_text(encoding="utf-8"))
    assert status_json["orders_delivered"] == 2
    assert status_json["orders_accepted"] == 2
    assert status_json["orders_paid"] == 2
    assert status_json["distinct_buyers_delivered"] == 2
    assert status_json["distinct_buyers_accepted"] == 2
    assert status_json["distinct_buyers_paid"] == 2

    # Enforce the catalog's "work, not volume" rule: no RTC totals in status.json
    for key in status_json:
        assert "rtc" not in key.lower()
        assert "volume" not in key.lower()
        assert "earned" not in key.lower()


def test_idempotent_across_restarts_and_mid_flight_recovery(
    net: CatalogNet, tmp_path: Path
):
    """Restarting the daemon on the same state_dir never redelivers a live order,
    even if the previous process crashed after server delivery before state flush."""
    provider = net.agent(1)
    buyer = net.agent(2)
    p_client = net.client(provider)
    listing = p_client.offer("Review repo", "review", "1.0")
    order = net.client(buyer).order(listing["id"], note=f"repo: {net.sample_repo}")

    state_dir = tmp_path / "restart_state"
    config = ProviderConfig(state_dir=state_dir, category="review", listing_id=listing["id"])
    worker = CodeReviewWorker(repo_root=net.sample_repo)

    daemon1 = ProviderDaemon(client=p_client, worker=worker, config=config)
    res1 = daemon1.run_once()
    assert res1["delivered_order_ids"] == [order["id"]]

    deliver_calls_before = [
        req for req in net.requests if req == ("POST", f"/catalog/orders/{order['id']}/deliver")
    ]
    assert len(deliver_calls_before) == 1

    # Restart a brand-new ProviderDaemon instance pointed at the same state_dir
    daemon2 = ProviderDaemon(client=p_client, worker=worker, config=config)
    res2 = daemon2.run_once()
    assert res2["delivered_order_ids"] == []
    # Calling fulfill_order directly on the already-delivered order is a no-op
    rec = daemon2.fulfill_order(order)
    assert rec["status"] == "delivered"

    deliver_calls_after = [
        req for req in net.requests if req == ("POST", f"/catalog/orders/{order['id']}/deliver")
    ]
    assert len(deliver_calls_after) == 1

    # Simulate crash where state.json was wiped/stale but server already has 'delivered'
    config.state_file.unlink()
    daemon3 = ProviderDaemon(client=p_client, worker=worker, config=config)
    rec3 = daemon3.fulfill_order(order)
    assert rec3["status"] == "delivered"
    assert len(
        [req for req in net.requests if req == ("POST", f"/catalog/orders/{order['id']}/deliver")]
    ) == 1


def test_duplicate_deliverable_hash_collision_recovery(
    net: CatalogNet, tmp_path: Path
):
    """If a custom worker produces the exact same bytes on attempt 1 for a second
    live order, the daemon catches the collision and retries with attempt=2."""

    class CollidingWorker(Worker):
        category = "review"

        def fulfill(
            self,
            order: Dict[str, Any],
            out_dir: Path,
            *,
            attempt: int = 1,
            base_uri: Optional[str] = None,
        ) -> WorkResult:
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"out_{attempt}.md"
            if attempt == 1:
                # Identical bytes regardless of order on attempt 1
                path.write_text("fixed-identical-body\n", encoding="utf-8")
            else:
                path.write_text(f"unique-body-{order['id']}-v{attempt}\n", encoding="utf-8")
            return WorkResult(artifact_path=path)

    provider = net.agent(1)
    buyer = net.agent(2)
    p_client = net.client(provider)
    listing = p_client.offer("Review repo", "review", "1.0")
    o1 = net.client(buyer).order(listing["id"], note="first")
    o2 = net.client(buyer).order(listing["id"], note="second")

    # Deliver o1 directly outside local state so the server (not just local used_hashes)
    # enforces the unique index idx_catalog_orders_live_hash on o2's attempt 1.
    fixed_hash = hashlib.sha256(b"fixed-identical-body\n").hexdigest()
    p_client.deliver(o1["id"], fixed_hash)

    config = ProviderConfig(
        state_dir=tmp_path / "collision_state",
        category="review",
        listing_id=listing["id"],
    )
    daemon = ProviderDaemon(client=p_client, worker=CollidingWorker(), config=config)
    res = daemon.run_once()
    assert res["delivered_order_ids"] == [o2["id"]]
    srv_o2 = p_client.get_order(o2["id"], signed=True)
    assert srv_o2["status"] == "delivered"
    assert srv_o2["deliverable_hash"] != fixed_hash


def test_safety_controls_kill_switch_concurrency_rate_limit_and_secret_hygiene(
    net: CatalogNet, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """Tests kill-switch file, max_concurrent_orders, rate limit, and ensures
    the private key is never printed or logged."""
    provider = net.agent(1)
    buyer = net.agent(2)
    priv_hex = (bytes([1]) * 32).hex()
    key_path = net.key_file(provider, 1)

    p_client = net.client(provider)
    listing = p_client.offer("Docs lint service", "docs", "0.5")
    for idx in range(3):
        net.client(buyer).order(listing["id"], note=f"path: {net.sample_repo} #{idx}")

    state_dir = tmp_path / "safety_state"
    kill_file = state_dir / "KILL"
    now_val = [1794040000.0]

    config = ProviderConfig(
        state_dir=state_dir,
        category="docs",
        listing_id=listing["id"],
        max_concurrent_orders=1,
        max_orders_per_minute=2,
        kill_switch_path=kill_file,
        clock=lambda: now_val[0],
    )
    worker = DocsLintWorker(docs_root=net.sample_repo)
    daemon = ProviderDaemon(client=p_client, worker=worker, config=config)

    # 1. max_concurrent_orders=1 -> only 1 order delivered on tick 1
    t1 = daemon.run_once()
    assert len(t1["delivered_order_ids"]) == 1

    # 2. Tick 2 delivers the 2nd order (hitting max_orders_per_minute=2)
    t2 = daemon.run_once()
    assert len(t2["delivered_order_ids"]) == 1

    # 3. Tick 3 within the same minute is rate-limited (0 delivered)
    t3 = daemon.run_once()
    assert t3["delivered_order_ids"] == []

    # 4. Advance clock past 60s window -> 3rd order is delivered
    now_val[0] += 61.0
    t4 = daemon.run_once()
    assert len(t4["delivered_order_ids"]) == 1

    # 5. Activate kill switch -> raises KillSwitchActive and CLI returns exit code 2
    kill_file.write_text("stop\n", encoding="utf-8")
    with pytest.raises(KillSwitchActive):
        daemon.run_once()

    rc = provider_main(
        [
            "--identity",
            key_path,
            "--state-dir",
            str(state_dir),
            "--kill-switch",
            str(kill_file),
            "--category",
            "docs",
            "--worker",
            "docs",
            "--once",
        ],
        transport=net.transport,
    )
    assert rc == 2

    # 6. Remove kill switch and run CLI --once; verify private key is nowhere in output or files
    kill_file.unlink()
    log_records = []

    class _ListHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            log_records.append(record.getMessage())

    handler = _ListHandler()
    daemon.logger.addHandler(handler)
    daemon.logger.info(f"accidental leak attempt {priv_hex} in log")
    assert all(priv_hex not in msg for msg in log_records)

    rc_ok = provider_main(
        [
            "--identity",
            key_path,
            "--state-dir",
            str(state_dir),
            "--category",
            "docs",
            "--worker",
            "docs",
            "--repo-root",
            str(net.sample_repo),
            "--once",
        ],
        transport=net.transport,
    )
    captured = capsys.readouterr()
    assert rc_ok == 0
    assert priv_hex not in captured.out
    assert priv_hex not in captured.err
    assert priv_hex not in repr(daemon)
    assert priv_hex not in config.state_file.read_text(encoding="utf-8")
    assert priv_hex not in config.status_file.read_text(encoding="utf-8")
