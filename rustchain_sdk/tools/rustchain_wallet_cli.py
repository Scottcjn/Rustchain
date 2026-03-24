#!/usr/bin/env python3
"""RustChain Wallet CLI (draft for bounty #39).

Commands:
  rustchain-wallet create
  rustchain-wallet import <mnemonic>
  rustchain-wallet export <wallet_name>
  rustchain-wallet balance <wallet_address>
  rustchain-wallet send <to> <amount> --from <wallet_name>
  rustchain-wallet history <wallet_address>
  rustchain-wallet miners
  rustchain-wallet epoch
"""

from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from pathlib import Path
from typing import Tuple

import requests
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

try:
    from mnemonic import Mnemonic
except Exception:  # pragma: no cover
    Mnemonic = None

NODE_URL = os.environ.get("RUSTCHAIN_NODE_URL", "https://rustchain.org")
VERIFY_SSL = os.environ.get("RUSTCHAIN_VERIFY_SSL", "0") in {"1", "true", "True"}
KEYSTORE_DIR = Path.home() / ".rustchain" / "wallets"
KEYSTORE_DIR.mkdir(parents=True, exist_ok=True)


def _derive_ed25519_from_mnemonic(mnemonic_phrase: str, passphrase: str = "") -> Tuple[str, str]:
    """Return (private_key_hex, public_key_hex) derived from BIP39 seed.

    Uses BIP39 seed + SLIP10-style master key extraction for ed25519.
    """
    if Mnemonic is None:
        raise RuntimeError("Missing dependency: mnemonic. Install via `python3 -m pip install mnemonic`.")

    m = Mnemonic("english")
    if not m.check(mnemonic_phrase):
        raise ValueError("Invalid BIP39 mnemonic")

    seed = Mnemonic.to_seed(mnemonic_phrase, passphrase=passphrase)
    i = hmac.new(b"ed25519 seed", seed, hashlib.sha512).digest()
    sk = i[:32]
    priv = Ed25519PrivateKey.from_private_bytes(sk)
    pub = priv.public_key().public_bytes_raw().hex()
    return sk.hex(), pub


def _address_from_pubkey_hex(pub_hex: str) -> str:
    return "RTC" + hashlib.sha256(bytes.fromhex(pub_hex)).hexdigest()[:40]


def _pbkdf2_key(password: str, salt: bytes, iterations: int = 100_000) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations, dklen=32)


def _encrypt_private_key(priv_hex: str, password: str) -> dict:
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    key = _pbkdf2_key(password, salt)
    aes = AESGCM(key)
    ct = aes.encrypt(nonce, bytes.fromhex(priv_hex), None)
    return {
        "cipher": "AES-256-GCM",
        "kdf": "PBKDF2-HMAC-SHA256",
        "kdf_iterations": 100000,
        "salt_b64": base64.b64encode(salt).decode(),
        "nonce_b64": base64.b64encode(nonce).decode(),
        "ciphertext_b64": base64.b64encode(ct).decode(),
    }


def _pick(enc: dict, *names: str):
    for n in names:
        if n in enc and enc[n] not in (None, ""):
            return enc[n]
    return None


def _decrypt_private_key(enc: dict, password: str) -> str:
    """Decrypt keystore payload with compatibility aliases.

    Supports current keys (salt_b64/nonce_b64/ciphertext_b64) and common
    legacy aliases (salt, nonce, ciphertext, encrypted_private_key).
    """
    salt_s = _pick(enc, "salt_b64", "salt")
    nonce_s = _pick(enc, "nonce_b64", "nonce", "iv_b64", "iv")
    ct_s = _pick(enc, "ciphertext_b64", "ciphertext", "encrypted_private_key")
    if not (salt_s and nonce_s and ct_s):
        raise ValueError("Unsupported keystore crypto format")

    salt = base64.b64decode(salt_s)
    nonce = base64.b64decode(nonce_s)
    ct = base64.b64decode(ct_s)

    iterations = int(_pick(enc, "kdf_iterations", "iterations", "pbkdf2_iterations") or 100000)
    key = _pbkdf2_key(password, salt, iterations)
    aes = AESGCM(key)
    pt = aes.decrypt(nonce, ct, None)
    if len(pt) != 32:
        raise ValueError("Invalid private key length")
    return pt.hex()


def _keystore_path(name: str) -> Path:
    safe = "".join(c for c in name if c.isalnum() or c in "-_.")
    if not safe:
        raise ValueError("Invalid wallet name")
    return KEYSTORE_DIR / f"{safe}.json"


def _load_keystore(name: str) -> dict:
    p = _keystore_path(name)
    if not p.exists():
        raise FileNotFoundError(f"Keystore not found: {p}")
    return json.loads(p.read_text())


def _save_keystore(name: str, data: dict) -> Path:
    p = _keystore_path(name)
    p.write_text(json.dumps(data, indent=2))
    return p




def _read_password(prompt: str, env_key: str) -> str:
    env_val = os.environ.get(env_key)
    if env_val:
        return env_val
    return getpass.getpass(prompt)

def _sign_transfer(priv_hex: str, from_addr: str, to_addr: str, amount_rtc: float, memo: str, nonce: int) -> dict:
    tx_data = {
        "from": from_addr,
        "to": to_addr,
        "amount": amount_rtc,
        "memo": memo,
        "nonce": str(nonce),
    }
    message = json.dumps(tx_data, sort_keys=True, separators=(",", ":")).encode()
    priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(priv_hex))
    sig_hex = priv.sign(message).hex()
    pub_hex = priv.public_key().public_bytes_raw().hex()
    return {
        "from_address": from_addr,
        "to_address": to_addr,
        "amount_rtc": amount_rtc,
        "nonce": nonce,
        "memo": memo,
        "public_key": pub_hex,
        "signature": sig_hex,
    }


def cmd_create(args):
    if Mnemonic is None:
        print("Error: missing dependency 'mnemonic'. Install: python3 -m pip install mnemonic", file=sys.stderr)
        return 2

    wallet_name = args.name or f"wallet-{int(time.time())}"
    password = _read_password("Set wallet password: ", "RUSTCHAIN_WALLET_PASSWORD")
    confirm = _read_password("Confirm password: ", "RUSTCHAIN_WALLET_PASSWORD_CONFIRM")
    if password != confirm:
        print("Error: password mismatch", file=sys.stderr)
        return 2

    m = Mnemonic("english")
    phrase = m.generate(strength=256)  # 24 words
    priv_hex, pub_hex = _derive_ed25519_from_mnemonic(phrase)
    address = _address_from_pubkey_hex(pub_hex)

    ks = {
        "version": 1,
        "name": wallet_name,
        "address": address,
        "public_key_hex": pub_hex,
        "mnemonic_words": 24,
        "crypto": _encrypt_private_key(priv_hex, password),
        "created_at": int(time.time()),
    }
    path = _save_keystore(wallet_name, ks)

    print(f"Wallet created: {wallet_name}")
    print(f"Address: {address}")
    print(f"Keystore: {path}")
    print("Seed phrase (write this down safely):")
    print(phrase)
    return 0


def cmd_import(args):
    if Mnemonic is None:
        print("Error: missing dependency 'mnemonic'. Install: python3 -m pip install mnemonic", file=sys.stderr)
        return 2

    phrase = args.mnemonic.strip().lower()
    wallet_name = args.name or f"imported-{int(time.time())}"
    password = _read_password("Set wallet password: ", "RUSTCHAIN_WALLET_PASSWORD")
    confirm = _read_password("Confirm password: ", "RUSTCHAIN_WALLET_PASSWORD_CONFIRM")
    if password != confirm:
        print("Error: password mismatch", file=sys.stderr)
        return 2

    priv_hex, pub_hex = _derive_ed25519_from_mnemonic(phrase)
    address = _address_from_pubkey_hex(pub_hex)
    ks = {
        "version": 1,
        "name": wallet_name,
        "address": address,
        "public_key_hex": pub_hex,
        "mnemonic_words": 24,
        "crypto": _encrypt_private_key(priv_hex, password),
        "created_at": int(time.time()),
    }
    path = _save_keystore(wallet_name, ks)
    print(f"Wallet imported: {wallet_name}")
    print(f"Address: {address}")
    print(f"Keystore: {path}")
    return 0


def cmd_export(args):
    ks = _load_keystore(args.wallet)
    print(json.dumps(ks, indent=2))
    return 0


def _safe_json(r: "requests.Response") -> "tuple[dict | list | None, int]":
    """Parse JSON from a response, returning (data, exit_code).

    Returns (None, 1) with a descriptive error printed to stderr when the
    response body is not valid JSON (e.g. HTML 502 error pages).  This avoids
    the opaque ``JSONDecodeError`` that previously surfaced to callers.
    """
    try:
        return r.json(), 0 if r.ok else 1
    except Exception:
        print(
            f"Error: Server returned HTTP {r.status_code} with non-JSON body"
            f" (check node URL / connectivity)",
            file=sys.stderr,
        )
        return None, 1


def cmd_balance(args):
    url = f"{NODE_URL}/wallet/balance"
    r = requests.get(url, params={"miner_id": args.wallet_id}, timeout=12, verify=VERIFY_SSL)
    data, rc = _safe_json(r)
    if data is None:
        return rc
    if isinstance(data, dict):
        if "amount_rtc" not in data and "balance_rtc" in data:
            data["amount_rtc"] = data.get("balance_rtc")
        data["wallet_id"] = args.wallet_id
    print(json.dumps(data, indent=2))
    return rc


def cmd_send(args):
    ks = _load_keystore(args.from_wallet)
    password = _read_password("Wallet password: ", "RUSTCHAIN_WALLET_PASSWORD")
    priv_hex = _decrypt_private_key(ks["crypto"], password)
    from_addr = ks["address"]
    nonce = int(time.time())
    payload = _sign_transfer(priv_hex, from_addr, args.to, float(args.amount), args.memo or "", nonce)

    url = f"{NODE_URL}/wallet/transfer/signed"
    r = requests.post(url, json=payload, timeout=20, verify=VERIFY_SSL)
    data, rc = _safe_json(r)
    if data is not None:
        print(json.dumps(data, indent=2))
    return rc


def cmd_history(args):
    url = f"{NODE_URL}/wallet/ledger"
    r = requests.get(url, params={"miner_id": args.wallet_id}, timeout=12, verify=VERIFY_SSL)
    data, rc = _safe_json(r)
    if data is None:
        return rc
    if isinstance(data, list):
        data = {"wallet_id": args.wallet_id, "transactions": data}
    print(json.dumps(data, indent=2))
    return rc


def cmd_miners(args):
    r = requests.get(f"{NODE_URL}/api/miners", timeout=12, verify=VERIFY_SSL)
    data, rc = _safe_json(r)
    if data is not None:
        print(json.dumps(data, indent=2))
    return rc


def cmd_epoch(args):
    r = requests.get(f"{NODE_URL}/epoch", timeout=12, verify=VERIFY_SSL)
    data, rc = _safe_json(r)
    if data is not None:
        print(json.dumps(data, indent=2))
    return rc


def build_parser():
    p = argparse.ArgumentParser(prog="rustchain-wallet", description="RustChain Wallet CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create", help="Generate new wallet (24-word mnemonic + encrypted keystore)")
    p_create.add_argument("--name", help="Wallet name (default: wallet-<timestamp>)")
    p_create.set_defaults(func=cmd_create)

    p_import = sub.add_parser("import", help="Import wallet from 24-word mnemonic")
    p_import.add_argument("mnemonic", help="Quoted 24-word seed phrase")
    p_import.add_argument("--name", help="Wallet name")
    p_import.set_defaults(func=cmd_import)

    p_export = sub.add_parser("export", help="Export encrypted keystore JSON")
    p_export.add_argument("wallet", help="Wallet name")
    p_export.set_defaults(func=cmd_export)

    p_balance = sub.add_parser("balance", help="Check wallet balance")
    p_balance.add_argument("wallet_id", help="RTC wallet address")
    p_balance.set_defaults(func=cmd_balance)

    p_send = sub.add_parser("send", help="Send signed transfer")
    p_send.add_argument("to", help="Recipient RTC address")
    p_send.add_argument("amount", type=float, help="Amount in RTC")
    p_send.add_argument("--from", dest="from_wallet", required=True, help="Local keystore wallet name")
    p_send.add_argument("--memo", default="", help="Optional memo")
    p_send.set_defaults(func=cmd_send)

    p_hist = sub.add_parser("history", help="Wallet transaction history")
    p_hist.add_argument("wallet_id", help="RTC wallet address")
    p_hist.set_defaults(func=cmd_history)

    p_miners = sub.add_parser("miners", help="List active miners")
    p_miners.set_defaults(func=cmd_miners)

    p_epoch = sub.add_parser("epoch", help="Show current epoch")
    p_epoch.set_defaults(func=cmd_epoch)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
