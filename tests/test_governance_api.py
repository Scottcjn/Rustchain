import gc
import json
import shutil
import sqlite3
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

integrated_node = sys.modules["integrated_node"]


@contextmanager
def _temporary_directory():
    path = tempfile.mkdtemp()
    try:
        yield path
    finally:
        for _ in range(5):
            try:
                shutil.rmtree(path)
                break
            except PermissionError:
                gc.collect()
                time.sleep(0.05)


def _vote_payload(proposal_id: int, wallet: str, vote: str, nonce: str):
    payload = {
        "proposal_id": proposal_id,
        "wallet": wallet,
        "vote": vote,
        "nonce": nonce,
    }
    return payload


def test_governance_propose_requires_gt_10_rtc_balance():
    with _temporary_directory() as td:
        db_path = str(Path(td) / "gov.db")
        integrated_node.DB_PATH = db_path
        integrated_node.app.config["DB_PATH"] = db_path
        integrated_node.init_db()

        with sqlite3.connect(db_path) as c:
            c.execute("INSERT INTO balances(miner_pk, balance_rtc) VALUES(?, ?)", ("RTC-low", 10.0))
            c.commit()

        integrated_node.app.config["TESTING"] = True
        with integrated_node.app.test_client() as client:
            resp = client.post(
                "/governance/propose",
                json={"wallet": "RTC-low", "title": "No", "description": "insufficient"},
            )
            assert resp.status_code == 403
            assert resp.get_json()["error"] == "insufficient_balance_to_propose"


def test_governance_propose_rejects_non_object_json():
    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as client:
        resp = client.post("/governance/propose", json=["not", "an", "object"])

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "JSON object required"


def test_governance_vote_rejects_non_object_json():
    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as client:
        resp = client.post("/governance/vote", json=["not", "an", "object"])

    assert resp.status_code == 400
    assert resp.get_json()["error"] == "JSON object required"


def test_governance_vote_rejects_invalid_proposal_id():
    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as client:
        resp = client.post(
            "/governance/vote",
            json={
                "proposal_id": "not-an-int",
                "wallet": "RTC-test",
                "vote": "yes",
                "nonce": "n-1",
                "signature": "ab",
                "public_key": "11" * 32,
            },
        )

    assert resp.status_code == 400
    assert resp.get_json()["error"] == (
        "proposal_id, wallet, vote(yes/no), nonce, signature, public_key are required"
    )


def test_governance_vote_flow_and_lifecycle_finalization():
    with _temporary_directory() as td:
        db_path = str(Path(td) / "gov.db")
        integrated_node.DB_PATH = db_path
        integrated_node.app.config["DB_PATH"] = db_path
        integrated_node.init_db()

        pub_hex = "11" * 32
        wallet = integrated_node.address_from_pubkey(pub_hex)

        with sqlite3.connect(db_path) as c:
            # proposer/voter has >10 RTC and can vote
            c.execute("INSERT INTO balances(miner_pk, balance_rtc) VALUES(?, ?)", (wallet, 20.0))
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS miner_attest_recent (
                    miner TEXT PRIMARY KEY,
                    ts_ok INTEGER,
                    device_family TEXT,
                    device_arch TEXT,
                    entropy_score REAL,
                    fingerprint_passed INTEGER,
                    source_ip TEXT
                )
                """
            )
            # mark as active miner in miner view used by node
            c.execute(
                """
                INSERT INTO miner_attest_recent(miner, ts_ok, device_family, device_arch, entropy_score, fingerprint_passed, source_ip)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (wallet, int(time.time()), "PowerPC", "g4", 1.0, 1, "127.0.0.1"),
            )
            c.commit()

        integrated_node.app.config["TESTING"] = True
        with integrated_node.app.test_client() as client:
            # Create proposal
            r1 = client.post(
                "/governance/propose",
                json={"wallet": wallet, "title": "Raise testnet fee", "description": "for anti-spam"},
            )
            assert r1.status_code == 201
            proposal_id = r1.get_json()["proposal"]["id"]

            # Signed YES vote (signature verification function is mocked)
            payload = _vote_payload(proposal_id, wallet, "yes", "n-1")
            with patch("integrated_node.verify_rtc_signature", return_value=True):
                r2 = client.post(
                    "/governance/vote",
                    json={
                        **payload,
                        "public_key": pub_hex,
                        "signature": "ab" * 64,
                    },
                )
            assert r2.status_code == 200
            body = r2.get_json()
            assert body["ok"] is True
            assert body["vote"] == "yes"
            assert body["vote_weight"] > 20.0  # includes antiquity multiplier for g4

            # Force proposal to end and ensure status becomes passed/failed
            with sqlite3.connect(db_path) as c:
                c.execute("UPDATE governance_proposals SET ends_at = ?, status = 'active' WHERE id = ?", (int(time.time()) - 1, proposal_id))
                c.commit()

            r3 = client.get(f"/governance/proposal/{proposal_id}")
            assert r3.status_code == 200
            detail = r3.get_json()["proposal"]
            assert detail["status"] in ("passed", "failed")
            assert detail["result"] in ("passed", "failed")
