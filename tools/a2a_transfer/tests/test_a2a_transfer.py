"""Tests for tools/a2a_transfer — agent-to-agent on-chain transfers (#13519).

No network access: the RustChain node is replaced by a fake opener that records
requests and verifies the Ed25519 signature exactly the way the node does.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import pytest

MODULE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "a2a_transfer.py",
)
_spec = importlib.util.spec_from_file_location("a2a_transfer", MODULE_PATH)
a2a = importlib.util.module_from_spec(_spec)
sys.modules["a2a_transfer"] = a2a
_spec.loader.exec_module(a2a)

SEED_A = bytes(range(32))
SEED_B = bytes(range(32, 64))


def _verify(public_key_hex: str, signature_hex: str, message: bytes) -> bool:
    try:
        from nacl.signing import VerifyKey

        VerifyKey(bytes.fromhex(public_key_hex)).verify(
            message, bytes.fromhex(signature_hex)
        )
        return True
    except ImportError:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex)).verify(
                bytes.fromhex(signature_hex), message
            )
            return True
        except InvalidSignature:
            return False
    except Exception:
        return False


class FakeNode:
    """Signature-checking stand-in for POST /wallet/transfer/signed."""

    def __init__(self, accept_legacy_only=False, fail_first_signature=False):
        self.requests = []
        self.accept_legacy_only = accept_legacy_only
        self.fail_first_signature = fail_first_signature
        self._calls = 0

    def __call__(self, url, body, timeout):
        self._calls += 1
        payload = json.loads(body.decode()) if body else {}
        self.requests.append((url, payload))
        if body is None:
            return {"balance_rtc": 42.0}
        current, legacy = a2a.canonical_messages(
            payload["from_address"],
            payload["to_address"],
            payload["amount_rtc"],
            payload.get("fee_rtc", 0.0),
            payload.get("memo", ""),
            payload["nonce"],
            payload.get("chain_id"),
        )
        if self.fail_first_signature and self._calls == 1:
            return {"ok": False, "error": "invalid signature"}
        candidates = [legacy] if self.accept_legacy_only else [current, legacy]
        for message in candidates:
            if _verify(payload["public_key"], payload["signature"], message):
                digest = hashlib.sha256(body).hexdigest()
                return {"ok": True, "tx_hash": digest, "pending_id": digest[:16]}
        return {"ok": False, "error": "invalid signature"}


@pytest.fixture
def signer_a():
    return a2a.Ed25519Signer(SEED_A)


@pytest.fixture
def signer_b():
    return a2a.Ed25519Signer(SEED_B)


# --------------------------------------------------------------------------- #
# canonical message / address helpers
# --------------------------------------------------------------------------- #
def test_canonical_message_matches_node_format():
    current, legacy = a2a.canonical_messages(
        "RTC" + "a" * 40, "RTC" + "b" * 40, 1.0, 0.0, "", 1700000000000,
        "rustchain-mainnet-v2",
    )
    assert current == (
        b'{"amount":1.0,"chain_id":"rustchain-mainnet-v2","fee":0.0,'
        b'"from":"RTC' + b"a" * 40 + b'","memo":"","nonce":1700000000000,'
        b'"to":"RTC' + b"b" * 40 + b'"}'
    )
    assert b'"fee"' not in legacy
    # compact separators, deterministic key order
    assert b", " not in current and b'": ' not in current


def test_address_from_pubkey_matches_node_rule():
    pubkey = "ab" * 32
    expected = "RTC" + hashlib.sha256(bytes.fromhex(pubkey)).hexdigest()[:40]
    assert a2a.address_from_pubkey(pubkey) == expected
    assert a2a.ADDRESS_RE.match(expected)


def test_signer_address_is_self_consistent(signer_a):
    assert signer_a.address == a2a.address_from_pubkey(signer_a.public_key_hex)
    assert a2a.ADDRESS_RE.match(signer_a.address)


@pytest.mark.parametrize(
    "bad", ["", "RTC", "0x" + "a" * 40, "RTC" + "A" * 40, "RTC" + "a" * 39, None]
)
def test_validate_address_rejects_non_native_wallets(bad):
    with pytest.raises(a2a.A2AError):
        a2a.validate_address(bad)


# --------------------------------------------------------------------------- #
# nonces
# --------------------------------------------------------------------------- #
def test_nonce_factory_is_strictly_monotonic():
    frozen = a2a.NonceFactory(clock=lambda: 1700000000.0)
    values = [frozen.next() for _ in range(5)]
    assert values == sorted(set(values)) and len(set(values)) == 5


# --------------------------------------------------------------------------- #
# payload construction guards
# --------------------------------------------------------------------------- #
def test_build_payload_rejects_self_transfer(signer_a):
    with pytest.raises(a2a.A2AError, match="self-transfer"):
        a2a.build_payload(signer_a, signer_a.address, 1.0, 1)


def test_build_payload_rejects_below_one_rtc(signer_a, signer_b):
    with pytest.raises(a2a.A2AError, match="at least 1 RTC"):
        a2a.build_payload(signer_a, signer_b.address, 0.5, 1)


def test_build_payload_signature_verifies(signer_a, signer_b):
    payload = a2a.build_payload(signer_a, signer_b.address, 1.0, 12345)
    current, _ = a2a.canonical_messages(
        signer_a.address, signer_b.address, 1.0, 0.0, "", 12345,
        a2a.DEFAULT_CHAIN_ID,
    )
    assert _verify(payload["public_key"], payload["signature"], current)


# --------------------------------------------------------------------------- #
# transfers
# --------------------------------------------------------------------------- #
def test_send_transfer_success(signer_a, signer_b):
    node = FakeNode()
    client = a2a.RustChainClient("https://node.test", opener=node)
    result = a2a.send_transfer(client, signer_a, signer_b.address, 1.0)
    assert result.ok and result.tx_hash and result.pending_id
    url, payload = node.requests[0]
    assert url == "https://node.test/wallet/transfer/signed"
    assert payload["from_address"] == signer_a.address
    assert payload["to_address"] == signer_b.address
    assert payload["amount_rtc"] == 1.0
    assert "seed" not in json.dumps(payload)


def test_send_transfer_retries_with_legacy_message(signer_a, signer_b):
    node = FakeNode(accept_legacy_only=True)
    client = a2a.RustChainClient("https://node.test", opener=node)
    result = a2a.send_transfer(client, signer_a, signer_b.address, 1.0)
    assert result.ok, result.error
    assert len(node.requests) == 2
    assert node.requests[0][1]["nonce"] != node.requests[1][1]["nonce"]


def test_send_transfer_reports_rejection(signer_a, signer_b):
    class Rejecting:
        def __call__(self, url, body, timeout):
            return {"ok": False, "error": "insufficient balance"}

    client = a2a.RustChainClient("https://node.test", opener=Rejecting())
    result = a2a.send_transfer(client, signer_a, signer_b.address, 1.0)
    assert not result.ok and result.error == "insufficient balance"


def test_round_trip_produces_both_legs(signer_a, signer_b):
    node = FakeNode()
    client = a2a.RustChainClient("https://node.test", opener=node)
    report = a2a.round_trip(client, signer_a, signer_b, 1.0)
    assert report["complete"] is True
    assert report["outbound"]["from_address"] == signer_a.address
    assert report["inbound"]["from_address"] == signer_b.address
    assert report["inbound"]["to_address"] == signer_a.address
    assert report["outbound"]["nonce"] != report["inbound"]["nonce"]


def test_round_trip_rejects_same_agent(signer_a):
    client = a2a.RustChainClient("https://node.test", opener=FakeNode())
    with pytest.raises(a2a.A2AError, match="distinct agents"):
        a2a.round_trip(client, signer_a, signer_a, 1.0)


def test_round_trip_skips_return_leg_when_outbound_fails(signer_a, signer_b):
    class Rejecting:
        calls = 0

        def __call__(self, url, body, timeout):
            Rejecting.calls += 1
            return {"ok": False, "error": "nope"}

    rejecting = Rejecting()
    client = a2a.RustChainClient("https://node.test", opener=rejecting)
    report = a2a.round_trip(client, signer_a, signer_b, 1.0)
    assert report["complete"] is False and report["inbound"] is None


# --------------------------------------------------------------------------- #
# key loading & CLI
# --------------------------------------------------------------------------- #
def test_signer_from_hex_and_json_file(tmp_path, signer_a):
    hex_file = tmp_path / "a.key"
    hex_file.write_text(SEED_A.hex())
    json_file = tmp_path / "a.json"
    json_file.write_text(json.dumps({"seed": SEED_A.hex()}))
    assert a2a.Ed25519Signer.from_file(str(hex_file)).address == signer_a.address
    assert a2a.Ed25519Signer.from_file(str(json_file)).address == signer_a.address


def test_signer_accepts_expanded_64_byte_key(signer_a):
    expanded = SEED_A.hex() + signer_a.public_key_hex
    assert a2a.Ed25519Signer.from_hex(expanded).address == signer_a.address


def test_cli_address_command(tmp_path, capsys, signer_a):
    key = tmp_path / "a.key"
    key.write_text(SEED_A.hex())
    code = a2a.main(["address", "--key-file", str(key)])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["address"] == signer_a.address


def test_cli_reports_error_without_key(capsys):
    os.environ.pop("RUSTCHAIN_AGENT_KEY", None)
    code = a2a.main(["send", "--to", "RTC" + "b" * 40])
    assert code == 2
    assert "no key" in capsys.readouterr().err
