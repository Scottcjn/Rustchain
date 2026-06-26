import sys
from unittest.mock import patch

import pytest


integrated_node = sys.modules["integrated_node"]


def _invalid_signature_payload():
    public_key = "11" * 32
    return {
        "proposal_id": 1,
        "wallet": integrated_node.address_from_pubkey(public_key),
        "vote": "yes",
        "nonce": "rate-limit-test",
        "signature": "22" * 64,
        "public_key": public_key,
    }


@pytest.fixture(autouse=True)
def _reset_governance_vote_rate_limit(monkeypatch):
    monkeypatch.setattr(integrated_node, "GOVERNANCE_VOTE_RATE_LIMIT_MAX", 2)
    monkeypatch.setattr(integrated_node, "GOVERNANCE_VOTE_RATE_LIMIT_WINDOW", 60)
    integrated_node._GOVERNANCE_VOTE_RATE_LIMIT_BUCKETS.clear()
    yield
    integrated_node._GOVERNANCE_VOTE_RATE_LIMIT_BUCKETS.clear()


def test_governance_vote_rate_limit_returns_429_with_retry_after():
    payload = _invalid_signature_payload()

    with patch.object(integrated_node.time, "time", return_value=1000), \
            patch.object(integrated_node, "verify_rtc_signature", return_value=False):
        with integrated_node.app.test_client() as client:
            responses = [
                client.post(
                    "/governance/vote",
                    json=payload,
                    environ_base={"REMOTE_ADDR": "198.51.100.20"},
                )
                for _ in range(3)
            ]

    assert [response.status_code for response in responses] == [401, 401, 429]
    assert responses[2].get_json()["code"] == "GOVERNANCE_VOTE_RATE_LIMIT"
    assert responses[2].headers["Retry-After"] == "60"


def test_governance_vote_rate_limit_is_isolated_per_client_ip(monkeypatch):
    monkeypatch.setattr(integrated_node, "GOVERNANCE_VOTE_RATE_LIMIT_MAX", 1)
    payload = _invalid_signature_payload()

    with patch.object(integrated_node.time, "time", return_value=1000), \
            patch.object(integrated_node, "verify_rtc_signature", return_value=False):
        with integrated_node.app.test_client() as client:
            first = client.post(
                "/governance/vote",
                json=payload,
                environ_base={"REMOTE_ADDR": "198.51.100.21"},
            )
            limited = client.post(
                "/governance/vote",
                json=payload,
                environ_base={"REMOTE_ADDR": "198.51.100.21"},
            )
            other_client = client.post(
                "/governance/vote",
                json=payload,
                environ_base={"REMOTE_ADDR": "198.51.100.22"},
            )

    assert first.status_code == 401
    assert limited.status_code == 429
    assert other_client.status_code == 401


def test_invalid_governance_vote_signature_does_not_open_database():
    payload = _invalid_signature_payload()

    with patch.object(integrated_node, "verify_rtc_signature", return_value=False), \
            patch.object(
                integrated_node.sqlite3,
                "connect",
                side_effect=AssertionError("invalid signature must fail before SQLite"),
            ):
        with integrated_node.app.test_client() as client:
            response = client.post(
                "/governance/vote",
                json=payload,
                environ_base={"REMOTE_ADDR": "198.51.100.23"},
            )

    assert response.status_code == 401
    assert response.get_json()["error"] == "invalid_signature"
