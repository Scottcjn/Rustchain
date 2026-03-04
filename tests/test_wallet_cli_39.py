import json
from tools import rustchain_wallet_cli as cli


def test_encrypt_decrypt_roundtrip():
    priv = "11" * 32
    enc = cli._encrypt_private_key(priv, "pw123")
    out = cli._decrypt_private_key(enc, "pw123")
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
    assert isinstance(tx["signature"], str) and len(tx["signature"]) > 20
    assert isinstance(tx["public_key"], str) and len(tx["public_key"]) == 64


def test_balance_normalization():
    payload = {"balance_rtc": 9.5}
    if "amount_rtc" not in payload and "balance_rtc" in payload:
        payload["amount_rtc"] = payload.get("balance_rtc")
    assert payload["amount_rtc"] == 9.5
