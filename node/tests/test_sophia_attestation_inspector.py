# SPDX-License-Identifier: MIT

import os
import sys

from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import sophia_attestation_inspector


def test_sophia_inspector_admin_auth_uses_constant_time_compare(monkeypatch):
    app = Flask(__name__)
    app.config["TESTING"] = True
    monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin")
    sophia_attestation_inspector.register_sophia_endpoints(app, ":memory:")

    calls = []

    def spy_compare_digest(provided, expected):
        calls.append((provided, expected))
        return provided == expected

    monkeypatch.setattr(sophia_attestation_inspector.hmac, "compare_digest", spy_compare_digest)
    monkeypatch.setattr(
        sophia_attestation_inspector,
        "inspect_miner",
        lambda *args, **kwargs: {"ok": True, "miner": args[0]},
    )

    client = app.test_client()
    denied = client.post(
        "/sophia/inspect",
        headers={"X-Admin-Key": "wrong-admin"},
        json={"miner_id": "alice"},
    )
    assert denied.status_code == 401

    accepted = client.post(
        "/sophia/inspect",
        headers={"X-API-Key": "expected-admin"},
        json={"miner_id": "alice"},
    )
    assert accepted.status_code == 200
    assert accepted.get_json() == {"ok": True, "miner": "alice"}

    assert calls == [
        ("wrong-admin", "expected-admin"),
        ("expected-admin", "expected-admin"),
    ]
