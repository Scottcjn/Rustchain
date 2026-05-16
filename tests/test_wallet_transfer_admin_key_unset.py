# SPDX-License-Identifier: MIT
"""
Regression test: fail-closed behavior when RC_ADMIN_KEY is unset.

Cherry-picked finding from BossChaos PR #5174.

The bug: several admin-gated endpoints called
    hmac.compare_digest(admin_key, os.environ.get("RC_ADMIN_KEY", ""))
without first checking that the env var was non-empty. If RC_ADMIN_KEY
became empty at request time (env unset, container misconfig, runtime
mutation), then `hmac.compare_digest("", "")` returns True and the
endpoint would be effectively unauthenticated.

Module-level startup already exits if RC_ADMIN_KEY is missing, but this
test pins the per-request fail-closed behavior so the latent bug cannot
return via a startup-bypass refactor.

We assert 503 (ADMIN_KEY_UNSET), NOT 401, when the env is empty — the
distinction matters because 401 implies "you sent the wrong key" and a
caller could brute-force; 503 makes the operator state explicit.
"""

import sys

import pytest

# Pre-loaded by conftest.py
integrated_node = sys.modules["integrated_node"]


@pytest.fixture
def client():
    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as c:
        yield c


# Endpoints that previously fell through to compare_digest with empty env.
# Each entry: (method, path, json_body_or_none, expected_503_when_unset)
ADMIN_GATED_ENDPOINTS = [
    ("POST", "/wallet/transfer", {"from_miner": "a", "to_miner": "b", "amount_rtc": 1}),
    ("POST", "/rewards/settle", {"epoch": 1}),
    ("GET", "/pending/list", None),
    ("POST", "/pending/void", {"tx_id": "x"}),
    ("POST", "/pending/confirm", {}),
    ("GET", "/pending/integrity", None),
    ("GET", "/wallet/ledger", None),
    ("GET", "/wallet/balances/all", None),
]


def _request(client, method, path, body):
    if method == "GET":
        return client.get(path)
    return client.post(path, json=body)


@pytest.mark.parametrize("method,path,body", ADMIN_GATED_ENDPOINTS)
def test_admin_endpoint_returns_503_when_admin_key_unset(monkeypatch, client, method, path, body):
    """When RC_ADMIN_KEY is empty, endpoint must return 503 ADMIN_KEY_UNSET, not 401."""
    monkeypatch.setenv("RC_ADMIN_KEY", "")

    resp = _request(client, method, path, body)

    assert resp.status_code == 503, (
        f"{method} {path}: expected 503 when RC_ADMIN_KEY empty, "
        f"got {resp.status_code} (body={resp.get_data(as_text=True)[:200]})"
    )
    payload = resp.get_json() or {}
    code = payload.get("code") or payload.get("reason") or ""
    assert "ADMIN_KEY_UNSET" in str(code) or "admin_key_unset" in str(code), (
        f"{method} {path}: expected ADMIN_KEY_UNSET code, got payload={payload}"
    )


@pytest.mark.parametrize("method,path,body", ADMIN_GATED_ENDPOINTS)
def test_admin_endpoint_returns_401_with_wrong_key(monkeypatch, client, method, path, body):
    """When RC_ADMIN_KEY is set but caller sends wrong/no key, return 401 (not 503)."""
    monkeypatch.setenv("RC_ADMIN_KEY", "a" * 32)

    resp = _request(client, method, path, body)

    # 401 (unauthorized) is the correct response — NOT 503.
    # We also accept 400 if the body fails validation BEFORE the auth check
    # is reached, but auth-first endpoints should give 401.
    assert resp.status_code == 401, (
        f"{method} {path}: expected 401 with wrong admin key, got {resp.status_code} "
        f"(body={resp.get_data(as_text=True)[:200]})"
    )


def test_wallet_transfer_does_not_authenticate_empty_to_empty(monkeypatch, client):
    """
    Direct regression: the original bug was that with RC_ADMIN_KEY unset
    AND no X-Admin-Key header, hmac.compare_digest("", "") returned True.
    Assert this cannot happen — no admin-gated wallet transfer goes through
    without a configured key, regardless of header content.
    """
    monkeypatch.setenv("RC_ADMIN_KEY", "")

    # No header at all
    resp1 = client.post("/wallet/transfer", json={"from_miner": "a", "to_miner": "b", "amount_rtc": 1})
    assert resp1.status_code == 503

    # Empty header
    resp2 = client.post(
        "/wallet/transfer",
        json={"from_miner": "a", "to_miner": "b", "amount_rtc": 1},
        headers={"X-Admin-Key": ""},
    )
    assert resp2.status_code == 503

    # Any attacker-supplied header
    resp3 = client.post(
        "/wallet/transfer",
        json={"from_miner": "a", "to_miner": "b", "amount_rtc": 1},
        headers={"X-Admin-Key": "anything"},
    )
    assert resp3.status_code == 503
