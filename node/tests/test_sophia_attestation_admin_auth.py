# SPDX-License-Identifier: MIT
import os
import sys

from flask import Flask


sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import sophia_attestation_inspector as inspector


def test_sophia_inspect_admin_auth_uses_compare_digest(monkeypatch):
    app = Flask(__name__)
    app.config["TESTING"] = True
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin")
    monkeypatch.setattr(
        inspector,
        "inspect_miner",
        lambda miner_id, device=None, fingerprint=None, db_path=None: {"miner": miner_id, "ok": True},
    )
    calls = []

    def spy_compare_digest(provided, expected):
        calls.append((provided, expected))
        return True

    monkeypatch.setattr(inspector.hmac, "compare_digest", spy_compare_digest)

    inspector.register_sophia_endpoints(app, db_path=":memory:")
    response = app.test_client().post(
        "/sophia/inspect",
        headers={"X-Admin-Key": "test-admin"},
        json={"miner_id": "miner-1"},
    )

    assert response.status_code == 200
    assert calls == [("test-admin", "test-admin")]
