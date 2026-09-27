# SPDX-License-Identifier: MIT
"""Test harness for RIP-302 under RIP-302-SEC / SEC-2 auth.

Production requires a pinned settlement-authority signature on
accept/dispute/cancel, and proof of control of ``poster_wallet`` on job
create (Ed25519 for keyed wallets, ``X-Admin-Key`` for named/treasury
wallets). Business-logic tests that predate the hardening post plain
requests, so this module supplies an operator-authorised client.

Import the fixture into a test module to opt in::

    from tests.rip302_auth_helpers import rip302_authorized  # noqa: F401

Tests that check the auth gates themselves should not import it.
"""
import os
import re

import pytest
from flask import Flask
from flask.testing import FlaskClient
from nacl.signing import SigningKey

import rip302_agent_economy

SETTLEMENT_KEY = SigningKey(bytes(range(32)))
_SETTLE_PATH = re.compile(r"^/agent/jobs/([^/?]+)/(accept|dispute|cancel)$")


def settlement_sig(job_id, action):
    return SETTLEMENT_KEY.sign(f"{job_id}:{action}".encode()).signature.hex()


class Rip302AuthorizedClient(FlaskClient):
    """Adds the operator credentials a real settlement authority would send."""

    def open(self, *args, **kwargs):
        path = args[0] if args and isinstance(args[0], str) else ""
        if kwargs.get("method", "GET").upper() == "POST" and path:
            path_only = path.split("?", 1)[0]
            if path_only.rstrip("/") == "/agent/jobs":
                headers = dict(kwargs.get("headers") or {})
                headers.setdefault("X-Admin-Key", os.environ.get("RC_ADMIN_KEY", ""))
                kwargs["headers"] = headers
            match = _SETTLE_PATH.match(path_only)
            body = kwargs.get("json")
            if match and isinstance(body, dict) and "settlement_sig" not in body:
                kwargs["json"] = {**body, "settlement_sig": settlement_sig(*match.groups())}
        return super().open(*args, **kwargs)


@pytest.fixture(autouse=True)
def rip302_authorized(monkeypatch):
    monkeypatch.setattr(rip302_agent_economy, "SETTLEMENT_PUBKEY_HEX",
                        SETTLEMENT_KEY.verify_key.encode().hex())
    monkeypatch.setenv("RC_ADMIN_KEY", os.environ.get("RC_ADMIN_KEY") or "0" * 32)
    monkeypatch.setattr(Flask, "test_client_class", Rip302AuthorizedClient)
