# SPDX-License-Identifier: MIT

import os
import sys

from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import sophia_attestation_inspector


class _FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_llm_fallback_continues_after_non_object_json(monkeypatch):
    posts = iter([
        _FakeResponse(["not", "an", "object"]),
        _FakeResponse({"response": "approved"}),
    ])

    def fake_post(*args, **kwargs):
        return next(posts)

    monkeypatch.setattr(sophia_attestation_inspector.requests, "post", fake_post)

    assert sophia_attestation_inspector._call_ollama("inspect", endpoint="http://llm") == "approved"


def test_deep_model_rejects_non_object_json(monkeypatch):
    monkeypatch.setattr(
        sophia_attestation_inspector.requests,
        "post",
        lambda *args, **kwargs: _FakeResponse([{"text": "not an object"}]),
    )

    assert sophia_attestation_inspector._call_deep_model("inspect deeply") is None


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


def test_sophia_inspect_rejects_non_object_json_before_inspection(monkeypatch):
    app = Flask(__name__)
    app.config["TESTING"] = True
    monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin")
    sophia_attestation_inspector.register_sophia_endpoints(app, ":memory:")

    inspect_calls = []

    def fake_inspect(*args, **kwargs):
        inspect_calls.append((args, kwargs))
        return {"ok": True}

    monkeypatch.setattr(sophia_attestation_inspector, "inspect_miner", fake_inspect)

    response = app.test_client().post(
        "/sophia/inspect",
        headers={"X-Admin-Key": "expected-admin"},
        json=["miner_id"],
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "JSON object required"}
    assert inspect_calls == []
