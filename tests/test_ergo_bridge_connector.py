"""Unit tests for the Ergo bridge connector HTTP wrapper.

SPDX-License-Identifier: Apache-2.0
"""

import sys
import types
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_SRC = PROJECT_ROOT / "src" / "bridge"
sys.path.insert(0, str(BRIDGE_SRC))
sys.modules.setdefault("requests", types.SimpleNamespace(get=None, post=None))

from ergo_connector import ErgoBridgeConnector  # noqa: E402


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


@pytest.fixture
def connector():
    return ErgoBridgeConnector(
        ergo_rpc_url="https://ergo.example",
        rustchain_node_url="https://rustchain.example",
        contract_address="contract-123",
    )


def test_get_merkle_root_returns_node_payload(monkeypatch, connector):
    calls = []

    def fake_get(url):
        calls.append(url)
        return FakeResponse(200, {"merkle_root": "abc123"})

    monkeypatch.setattr("ergo_connector.requests.get", fake_get)

    assert connector.get_merkle_root() == "abc123"
    assert calls == ["https://rustchain.example/get_merkle_root"]


def test_submit_merkle_root_posts_contract_payload(monkeypatch, connector):
    posts = []

    def fake_post(url, json):
        posts.append((url, json))
        return FakeResponse(200, {"tx_id": "tx-1"})

    monkeypatch.setattr("ergo_connector.requests.post", fake_post)

    assert connector.submit_merkle_root_to_ergo("root-456") == {"tx_id": "tx-1"}
    assert posts == [
        (
            "https://ergo.example/submit_merkle_root",
            {"contract_address": "contract-123", "merkle_root": "root-456"},
        )
    ]


def test_verify_contract_distinguishes_existing_contract(monkeypatch, connector):
    responses = iter(
        [
            FakeResponse(200, {"status": "exists"}),
            FakeResponse(200, {"status": "missing"}),
        ]
    )

    monkeypatch.setattr("ergo_connector.requests.get", lambda url: next(responses))

    assert connector.verify_contract() is True
    assert connector.verify_contract() is False


@pytest.mark.parametrize(
    ("method_name", "patch_target", "response", "error_message"),
    [
        (
            "get_merkle_root",
            "ergo_connector.requests.get",
            FakeResponse(503),
            "Failed to fetch Merkle root from RustChain",
        ),
        (
            "submit_merkle_root_to_ergo",
            "ergo_connector.requests.post",
            FakeResponse(500),
            "Failed to submit Merkle root to Ergo",
        ),
        (
            "verify_contract",
            "ergo_connector.requests.get",
            FakeResponse(404),
            "Failed to verify contract on Ergo",
        ),
    ],
)
def test_connector_raises_for_failed_http_responses(
    monkeypatch, connector, method_name, patch_target, response, error_message
):
    monkeypatch.setattr(patch_target, lambda *args, **kwargs: response)

    method = getattr(connector, method_name)
    args = ("root-456",) if method_name == "submit_merkle_root_to_ergo" else ()

    with pytest.raises(Exception, match=error_message):
        method(*args)
