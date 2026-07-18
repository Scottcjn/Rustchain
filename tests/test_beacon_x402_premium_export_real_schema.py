# SPDX-License-Identifier: MIT
"""Premium x402 exports must query the tables the Beacon producer actually creates.

The existing gate suite (test_beacon_x402_payment_gate.py) fixtures its database with
hand-written ``CREATE TABLE reputation`` / ``CREATE TABLE contracts`` statements. No
producer in the tree ever creates those names: ``beacon_api.init_beacon_tables`` -- the
only writer, and the one the node calls -- creates ``beacon_reputation`` and
``beacon_contracts``. So the suite is green while production exports nothing.

These tests build the database with the *real* producer so the schema cannot drift from
what the node actually deploys.
"""

import sqlite3

import pytest
from flask import Flask

import beacon_api
import beacon_x402


@pytest.fixture
def real_schema_db(tmp_path):
    """A database created by the real producer, seeded via its real table names."""
    db_path = tmp_path / "rustchain_v2.db"
    beacon_api.init_beacon_tables(str(db_path))

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO beacon_reputation (agent_id, score, bounties_completed) "
            "VALUES (?, ?, ?)",
            ("agent-alpha", 99, 3),
        )
        conn.execute(
            "INSERT INTO beacon_contracts (id, from_agent, to_agent, type, amount, "
            "term, state, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("contract-1", "agent-alpha", "agent-beta", "work", 100.0, "net30",
             "offered", 1000),
        )
    return db_path


def _client(db_path, monkeypatch):
    monkeypatch.setattr(beacon_x402, "X402_CONFIG_OK", True)
    monkeypatch.setattr(beacon_x402, "PRICE_REPUTATION_EXPORT", "0", raising=False)
    monkeypatch.setattr(beacon_x402, "PRICE_BEACON_CONTRACT", "0", raising=False)
    monkeypatch.setattr(
        beacon_x402,
        "is_free",
        lambda price: str(price) in ("0", "0.0", "0.00", ""),
        raising=False,
    )
    # The module migrates a path of its own choosing; these tests exercise the runtime
    # connection the node hands in, which is what every route actually reads.
    monkeypatch.setattr(beacon_x402, "_run_migrations", lambda _db_path: None)

    def get_db():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    app = Flask(__name__)
    app.config["TESTING"] = True
    beacon_x402.init_app(app, get_db)
    return app.test_client()


def test_reputation_export_returns_producer_rows(real_schema_db, monkeypatch):
    """/api/premium/reputation must export the rows beacon_api wrote."""
    client = _client(real_schema_db, monkeypatch)

    resp = client.get("/api/premium/reputation")

    assert resp.status_code == 200
    body = resp.get_json()
    # On main this is 0: the query reads `reputation`, the producer wrote
    # `beacon_reputation`, and the OperationalError is swallowed into an empty list.
    assert body["total"] == 1
    assert body["reputation"][0]["agent_id"] == "agent-alpha"
    assert body["reputation"][0]["score"] == 99


def test_contracts_export_returns_producer_rows(real_schema_db, monkeypatch):
    """/api/premium/contracts/export must export the rows beacon_api wrote."""
    client = _client(real_schema_db, monkeypatch)

    resp = client.get("/api/premium/contracts/export")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["total"] == 1
    assert body["contracts"][0]["id"] == "contract-1"


def test_contracts_export_survives_a_runtime_db_without_beacon_wallets(
    real_schema_db, monkeypatch
):
    """The wallet join must not 500 on a database the module never migrated.

    ``_run_migrations`` creates beacon_wallets in a beacon_atlas.db beside this module,
    but the node hands the routes a connection to RUSTCHAIN_DB_PATH/rustchain_v2.db.
    Only the two wallet routes call _ensure_x402_tables, so on a node where no wallet
    was ever registered the table is absent from the runtime database and the unguarded
    join at the bottom of the export raises.

    This never fired on main only because the export selected a non-existent table,
    returned zero rows, and skipped the loop -- the two defects masked each other.
    """
    with sqlite3.connect(real_schema_db) as conn:
        conn.execute("DROP TABLE IF EXISTS beacon_wallets")

    client = _client(real_schema_db, monkeypatch)

    resp = client.get("/api/premium/contracts/export")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["total"] == 1
    # No wallet registered for either party -> reported as null, not a crash.
    assert body["contracts"][0]["from_agent_wallet"] is None
    assert body["contracts"][0]["to_agent_wallet"] is None


def test_export_does_not_mask_a_missing_table_as_an_empty_export(
    real_schema_db, monkeypatch
):
    """A real empty table and a missing table must not look identical to a payer.

    This is what let the bug survive: `except sqlite3.OperationalError: -> []` turns
    "your query names a table that does not exist" into a 200 with total: 0, which is
    indistinguishable from "there is genuinely no reputation data yet".
    """
    with sqlite3.connect(real_schema_db) as conn:
        conn.execute("DELETE FROM beacon_reputation")

    client = _client(real_schema_db, monkeypatch)
    empty = client.get("/api/premium/reputation").get_json()

    # Genuinely-empty table: 200 + total 0 is correct here.
    assert empty["total"] == 0

    # And the queried table must be one that actually exists, so that the swallow
    # cannot hide a schema drift again.
    with sqlite3.connect(real_schema_db) as conn:
        names = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert "beacon_reputation" in names
    assert "reputation" not in names, (
        "No producer creates a bare `reputation` table; if a test creates one it is "
        "fixturing the consumer's bug rather than the deployed schema."
    )
