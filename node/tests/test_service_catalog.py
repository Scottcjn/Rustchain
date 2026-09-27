# SPDX-License-Identifier: MIT
"""Tests for the RTC service catalog (node/service_catalog.py)."""
import hashlib
import json
import sqlite3
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from flask import Flask

import service_catalog as sc


class Agent:
    def __init__(self):
        self.key = Ed25519PrivateKey.generate()
        pub = self.key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.pubkey_hex = pub.hex()
        self.id = "bcn_" + hashlib.sha256(pub).hexdigest()[:12]
        self._n = 0

    def headers(self, method, path, body, *, ts=None, nonce=None):
        self._n += 1
        ts = int(time.time()) if ts is None else ts
        nonce = nonce or f"n{self._n}"
        msg = "\n".join([method, path, hashlib.sha256(body).hexdigest(),
                         str(ts), nonce, self.id]).encode()
        return {
            "X-Agent-Id": self.id,
            "X-Agent-Timestamp": str(ts),
            "X-Agent-Nonce": nonce,
            "X-Agent-Signature": self.key.sign(msg).hex(),
            "Content-Type": "application/json",
        }


@pytest.fixture
def env(tmp_path):
    db = str(tmp_path / "node.db")
    with sqlite3.connect(db) as conn:
        conn.execute("""CREATE TABLE pending_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT, from_miner TEXT, to_miner TEXT,
            amount_i64 INTEGER, reason TEXT, status TEXT, tx_hash TEXT)""")
    registry = {}
    app = Flask(__name__)
    assert sc.register_service_catalog(app, db, pubkey_resolver=registry.get)
    client = app.test_client()

    def make_agent():
        a = Agent()
        registry[a.id] = a.pubkey_hex
        return a

    def post(agent, path, payload, **kw):
        body = json.dumps(payload).encode()
        return client.post(path, data=body, headers=agent.headers("POST", path, body, **kw))

    return {"db": db, "client": client, "agent": make_agent, "post": post}


LISTING = {"title": "Render a 10s clip", "category": "render", "price_rtc": 2.5,
           "unit": "per clip", "turnaround_hours": 24}


def make_listing(env, provider, **over):
    r = env["post"](provider, "/catalog/listings", {**LISTING, **over})
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def full_order(env, provider, buyer, digest="a" * 64):
    listing = make_listing(env, provider)
    order = env["post"](buyer, "/catalog/orders", {"listing_id": listing["id"]}).get_json()
    r = env["post"](provider, f"/catalog/orders/{order['id']}/deliver", {"deliverable_hash": digest})
    assert r.status_code == 200, r.get_json()
    return order


def test_index_is_rtc_only_and_states_non_custody(env):
    body = env["client"].get("/catalog").get_json()
    assert body["currency"] == "RTC"
    assert "holds no funds" in body["terms"]
    assert "$" not in json.dumps(body)


def test_create_and_list_listing(env):
    p = env["agent"]()
    listing = make_listing(env, p)
    assert listing["provider"] == p.id and listing["price_rtc"] == 2.5
    listed = env["client"].get("/catalog/listings?category=render").get_json()["listings"]
    assert [x["id"] for x in listed] == [listing["id"]]


@pytest.mark.parametrize("field,value", [
    ("price_usd", 1), ("usd_value", "0.10"), ("reference_rate", 0.1)])
def test_unknown_fields_rejected(env, field, value):
    r = env["post"](env["agent"](), "/catalog/listings", {**LISTING, field: value})
    assert r.status_code == 400 and r.get_json()["error"] == "unknown_fields"


@pytest.mark.parametrize("title", [
    "Render for $5", "Render 5$ each", "Render worth 3 USD", "Paid in USDC",
    "Ten dollars", "Costs USD5", "Only 5USD", "Fullwidth \uff045 ok", "Five euros each"])
def test_fiat_text_rejected(env, title):
    r = env["post"](env["agent"](), "/catalog/listings", {**LISTING, "title": title})
    assert r.get_json()["error"] == "fiat_reference_not_allowed"


@pytest.mark.parametrize("price", [0, -1, "abc", True, 0.0000001, 100_001, "NaN", "1e999999", "-1e999999"])
def test_bad_prices_rejected(env, price):
    r = env["post"](env["agent"](), "/catalog/listings", {**LISTING, "price_rtc": price})
    assert r.status_code == 400


def test_unsigned_and_unregistered_rejected(env):
    c = env["client"]
    assert c.post("/catalog/listings", json=LISTING).status_code == 401
    stranger = Agent()  # never registered
    assert env["post"](stranger, "/catalog/listings", LISTING).status_code == 403


def test_bad_signature_stale_and_replay(env):
    p = env["agent"]()
    body = json.dumps(LISTING).encode()
    h = p.headers("POST", "/catalog/listings", body)
    h["X-Agent-Signature"] = "00" * 64
    assert env["client"].post("/catalog/listings", data=body, headers=h).status_code == 401
    stale = env["post"](p, "/catalog/listings", LISTING, ts=int(time.time()) - 1000)
    assert stale.status_code == 401
    future = env["post"](p, "/catalog/listings", LISTING, ts=int(time.time()) + 120)
    assert future.status_code == 401
    assert env["post"](p, "/catalog/listings", LISTING, nonce="same").status_code == 201
    assert env["post"](p, "/catalog/listings", LISTING, nonce="same").status_code == 401


def test_signature_bound_to_body(env):
    p = env["agent"]()
    signed = json.dumps(LISTING).encode()
    tampered = json.dumps({**LISTING, "price_rtc": 99}).encode()
    h = p.headers("POST", "/catalog/listings", signed)
    assert env["client"].post("/catalog/listings", data=tampered, headers=h).status_code == 401


def test_self_dealing_blocked(env):
    p = env["agent"]()
    listing = make_listing(env, p)
    r = env["post"](p, "/catalog/orders", {"listing_id": listing["id"]})
    assert r.get_json()["error"] == "self_dealing"


def test_order_happy_path_returns_payment_instructions(env):
    p, b = env["agent"](), env["agent"]()
    order = full_order(env, p, b)
    r = env["post"](b, f"/catalog/orders/{order['id']}/accept", {})
    body = r.get_json()
    assert body["status"] == "accepted"
    assert body["payment"] == {"state": "unpaid"}
    ins = body["payment_instructions"]
    assert ins == {"endpoint": "/wallet/transfer/signed", "to_address": p.id,
                   "amount_rtc": 2.5, "memo": f"svc:{order['id']}",
                   "note": ins["note"]}


def test_catalog_never_writes_ledger(env):
    p, b = env["agent"](), env["agent"]()
    order = full_order(env, p, b)
    env["post"](b, f"/catalog/orders/{order['id']}/accept", {})
    with sqlite3.connect(env["db"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM pending_ledger").fetchone()[0] == 0


def _pay(env, frm, to, amount_i64, memo, status="pending"):
    with sqlite3.connect(env["db"]) as conn:
        conn.execute("INSERT INTO pending_ledger (from_miner, to_miner, amount_i64, reason, "
                     "status, tx_hash) VALUES (?, ?, ?, ?, ?, 'tx1')",
                     (frm, to, amount_i64, "signed_transfer:" + memo, status))


def test_payment_reconciliation(env):
    p, b = env["agent"](), env["agent"]()
    order = full_order(env, p, b)
    env["post"](b, f"/catalog/orders/{order['id']}/accept", {})

    def get():
        return env["client"].get(f"/catalog/orders/{order['id']}").get_json()["payment"]

    memo = f"svc:{order['id']}"
    _pay(env, b.id, p.id, 1_000_000, memo)             # underpaid
    _pay(env, p.id, p.id, 5_000_000, memo)             # self-transfer
    _pay(env, b.id, p.id, 5_000_000, memo, "voided")   # voided
    _pay(env, b.id, "bcn_other00000", 5_000_000, memo) # wrong recipient
    assert get() == {"state": "unpaid"}
    _pay(env, b.id, p.id, 2_500_000, memo)
    assert get()["state"] == "pending"
    _pay(env, b.id, p.id, 2_500_000, memo, "confirmed")
    assert get()["state"] == "confirmed"


def test_deliverable_hash_settles_once_per_provider(env):
    p, b, other = env["agent"](), env["agent"](), env["agent"]()
    first = full_order(env, p, b, digest="b" * 64)
    listing = make_listing(env, p, title="Another render job")
    o2 = env["post"](b, "/catalog/orders", {"listing_id": listing["id"]}).get_json()
    path = f"/catalog/orders/{o2['id']}/deliver"
    assert env["post"](p, path, {"deliverable_hash": "b" * 64}).status_code == 409
    # Another provider can't be blocked by someone else's hash.
    full_order(env, other, b, digest="b" * 64)
    # A rejected order frees the hash for redelivery.
    env["post"](b, f"/catalog/orders/{first['id']}/reject", {"reason": "wrong size"})
    assert env["post"](p, path, {"deliverable_hash": "b" * 64}).status_code == 200


def test_only_right_party_transitions(env):
    p, b, x = env["agent"](), env["agent"](), env["agent"]()
    listing = make_listing(env, p)
    order = env["post"](b, "/catalog/orders", {"listing_id": listing["id"]}).get_json()
    path = f"/catalog/orders/{order['id']}"
    assert env["post"](b, path + "/deliver", {"deliverable_hash": "c" * 64}).status_code == 403
    assert env["post"](x, path + "/cancel", {}).status_code == 403
    assert env["post"](b, path + "/accept", {}).status_code == 409  # not delivered yet
    env["post"](p, path + "/deliver", {"deliverable_hash": "c" * 64})
    assert env["post"](p, path + "/accept", {}).status_code == 403
    assert env["post"](b, path + "/cancel", {}).status_code == 409  # past requested
    r = env["post"](b, path + "/reject", {"reason": "wrong format"})
    assert r.get_json()["status"] == "rejected"


def test_inactive_listing_cannot_be_ordered_and_retired_is_final(env):
    p, b = env["agent"](), env["agent"]()
    listing = make_listing(env, p)
    path = f"/catalog/listings/{listing['id']}/status"
    assert env["post"](b, path, {"status": "paused"}).status_code == 403
    assert env["post"](p, path, {"status": "paused"}).get_json()["status"] == "paused"
    assert env["post"](b, "/catalog/orders", {"listing_id": listing["id"]}).status_code == 409
    assert env["post"](p, path, {"status": "retired"}).status_code == 200
    assert env["post"](p, path, {"status": "active"}).status_code == 409


def test_price_snapshot_survives_new_listing(env):
    p, b = env["agent"](), env["agent"]()
    order = full_order(env, p, b)
    make_listing(env, p, price_rtc=9)
    got = env["client"].get(f"/catalog/orders/{order['id']}").get_json()
    assert got["price_rtc"] == 2.5


def test_provider_record_counts_work_not_rtc(env):
    p, b1, b2 = env["agent"](), env["agent"](), env["agent"]()
    for buyer, digest in ((b1, "d" * 64), (b2, "e" * 64)):
        o = full_order(env, p, buyer, digest=digest)
        env["post"](buyer, f"/catalog/orders/{o['id']}/accept", {})
    rec = env["client"].get(f"/catalog/providers/{p.id}").get_json()
    assert rec["orders_accepted"] == 2 and rec["distinct_buyers_accepted"] == 2
    assert not any("rtc" in k for k in rec)


def test_listing_cap(env, monkeypatch):
    monkeypatch.setattr(sc, "MAX_ACTIVE_LISTINGS", 2)
    p = env["agent"]()
    make_listing(env, p)
    make_listing(env, p)
    assert env["post"](p, "/catalog/listings", LISTING).status_code == 429


def test_refused_request_spends_its_nonce(env):
    p, b = env["agent"](), env["agent"]()
    listing = make_listing(env, p)
    order = env["post"](b, "/catalog/orders", {"listing_id": listing["id"]}).get_json()
    path = f"/catalog/orders/{order['id']}/accept"
    body = b"{}"
    early = b.headers("POST", path, body)
    assert env["client"].post(path, data=body, headers=early).status_code == 409
    env["post"](p, f"/catalog/orders/{order['id']}/deliver", {"deliverable_hash": "f" * 64})
    replay = env["client"].post(path, data=body, headers=early)
    assert replay.status_code == 401
    assert env["client"].get(f"/catalog/orders/{order['id']}").get_json()["status"] == "delivered"


def test_atlas_resolver_requires_active_and_matching_id(tmp_path):
    atlas = str(tmp_path / "atlas.db")
    good, bad = Agent(), Agent()
    with sqlite3.connect(atlas) as conn:
        conn.execute("CREATE TABLE relay_agents (agent_id TEXT, pubkey_hex TEXT, status TEXT)")
        conn.execute("INSERT INTO relay_agents VALUES (?, ?, 'active')", (good.id, good.pubkey_hex))
        conn.execute("INSERT INTO relay_agents VALUES (?, ?, 'suspended')", (bad.id, bad.pubkey_hex))
    resolve = sc._atlas_pubkey_resolver(atlas)
    assert resolve(good.id) == good.pubkey_hex
    assert resolve(bad.id) is None
    # Heartbeats set "alive"/"degraded"; those stay usable, like the payment path.
    for status in ("alive", "degraded", "banned", "revoked"):
        a = Agent()
        with sqlite3.connect(atlas) as conn:
            conn.execute("INSERT INTO relay_agents VALUES (?, ?, ?)", (a.id, a.pubkey_hex, status))
        expected = None if status in ("banned", "revoked") else a.pubkey_hex
        assert resolve(a.id) == expected, status
    assert resolve("bcn_000000000000") is None
    assert not sc._id_matches_pubkey(good.id, bad.pubkey_hex)


def test_order_view_is_private_to_parties(env):
    p, b, x = env["agent"](), env["agent"](), env["agent"]()
    listing = make_listing(env, p)
    order = env["post"](b, "/catalog/orders", {"listing_id": listing["id"], "note": "secret brief"}).get_json()
    path = f"/catalog/orders/{order['id']}"
    public = env["client"].get(path).get_json()
    assert "note" not in public and "buyer" not in public
    for agent, code in ((b, 200), (p, 200), (x, 403)):
        r = env["client"].get(path, headers=agent.headers("GET", path, b""))
        assert r.status_code == code
    r = env["client"].get(path, headers=b.headers("GET", path, b""))
    assert r.get_json()["note"] == "secret brief"


def test_provider_inbox_and_signed_query(env):
    p, b = env["agent"](), env["agent"]()
    listing = make_listing(env, p)
    env["post"](b, "/catalog/orders", {"listing_id": listing["id"]})
    path = "/catalog/orders?role=provider&status=requested"
    r = env["client"].get(path, headers=p.headers("GET", path, b""))
    assert [o["buyer"] for o in r.get_json()["orders"]] == [b.id]
    # A signature for one query can't be reused for another.
    h = p.headers("GET", path, b"")
    assert env["client"].get("/catalog/orders?role=buyer", headers=h).status_code == 401


def test_fiat_in_order_note_rejected(env):
    p, b = env["agent"](), env["agent"]()
    listing = make_listing(env, p)
    r = env["post"](b, "/catalog/orders", {"listing_id": listing["id"], "note": "I'll pay $50 via PayPal"})
    assert r.get_json()["error"] == "fiat_reference_not_allowed"


def test_paid_counts_need_confirmed_transfer(env):
    p, b = env["agent"](), env["agent"]()
    order = full_order(env, p, b)
    env["post"](b, f"/catalog/orders/{order['id']}/accept", {})
    rec = lambda: env["client"].get(f"/catalog/providers/{p.id}").get_json()  # noqa: E731
    assert rec()["orders_accepted"] == 1 and rec()["orders_paid_confirmed"] == 0
    _pay(env, b.id, p.id, 2_500_000, f"svc:{order['id']}", "confirmed")
    assert rec()["orders_paid_confirmed"] == 1 and rec()["distinct_paying_buyers"] == 1


def test_daily_order_cap(env, monkeypatch):
    monkeypatch.setattr(sc, "MAX_ORDERS_PER_DAY", 1)
    p, b = env["agent"](), env["agent"]()
    listing = make_listing(env, p)
    first = env["post"](b, "/catalog/orders", {"listing_id": listing["id"]}).get_json()
    env["post"](b, f"/catalog/orders/{first['id']}/cancel", {})
    assert env["post"](b, "/catalog/orders", {"listing_id": listing["id"]}).status_code == 429
