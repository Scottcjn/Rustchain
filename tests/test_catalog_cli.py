# SPDX-License-Identifier: MIT
"""tools/catalog_cli.py against the real node code.

Catalog calls go to node/service_catalog.py's real blueprint with the real
Beacon Atlas resolver (a temp ``relay_agents`` table) and real Ed25519
request verification. Payments go to the node's real
``POST /wallet/transfer/signed`` with its real verifier: no signature or
address monkeypatching. Both share one ledger database, so the catalog's
read-only payment reconciliation sees what the node wrote.
"""

import hashlib
import importlib.util
import json
import sqlite3
import uuid
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from flask import Flask

import service_catalog

ROOT = Path(__file__).resolve().parents[1]
integrated_node = __import__("sys").modules["integrated_node"]


def _load_cli():
    spec = importlib.util.spec_from_file_location("catalog_cli_under_test",
                                                  ROOT / "tools" / "catalog_cli.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cli = _load_cli()
OTHER_CHAIN = "rustchain-testnet-v2"


def _init_node_db(db_path):
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


class Net:
    """One node: the catalog blueprint and the main app, on one ledger DB."""

    def __init__(self, tmp_path, monkeypatch):
        self.db = str(tmp_path / f"{uuid.uuid4().hex}.sqlite3")
        self.atlas = str(tmp_path / "beacon_atlas.db")
        self.tmp = tmp_path
        _init_node_db(self.db)
        with sqlite3.connect(self.atlas) as conn:
            conn.execute("CREATE TABLE relay_agents (agent_id TEXT PRIMARY KEY, "
                         "pubkey_hex TEXT, name TEXT, status TEXT)")
        monkeypatch.setattr(integrated_node, "DB_PATH", self.db)
        monkeypatch.setattr(integrated_node, "BEACON_ATLAS_DB", self.atlas)
        monkeypatch.setattr(integrated_node, "current_slot", lambda: 12345)
        # The catalog reads the same env var the node reads for its CHAIN_ID.
        monkeypatch.setenv("RC_CHAIN_ID", integrated_node.CHAIN_ID)
        integrated_node.app.config["TESTING"] = True
        catalog_app = Flask("catalog_cli_test")
        assert service_catalog.register_service_catalog(catalog_app, self.db,
                                                        atlas_db_path=self.atlas)
        self.catalog = catalog_app.test_client()
        self.node = integrated_node.app.test_client()
        self.requests = []

    def transport(self, method, path, body, headers):
        self.requests.append((method, path))
        client = self.catalog if path.startswith("/catalog") else self.node
        resp = client.open(path, method=method, data=body or None, headers=headers)
        return resp.status_code, resp.get_json(silent=True)

    def agent(self, seed, register=True, status="active"):
        key = cli.AgentKey(Ed25519PrivateKey.from_private_bytes(bytes([seed]) * 32))
        if register:
            with sqlite3.connect(self.atlas) as conn:
                conn.execute("INSERT INTO relay_agents VALUES (?, ?, ?, ?)",
                             (key.agent_id, key.public_key, f"agent{seed}", status))
        return key

    def key_file(self, agent, seed):
        path = self.tmp / f"agent{seed}.key"
        path.write_text(json.dumps({"version": 1, "agent_id": agent.agent_id,
                                    "public_key_hex": agent.public_key, "encrypted": False,
                                    "private_key_hex": (bytes([seed]) * 32).hex()}))
        return str(path)

    def client(self, agent):
        return cli.CatalogClient(self.transport, agent)

    def fund(self, address, rtc=100):
        with sqlite3.connect(self.db) as conn:
            conn.execute("INSERT OR REPLACE INTO balances VALUES (?, ?)",
                         (address, int(rtc * 1_000_000)))

    def ledger(self):
        with sqlite3.connect(self.db) as conn:
            return conn.execute("SELECT from_miner, to_miner, amount_i64, reason, status "
                                "FROM pending_ledger ORDER BY id").fetchall()

    def run(self, agent_seed, argv, capsys):
        """Run the CLI's main() with an identity file; return (exit code, stdout)."""
        args = list(argv)
        if agent_seed is not None:
            args = ["--identity", str(self.tmp / f"agent{agent_seed}.key")] + args
        code = cli.main(args, transport=self.transport)
        return code, capsys.readouterr()


@pytest.fixture
def net(tmp_path, monkeypatch):
    return Net(tmp_path, monkeypatch)


OFFER = ["offer", "--title", "Review one public repo", "--category", "review",
         "--price-rtc", "2.5", "--unit", "per repo", "--turnaround-hours", "48",
         "--description", "Read-only code review delivered as markdown."]


def _accepted_order(net, provider, buyer, price="2.5"):
    """Provider lists, buyer orders, provider delivers, buyer accepts, all via the client."""
    listing = net.client(provider).offer("Review one public repo", "review", price)
    order = net.client(buyer).order(listing["id"], note="repo: example/example")
    net.client(provider).deliver(order["id"], hashlib.sha256(b"the review").hexdigest())
    accepted = net.client(buyer).accept(order["id"])
    assert accepted["status"] == "accepted"
    return accepted


# --------------------------------------------------------------------------
# list / offer / order
# --------------------------------------------------------------------------

def test_offer_then_list_via_cli(net, capsys):
    provider = net.agent(1)
    net.key_file(provider, 1)
    code, out = net.run(1, OFFER + [], capsys)
    assert code == 0, out.err
    listing = json.loads(out.out)
    assert listing["provider"] == provider.agent_id
    assert listing["price_rtc"] == 2.5 and listing["category"] == "review"

    code, out = net.run(None, ["list", "--category", "review"], capsys)
    assert code == 0
    assert listing["id"] in out.out and "2.5 RTC per repo" in out.out
    assert "holds no funds" in out.out

    code, out = net.run(None, ["--json", "list", "--category", "render"], capsys)
    assert json.loads(out.out)["listings"] == []


def test_offer_by_unregistered_or_barred_agent_is_refused(net, capsys):
    stranger = net.agent(2, register=False)
    net.key_file(stranger, 2)
    code, out = net.run(2, OFFER, capsys)
    assert code == 1 and "403" in out.err
    banned = net.agent(3, status="suspended")
    net.key_file(banned, 3)
    code, out = net.run(3, OFFER, capsys)
    assert code == 1 and "403" in out.err


def test_offer_refuses_bad_price_and_category_locally(net):
    client = net.client(net.agent(1))
    for price in ("0", "-1", "1.0000001", "abc", "nan"):
        with pytest.raises(cli.CatalogError):
            client.offer("Review one public repo", "review", price)
    with pytest.raises(cli.CatalogError):
        client.offer("Review one public repo", "not_a_category", "1")
    assert net.requests == []  # nothing reached the node


def test_node_rejections_surface_as_errors(net):
    client = net.client(net.agent(1))
    with pytest.raises(cli.CatalogError) as exc:
        client.offer("Render for $5 each", "render", "1")
    assert exc.value.status == 400
    assert exc.value.payload["error"] == "fiat_reference_not_allowed"


def test_order_deliver_accept_and_signed_inbox(net, tmp_path):
    provider, buyer = net.agent(1), net.agent(2)
    order = _accepted_order(net, provider, buyer)
    assert order["buyer"] == buyer.agent_id and order["provider"] == provider.agent_id
    # Signed GET with a query string: the signature covers the query.
    inbox = net.client(provider).my_orders(role="provider", status="accepted")
    assert [o["id"] for o in inbox["orders"]] == [order["id"]]
    assert net.client(buyer).my_orders(role="buyer")["orders"][0]["id"] == order["id"]
    # Unsigned public view hides the buyer and note.
    public = net.client(None).get_order(order["id"], signed=False)
    assert "buyer" not in public and "note" not in public


def test_deliver_file_hash_via_cli(net, capsys, tmp_path):
    provider, buyer = net.agent(1), net.agent(2)
    net.key_file(provider, 1)
    listing = net.client(provider).offer("Review one public repo", "review", "1")
    order = net.client(buyer).order(listing["id"])
    artifact = tmp_path / "review.md"
    artifact.write_bytes(b"# review\nall good\n")
    code, out = net.run(1, ["deliver", order["id"], "--file", str(artifact),
                            "--uri", "https://example.org/review.md"], capsys)
    assert code == 0, out.err
    assert json.loads(out.out)["deliverable_hash"] == hashlib.sha256(
        artifact.read_bytes()).hexdigest()


def test_ids_with_path_separators_are_refused(net):
    client = net.client(net.agent(1))
    for bad in ("../listings", "ord_1/accept", "ord_1?x=1", ""):
        with pytest.raises(cli.CatalogError):
            client.accept(bad)
    assert net.requests == []


# --------------------------------------------------------------------------
# pay
# --------------------------------------------------------------------------

def test_pay_builds_chain_bound_transfer_the_node_verifies(net):
    provider, buyer = net.agent(1), net.agent(2)
    order = _accepted_order(net, provider, buyer)
    net.fund(buyer.agent_id)
    built = net.client(buyer).build_payment(order["id"])
    body = built["body"]
    assert body["from_address"] == buyer.agent_id
    assert body["to_address"] == provider.agent_id
    assert body["amount_rtc"] == 2.5
    assert body["memo"] == f"svc:{order['id']}"
    assert body["chain_id"] == integrated_node.CHAIN_ID
    # The signed bytes are exactly the node's own canonical message.
    _, legacy = integrated_node._wallet_transfer_signed_messages(
        body["from_address"], body["to_address"], 2.5, 0.0, body["memo"],
        str(body["nonce"]), body["chain_id"])
    assert built["signed_message"].encode() == legacy
    assert net.ledger() == []  # building is not sending

    # Chain binding: stripped or swapped chain_id must fail on the real verifier.
    stripped = {k: v for k, v in body.items() if k != "chain_id"}
    r = net.node.post("/wallet/transfer/signed", json=stripped)
    assert r.status_code in (400, 401), r.get_json()
    r = net.node.post("/wallet/transfer/signed", json=dict(body, chain_id=OTHER_CHAIN))
    assert r.status_code == 400 and "chain_id" in json.dumps(r.get_json())
    # Tampering with the amount or the memo breaks the signature.
    for tampered in (dict(body, amount_rtc=0.5), dict(body, memo="svc:ord_0000000000000000")):
        assert net.node.post("/wallet/transfer/signed", json=tampered).status_code == 401
    assert net.ledger() == []

    r = net.node.post("/wallet/transfer/signed", json=body)
    assert r.status_code == 200 and r.get_json()["ok"] is True, r.get_json()
    assert net.ledger() == [(buyer.agent_id, provider.agent_id, 2_500_000,
                             f"signed_transfer:svc:{order['id']}", "pending")]
    # The catalog's read-only reconciliation now sees the payment.
    assert net.client(None).get_order(order["id"], signed=False)["payment"]["state"] == "pending"


def test_pay_is_dry_run_without_send(net, capsys):
    provider, buyer = net.agent(1), net.agent(2)
    net.key_file(buyer, 2)
    order = _accepted_order(net, provider, buyer)
    net.fund(buyer.agent_id)
    code, out = net.run(2, ["pay", order["id"]], capsys)
    assert code == 0, out.err
    shown = json.loads(out.out)
    assert shown["dry_run"] is True
    assert shown["would_send"]["memo"] == f"svc:{order['id']}"
    assert "Re-run with --send" in out.err
    # The dry run never prints a usable signature.
    assert shown["request_body"]["signature"] == "<withheld in dry run>"
    assert net.ledger() == []
    assert ("POST", "/wallet/transfer/signed") not in net.requests


def test_pay_send_moves_rtc_once_and_refuses_double_pay(net, capsys):
    provider, buyer = net.agent(1), net.agent(2)
    net.key_file(buyer, 2)
    order = _accepted_order(net, provider, buyer)
    net.fund(buyer.agent_id)
    code, out = net.run(2, ["pay", order["id"], "--send"], capsys)
    assert code == 0, out.err
    result = json.loads(out.out)
    assert result["node_response"]["ok"] is True
    assert result["order_payment"]["state"] == "pending"
    assert len(net.ledger()) == 1

    code, out = net.run(2, ["pay", order["id"], "--send"], capsys)
    assert code == 1 and "already has a pending payment" in out.err
    assert len(net.ledger()) == 1


def test_pay_from_rtc_address_of_same_key(net):
    provider, buyer = net.agent(1), net.agent(2)
    order = _accepted_order(net, provider, buyer)
    net.fund(buyer.rtc_address)
    body = net.client(buyer).build_payment(order["id"], pay_from="rtc")["body"]
    assert body["from_address"] == buyer.rtc_address
    r = net.node.post("/wallet/transfer/signed", json=body)
    assert r.status_code == 200, r.get_json()
    assert net.client(None).get_order(order["id"], signed=False)["payment"]["state"] == "pending"


def test_pay_smallest_price_covers_order(net):
    provider, buyer = net.agent(1), net.agent(2)
    order = _accepted_order(net, provider, buyer, price="0.000003")
    net.fund(buyer.agent_id)
    body = net.client(buyer).build_payment(order["id"])["body"]
    assert net.node.post("/wallet/transfer/signed", json=body).status_code == 200
    assert net.ledger()[0][2] == 3
    assert net.client(None).get_order(order["id"], signed=False)["payment"]["state"] == "pending"


def test_pay_refused_before_accept_and_for_non_buyer(net):
    provider, buyer, other = net.agent(1), net.agent(2), net.agent(3)
    listing = net.client(provider).offer("Review one public repo", "review", "1")
    order = net.client(buyer).order(listing["id"])
    with pytest.raises(cli.CatalogError, match="pay after delivery"):
        net.client(buyer).build_payment(order["id"])
    with pytest.raises(cli.CatalogError):
        net.client(other).build_payment(order["id"])  # 403 from the catalog
    with pytest.raises(cli.CatalogError, match="not the buyer"):
        net.client(provider).build_payment(order["id"])
    assert net.ledger() == []


def test_pay_refuses_when_catalog_and_node_chain_ids_differ(net, monkeypatch):
    provider, buyer = net.agent(1), net.agent(2)
    order = _accepted_order(net, provider, buyer)
    monkeypatch.setenv("RC_CHAIN_ID", OTHER_CHAIN)  # catalog instructions now disagree
    with pytest.raises(cli.CatalogError, match="wrong network"):
        net.client(buyer).build_payment(order["id"])


# --------------------------------------------------------------------------
# identity files
# --------------------------------------------------------------------------

def test_malformed_identity_is_a_clean_error(net, capsys, tmp_path):
    bad = tmp_path / "bad.key"
    bad.write_text("not-hex")
    code, out = net.run(None, ["--identity", str(bad), "whoami"], capsys)
    assert code == 1 and out.err.startswith("error:")


def test_identity_formats(tmp_path):
    seed = bytes([7]) * 32
    expected = cli.AgentKey(Ed25519PrivateKey.from_private_bytes(seed))
    raw = tmp_path / "raw.key"
    raw.write_text(seed.hex())
    assert cli.AgentKey.load(str(raw)).agent_id == expected.agent_id

    plain = tmp_path / "plain.key"
    plain.write_text(json.dumps({"agent_id": expected.agent_id, "encrypted": False,
                                 "private_key_hex": seed.hex()}))
    assert cli.AgentKey.load(str(plain)).agent_id == expected.agent_id

    wrong = tmp_path / "wrong.key"
    wrong.write_text(json.dumps({"agent_id": "bcn_000000000000", "encrypted": False,
                                 "private_key_hex": seed.hex()}))
    with pytest.raises(cli.CatalogError, match="does not match"):
        cli.AgentKey.load(str(wrong))
    with pytest.raises(cli.CatalogError, match="no Beacon identity"):
        cli.AgentKey.load(str(tmp_path / "missing.key"))


def test_encrypted_beacon_identity(tmp_path):
    """Same keystore layout beacon_skill.identity.AgentIdentity.save(password) writes."""
    import os

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    seed, salt, nonce = bytes([9]) * 32, os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                     iterations=600_000).derive(b"pw")
    path = tmp_path / "enc.key"
    expected = cli.AgentKey(Ed25519PrivateKey.from_private_bytes(seed))
    path.write_text(json.dumps({
        "version": 1, "agent_id": expected.agent_id, "public_key_hex": expected.public_key,
        "encrypted": True, "salt": salt.hex(), "nonce": nonce.hex(),
        "ciphertext": AESGCM(key).encrypt(nonce, seed, None).hex()}))
    assert cli.AgentKey.load(str(path), password="pw").agent_id == expected.agent_id
    with pytest.raises(cli.CatalogError, match="wrong password"):
        cli.AgentKey.load(str(path), password="nope")


@pytest.mark.parametrize("drop", ["payment", "payment_instructions"])
def test_pay_fails_closed_without_payment_state_or_instructions(net, drop):
    """If the node's order view lacks payment state or instructions, do not sign."""
    provider, buyer = net.agent(1), net.agent(2)
    order = _accepted_order(net, provider, buyer)

    def transport(method, path, body, headers):
        status, data = net.transport(method, path, body, headers)
        if path == f"/catalog/orders/{order['id']}" and isinstance(data, dict):
            data.pop(drop, None)
        return status, data

    with pytest.raises(cli.CatalogError, match="not signing"):
        cli.CatalogClient(transport, buyer).build_payment(order["id"])
    assert ("GET", "/network/info") not in net.requests
