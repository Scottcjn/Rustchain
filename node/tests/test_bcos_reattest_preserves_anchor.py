# SPDX-License-Identifier: MIT
"""
Test: re-attesting an existing BCOS cert_id must not overwrite/erase the record.

Bug:
  bcos_attest() stored with `INSERT OR REPLACE`, but cert_id is UNIQUE and the
  handler carries an `except sqlite3.IntegrityError -> 409 "already exists"`
  guard. INSERT OR REPLACE resolves a UNIQUE conflict with a silent DELETE+
  INSERT, so it never raises IntegrityError: the 409 guard was dead code and a
  second attest for a known cert_id silently overwrote repo/tier/trust_score/
  reviewer/report. Worse, the REPLACE column list omits anchor_tx and passes
  anchored_epoch=None, so re-attesting a *ledger-anchored* cert wiped its
  anchor_tx back to NULL. That breaks /api/v1/bcos/anchor's documented
  idempotency ("a cert that is already anchored returns its existing tx hash
  rather than writing a second ledger row"): after the wipe, a re-anchor no
  longer short-circuits and writes a *second* ledger row with a new tx hash.

  Because auth passes on `is_admin OR valid Ed25519 sig over a caller-supplied
  signer_pubkey`, any party could self-sign a report and overwrite a public
  cert_id.

Fix: plain INSERT so the duplicate raises IntegrityError and the 409 guard
fires, preserving the original (and its anchor).

Same overwrite class as node/tests/test_attestation_overwrite_reward_loss.py.
"""

import json
import os
import sqlite3
import sys
from hashlib import blake2b

from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from bcos_routes import init_bcos_table, register_bcos_routes


def _with_commitment(report):
    report = dict(report)
    commitment_report = {
        k: v for k, v in report.items()
        if k not in ("cert_id", "commitment")
    }
    canonical = json.dumps(commitment_report, sort_keys=True, separators=(",", ":"))
    report["commitment"] = blake2b(canonical.encode(), digest_size=32).hexdigest()
    return report


def _make_app(db_path):
    with sqlite3.connect(db_path) as conn:
        init_bcos_table(conn)
    app = Flask(__name__)
    register_bcos_routes(app, str(db_path))
    app.config["TESTING"] = True
    return app


def test_reattest_duplicate_cert_id_is_rejected_and_preserves_anchor(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin")
    db_path = tmp_path / "bcos.db"
    app = _make_app(db_path)
    client = app.test_client()

    original = _with_commitment({
        "cert_id": "BCOS-anchored",
        "repo": "Scottcjn/Rustchain",
        "commit_sha": "abcdef1234567890",
        "tier": "L2",
        "trust_score": 90,
        "reviewer": "codex-reviewer",
    })
    assert client.post(
        "/bcos/attest", headers={"X-Admin-Key": "test-admin"}, json=original
    ).status_code == 200

    # Simulate a ledger anchor having been recorded for this cert.
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE bcos_attestations SET anchored_epoch = ?, anchor_tx = ? "
            "WHERE cert_id = ?",
            (42, "deadbeefTXHASH", "BCOS-anchored"),
        )
        conn.commit()

    # Attacker re-attests the SAME cert_id with a forged score/repo.
    forged = _with_commitment({
        "cert_id": "BCOS-anchored",
        "repo": "attacker/evil",
        "commit_sha": "0000000000000000",
        "tier": "L4",
        "trust_score": 100,
        "reviewer": "attacker",
    })
    resp = client.post(
        "/bcos/attest", headers={"X-Admin-Key": "test-admin"}, json=forged
    )

    # Duplicate cert_id must be rejected, not silently overwritten.
    assert resp.status_code == 409
    assert "already exists" in resp.get_json()["error"]

    # Original record and its anchor survive untouched.
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT repo, trust_score, anchored_epoch, anchor_tx "
            "FROM bcos_attestations WHERE cert_id = ?",
            ("BCOS-anchored",),
        ).fetchone()

    assert row["repo"] == "Scottcjn/Rustchain"
    assert row["trust_score"] == 90
    assert row["anchored_epoch"] == 42
    assert row["anchor_tx"] == "deadbeefTXHASH"
