# SPDX-License-Identifier: MIT
"""Tests for the canonical /api/v1 read API blueprint."""
import importlib.util
import sqlite3
import sys
import time
from pathlib import Path

import pytest
from flask import Flask

NODE = Path(__file__).resolve().parents[1] / "node"
sys.path.insert(0, str(NODE))
spec = importlib.util.spec_from_file_location("api_v1_under_test", NODE / "api_v1.py")
api_v1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api_v1)


@pytest.fixture
def client(tmp_path):
    db = tmp_path / "v1.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE schema_version (v INTEGER);
        INSERT INTO schema_version VALUES (1);
        CREATE TABLE headers (slot INTEGER, miner_id TEXT, message_hex TEXT,
            signature_hex TEXT, pubkey_hex TEXT, ts INTEGER);
        CREATE TABLE miner_attest_recent (miner TEXT, ts_ok INTEGER,
            device_family TEXT, device_arch TEXT, entropy_score REAL,
            fingerprint_passed INTEGER);
        CREATE TABLE ergo_anchors (id INTEGER PRIMARY KEY, commitment TEXT,
            miner_count INTEGER, miner_data TEXT, rc_slot INTEGER,
            ergo_height INTEGER, tx_id TEXT, status TEXT, created_at INTEGER);
        CREATE TABLE epoch_enroll (epoch INTEGER, miner TEXT);
        CREATE TABLE epoch_state (epoch INTEGER, settled INTEGER, settled_ts INTEGER);
        CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER);
        CREATE TABLE governance_proposals (id INTEGER PRIMARY KEY, proposer_wallet TEXT,
            title TEXT, description TEXT, created_at INTEGER, activated_at INTEGER,
            ends_at INTEGER, status TEXT, yes_weight REAL, no_weight REAL);
    """)
    now = int(time.time())
    conn.execute("INSERT INTO headers VALUES (1700,'minerA','','','',?)", (now,))
    conn.execute("INSERT INTO headers VALUES (1701,'minerB','','','',?)", (now,))
    conn.execute("INSERT INTO miner_attest_recent VALUES ('minerA',?, 'POWER8','power8',0.9,1)", (now,))
    conn.execute("INSERT INTO ergo_anchors (commitment,miner_count,tx_id,status,created_at) VALUES ('abc',5,'txid1','confirmed',?)", (now,))
    conn.execute("INSERT INTO epoch_enroll VALUES (10,'minerA')")
    conn.execute("INSERT INTO epoch_state VALUES (10,0,0)")
    conn.execute("INSERT INTO balances VALUES ('minerA', 5000000)")
    conn.execute("INSERT INTO governance_proposals (proposer_wallet,title,status,created_at,ends_at,yes_weight,no_weight) VALUES ('w','T','active',?,?,1,0)", (now, now+1000))
    conn.commit(); conn.close()

    app = Flask(__name__)
    api_v1.register_api_v1(
        app, db_path=str(db),
        current_slot=lambda: 1701, slot_to_epoch=lambda s: 10,
        app_version="test", app_start_ts=time.time(),
        per_epoch_rtc=1.5, epoch_slots=144, total_supply_rtc=8388608,
    )
    app.config["TESTING"] = True
    return app.test_client()


def test_index_lists_endpoints(client):
    r = client.get("/api/v1/")
    assert r.status_code == 200 and r.get_json()["ok"] is True
    assert any("blocks" in e for e in r.get_json()["endpoints"])


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200 and r.get_json()["db_ok"] is True


def test_info_chain_summary(client):
    r = client.get("/api/v1/info")
    j = r.get_json()
    assert r.status_code == 200 and j["epoch"] == 10 and j["tip_height"] == 1701
    assert j["active_miners_24h"] == 1


def test_epoch(client):
    j = client.get("/api/v1/epoch").get_json()
    assert j["epoch"] == 10 and j["enrolled_miners"] == 1 and j["settled"] is False


def test_miners(client):
    j = client.get("/api/v1/miners").get_json()
    assert j["count"] == 1 and j["miners"][0]["device_arch"] == "power8"


def test_blocks_and_latest_and_by_slot(client):
    assert client.get("/api/v1/blocks").get_json()["count"] == 2
    assert client.get("/api/v1/blocks/latest").get_json()["block"]["slot"] == 1701
    assert client.get("/api/v1/blocks/1700").get_json()["block"]["miner_id"] == "minerA"
    assert client.get("/api/v1/blocks/999999").status_code == 404


def test_anchors_and_leaderboard_and_governance(client):
    assert client.get("/api/v1/anchors").get_json()["anchors"][0]["tx_id"] == "txid1"
    lb = client.get("/api/v1/leaderboard").get_json()
    assert lb["leaderboard"][0]["balance_rtc"] == 5.0
    assert client.get("/api/v1/governance/proposals").get_json()["count"] == 1


def test_unknown_v1_path_returns_json_404_not_nginx(client):
    r = client.get("/api/v1/totally/made/up")
    assert r.status_code == 404
    j = r.get_json()
    assert j["error"] == "not_found" and "/api/v1/" in j["path"]
