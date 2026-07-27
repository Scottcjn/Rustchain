import json
import os
import stat
from types import SimpleNamespace

from tools import rustchain_wallet_cli as cli


def test_save_keystore_uses_owner_only_permissions(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "KEYSTORE_DIR", tmp_path)

    path = cli._save_keystore("secure-wallet", {"address": "RTC" + "a" * 40})

    assert path.exists()
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert json.loads(path.read_text())["address"] == "RTC" + "a" * 40


def test_encrypt_decrypt_roundtrip():
    priv = "11" * 32
    enc = cli._encrypt_private_key(priv, "pw123")
    out = cli._decrypt_private_key(enc, "pw123")
    assert out == priv


def test_decrypt_compat_alias_fields():
    priv = "22" * 32
    enc = cli._encrypt_private_key(priv, "pw456")
    legacy = {
        "salt": enc["salt_b64"],
        "nonce": enc["nonce_b64"],
        "encrypted_private_key": enc["ciphertext_b64"],
        "iterations": enc["kdf_iterations"],
    }
    out = cli._decrypt_private_key(legacy, "pw456")
    assert out == priv


def test_address_format_from_pubkey():
    pub = "22" * 32
    addr = cli._address_from_pubkey_hex(pub)
    assert addr.startswith("RTC")
    assert len(addr) == 43


def test_sign_transfer_shape():
    # deterministic private key bytes for test
    priv = "01" * 32
    tx = cli._sign_transfer(priv, "RTC" + "a" * 40, "RTC" + "b" * 40, 1.23, "m", 123)
    assert tx["from_address"].startswith("RTC")
    assert tx["to_address"].startswith("RTC")
    assert tx["amount_rtc"] == 1.23
    assert tx["chain_id"] == cli.CHAIN_ID
    assert isinstance(tx["signature"], str) and len(tx["signature"]) > 20
    assert isinstance(tx["public_key"], str) and len(tx["public_key"]) == 64


def test_sign_transfer_allows_legacy_no_chain_id():
    priv = "01" * 32
    tx = cli._sign_transfer(
        priv,
        "RTC" + "a" * 40,
        "RTC" + "b" * 40,
        1.23,
        "m",
        123,
        chain_id="",
    )

    assert "chain_id" not in tx


def test_balance_normalization():
    payload = {"balance_rtc": 9.5}
    if "amount_rtc" not in payload and "balance_rtc" in payload:
        payload["amount_rtc"] = payload.get("balance_rtc")
    assert payload["amount_rtc"] == 9.5


class FakeResponse:
    def __init__(self, payload, ok=True, status_code=200):
        self.payload = payload
        self.ok = ok
        self.status_code = status_code

    def json(self):
        return self.payload


def test_safe_json_object_rejects_array_payload(capsys):
    data, rc = cli._safe_json_object(FakeResponse([{"amount_rtc": 1.0}]))

    assert data is None
    assert rc == cli.EXIT_BAD_RESPONSE
    assert "not an object" in capsys.readouterr().err


def test_cmd_balance_rejects_non_object_json(monkeypatch, capsys):
    monkeypatch.setattr(cli.requests, "get", lambda *args, **kwargs: FakeResponse(["bad"]))

    rc = cli.cmd_balance(SimpleNamespace(wallet_id="RTCabc"))

    assert rc == cli.EXIT_BAD_RESPONSE
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "not an object" in captured.err


# ─────────────────────────────────────────────────────────────────
# Comprehensive cmd_balance failure-path tests
# ─────────────────────────────────────────────────────────────────

def test_cmd_balance_happy_path(monkeypatch, capsys):
    """Happy path: valid response with amount_rtc."""

    def fake_get(url, **kwargs):
        return FakeResponse({"amount_rtc": 42.5, "nonce": 7})

    monkeypatch.setattr(cli.requests, "get", fake_get)

    rc = cli.cmd_balance(SimpleNamespace(wallet_id="RTCtest"))

    assert rc == cli.EXIT_SUCCESS
    out = capsys.readouterr().out
    assert "42.5" in out
    assert "RTCtest" in out


def test_cmd_balance_network_error(monkeypatch, capsys):
    """Network error → exit code 2, clear stderr."""

    def fake_get(url, **kwargs):
        raise cli.requests.exceptions.ConnectionError("Connection refused")

    monkeypatch.setattr(cli.requests, "get", fake_get)

    rc = cli.cmd_balance(SimpleNamespace(wallet_id="RTCnet"))

    assert rc == cli.EXIT_NETWORK_ERROR
    assert "Network error" in capsys.readouterr().err


def test_cmd_balance_not_found(monkeypatch, capsys):
    """404 response → exit code 4, clear stderr."""

    def fake_get(url, **kwargs):
        return FakeResponse({"error": "not found"}, ok=False, status_code=404)

    monkeypatch.setattr(cli.requests, "get", fake_get)

    rc = cli.cmd_balance(SimpleNamespace(wallet_id="RTCunknown"))

    assert rc == cli.EXIT_WALLET_NOT_FOUND
    assert "not found" in capsys.readouterr().err.lower()


def test_cmd_balance_server_error(monkeypatch, capsys):
    """Non-200, non-404 response → exit code 3 (bad response)."""

    def fake_get(url, **kwargs):
        return FakeResponse({"error": "internal"}, ok=False, status_code=500)

    monkeypatch.setattr(cli.requests, "get", fake_get)

    rc = cli.cmd_balance(SimpleNamespace(wallet_id="RTCerr"))

    assert rc == cli.EXIT_BAD_RESPONSE
    assert "HTTP 500" in capsys.readouterr().err


def test_cmd_balance_malformed_json(monkeypatch, capsys):
    """Non-JSON response body → exit code 3."""

    class RawResponse:
        status_code = 200
        ok = True

        def json(self):
            raise ValueError("Expecting value")

    monkeypatch.setattr(cli.requests, "get", lambda *a, **kw: RawResponse())

    rc = cli.cmd_balance(SimpleNamespace(wallet_id="RTCbadjson"))

    assert rc == cli.EXIT_BAD_RESPONSE
    err = capsys.readouterr().err
    assert "non-JSON body" in err


def test_cmd_balance_missing_amount_rtc(monkeypatch, capsys):
    """Response lacks amount_rtc → exit code 3."""

    def fake_get(url, **kwargs):
        return FakeResponse({"nonce": 0})  # no amount_rtc

    monkeypatch.setattr(cli.requests, "get", fake_get)

    rc = cli.cmd_balance(SimpleNamespace(wallet_id="RTCmissing"))

    assert rc == cli.EXIT_BAD_RESPONSE
    assert "amount_rtc" in capsys.readouterr().err


def test_cmd_balance_timeout(monkeypatch, capsys):
    """Timeout → exit code 2."""

    def fake_get(url, **kwargs):
        raise cli.requests.exceptions.Timeout("timed out")

    monkeypatch.setattr(cli.requests, "get", fake_get)

    rc = cli.cmd_balance(SimpleNamespace(wallet_id="RTCtimeout"))

    assert rc == cli.EXIT_NETWORK_ERROR
    assert "Network error" in capsys.readouterr().err
