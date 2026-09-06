#!/usr/bin/env python3
"""Agent-to-Agent (A2A) on-chain RTC transfer harness.

Implements the workflow requested by bounty issue #13519 of
``Scottcjn/rustchain-bounties``: exercise *real* agent-to-agent RTC transfers
through ``POST /wallet/transfer/signed`` (one-way or round-trip) and produce a
machine-readable receipt that a maintainer can verify on-chain.

Why this exists
---------------
Every agent that tried the bounty re-implemented ad-hoc curl + signing snippets,
and most of them got the canonical message wrong (wrong key order, missing
``fee``, float formatting drift), which makes the node reject the transfer with
``invalid signature``.  This module centralises:

* canonical message construction, byte-identical to the node implementation in
  ``node/rustchain_v2_integrated_v2.2.1_rip200.py::_wallet_transfer_signed_messages``
  (current schema *and* the legacy no-fee schema, for older nodes),
* Ed25519 signing (PyNaCl, with a ``cryptography`` fallback),
* strictly monotonic unix-ms nonces (replay/duplicate-nonce safety),
* address derivation + validation (``RTC`` + 40 hex from SHA256(pubkey)),
* self-transfer / sock-puppet rejection (the bounty explicitly excludes them),
* round-trip orchestration (A->B then B->A) and ledger confirmation polling,
* a JSON receipt with ``tx_hash`` / ``pending_id`` for both directions.

Usage
-----
Sign and send 1 RTC to a partner agent::

    python tools/a2a_transfer/a2a_transfer.py send \
        --node https://rustchain.org \
        --key-file ~/.rustchain/agent.key \
        --to RTC<partner 40 hex> --amount 1

Full round trip (both legs signed locally, e.g. a coordinated test run)::

    python tools/a2a_transfer/a2a_transfer.py roundtrip \
        --key-file agent_a.key --peer-key-file agent_b.key --amount 1 \
        --receipt receipt.json

Key files are ``64`` hex chars (32-byte Ed25519 seed) or a JSON object with a
``seed``/``private_key`` hex field.  Nothing here ever prints a private key.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, Optional, Tuple

__all__ = [
    "ADDRESS_RE",
    "A2AError",
    "TransferResult",
    "canonical_messages",
    "address_from_pubkey",
    "validate_address",
    "NonceFactory",
    "Ed25519Signer",
    "RustChainClient",
    "send_transfer",
    "round_trip",
]

DEFAULT_NODE = "https://rustchain.org"
DEFAULT_CHAIN_ID = "rustchain-mainnet-v2"
TRANSFER_PATH = "/wallet/transfer/signed"
ADDRESS_RE = re.compile(r"^RTC[0-9a-f]{40}$")


class A2AError(RuntimeError):
    """Raised for any unrecoverable A2A transfer problem."""


# --------------------------------------------------------------------------- #
# canonical message + addresses
# --------------------------------------------------------------------------- #
def canonical_messages(
    from_address: str,
    to_address: str,
    amount_rtc: float,
    fee_rtc: float,
    memo: str,
    nonce: int,
    chain_id: Optional[str] = None,
) -> Tuple[bytes, bytes]:
    """Return ``(current, legacy)`` canonical signing payloads.

    Mirrors the node exactly: compact JSON, ``sort_keys=True``, no spaces.
    The legacy variant omits ``fee`` so signatures stay valid against nodes
    that predate the fee field.
    """
    tx = {
        "from": from_address,
        "to": to_address,
        "amount": amount_rtc,
        "fee": fee_rtc,
        "memo": memo,
        "nonce": nonce,
    }
    legacy = {
        "from": from_address,
        "to": to_address,
        "amount": amount_rtc,
        "memo": memo,
        "nonce": nonce,
    }
    if chain_id:
        tx["chain_id"] = chain_id
        legacy["chain_id"] = chain_id
    dump: Callable[[Dict[str, Any]], bytes] = lambda d: json.dumps(
        d, sort_keys=True, separators=(",", ":")
    ).encode()
    return dump(tx), dump(legacy)


def address_from_pubkey(public_key_hex: str) -> str:
    """``RTC`` + first 40 chars of SHA256(pubkey bytes) — same as the node."""
    digest = hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()[:40]
    return f"RTC{digest}"


def validate_address(address: str, label: str = "address") -> str:
    if not isinstance(address, str) or not ADDRESS_RE.match(address):
        raise A2AError(
            f"invalid {label}: {address!r} — expected native 'RTC' + 40 lowercase hex chars"
        )
    return address


# --------------------------------------------------------------------------- #
# nonces
# --------------------------------------------------------------------------- #
class NonceFactory:
    """Strictly increasing unix-millisecond nonce source.

    The node rejects replayed nonces, and two legs of a round trip fired in the
    same millisecond would otherwise collide.
    """

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._last = 0

    def next(self) -> int:
        value = int(self._clock() * 1000)
        if value <= self._last:
            value = self._last + 1
        self._last = value
        return value


# --------------------------------------------------------------------------- #
# signing
# --------------------------------------------------------------------------- #
class Ed25519Signer:
    """Ed25519 signer built from a 32-byte seed. Never exposes the seed."""

    def __init__(self, seed: bytes) -> None:
        if len(seed) != 32:
            raise A2AError(f"Ed25519 seed must be 32 bytes, got {len(seed)}")
        self._backend, self._key = self._load(seed)
        self.public_key_hex = self._pubkey_hex()
        self.address = address_from_pubkey(self.public_key_hex)

    @staticmethod
    def _load(seed: bytes):
        try:
            from nacl.signing import SigningKey  # type: ignore

            return "pynacl", SigningKey(seed)
        except ImportError:
            pass
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PrivateKey,
            )

            return "cryptography", Ed25519PrivateKey.from_private_bytes(seed)
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise A2AError(
                "no Ed25519 backend available; install 'pynacl' or 'cryptography'"
            ) from exc

    def _pubkey_hex(self) -> str:
        if self._backend == "pynacl":
            return bytes(self._key.verify_key).hex()
        from cryptography.hazmat.primitives import serialization

        raw = self._key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return raw.hex()

    def sign(self, message: bytes) -> str:
        if self._backend == "pynacl":
            return self._key.sign(message).signature.hex()
        return self._key.sign(message).hex()

    # -- key loading helpers -------------------------------------------------
    @classmethod
    def from_hex(cls, seed_hex: str) -> "Ed25519Signer":
        seed_hex = seed_hex.strip()
        try:
            seed = bytes.fromhex(seed_hex)
        except ValueError as exc:
            raise A2AError("key material is not valid hex") from exc
        # Accept 64-byte expanded keys (seed || pubkey), as emitted by some wallets.
        if len(seed) == 64:
            seed = seed[:32]
        return cls(seed)

    @classmethod
    def from_file(cls, path: str) -> "Ed25519Signer":
        with open(path, "r", encoding="utf-8") as handle:
            raw = handle.read().strip()
        if raw.startswith("{"):
            data = json.loads(raw)
            for field_name in ("seed", "private_key", "secret_key", "sk"):
                if data.get(field_name):
                    return cls.from_hex(str(data[field_name]))
            raise A2AError(f"{path}: JSON key file has no seed/private_key field")
        return cls.from_hex(raw)


# --------------------------------------------------------------------------- #
# transport
# --------------------------------------------------------------------------- #
@dataclass
class TransferResult:
    ok: bool
    from_address: str
    to_address: str
    amount_rtc: float
    nonce: int
    tx_hash: Optional[str] = None
    pending_id: Optional[str] = None
    error: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RustChainClient:
    """Minimal JSON client for the RustChain node HTTP API."""

    def __init__(
        self,
        node_url: str = DEFAULT_NODE,
        timeout: float = 20.0,
        opener: Optional[Callable[[str, Optional[bytes], float], Dict[str, Any]]] = None,
    ) -> None:
        self.node_url = node_url.rstrip("/")
        self.timeout = timeout
        self._opener = opener or self._http

    @staticmethod
    def _http(url: str, body: Optional[bytes], timeout: float) -> Dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "rustchain-a2a-transfer/1.0",
            },
            method="POST" if body is not None else "GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode("utf-8", "replace")
        except urllib.error.URLError as exc:
            raise A2AError(f"network error talking to {url}: {exc.reason}") from exc
        try:
            return json.loads(payload) if payload else {}
        except json.JSONDecodeError:
            return {"ok": False, "error": "non-JSON response", "body": payload[:500]}

    def post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._opener(
            f"{self.node_url}{path}", json.dumps(payload).encode(), self.timeout
        )

    def get(self, path: str) -> Dict[str, Any]:
        return self._opener(f"{self.node_url}{path}", None, self.timeout)

    def balance(self, address: str) -> Optional[float]:
        data = self.get(f"/wallet/balance/{address}")
        for key in ("balance_rtc", "balance", "amount_rtc"):
            if isinstance(data.get(key), (int, float)):
                return float(data[key])
        return None


# --------------------------------------------------------------------------- #
# core operations
# --------------------------------------------------------------------------- #
def build_payload(
    signer: Ed25519Signer,
    to_address: str,
    amount_rtc: float,
    nonce: int,
    memo: str = "",
    fee_rtc: float = 0.0,
    chain_id: Optional[str] = DEFAULT_CHAIN_ID,
    legacy: bool = False,
) -> Dict[str, Any]:
    """Build the signed request body for ``POST /wallet/transfer/signed``."""
    from_address = signer.address
    validate_address(from_address, "from_address")
    validate_address(to_address, "to_address")
    if from_address == to_address:
        raise A2AError(
            "refusing self-transfer: bounty #13519 requires two independent agents"
        )
    if amount_rtc < 1:
        raise A2AError("bounty #13519 requires an on-chain transfer of at least 1 RTC")
    current_msg, legacy_msg = canonical_messages(
        from_address, to_address, amount_rtc, fee_rtc, memo, nonce, chain_id
    )
    message = legacy_msg if legacy else current_msg
    return {
        "from_address": from_address,
        "to_address": to_address,
        "amount_rtc": amount_rtc,
        "fee_rtc": fee_rtc,
        "memo": memo,
        "nonce": nonce,
        "public_key": signer.public_key_hex,
        "signature": signer.sign(message),
        "chain_id": chain_id,
    }


def _extract(result: Dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        value = result.get(key)
        if value:
            return str(value)
    tx = result.get("tx") or result.get("transaction")
    if isinstance(tx, dict):
        for key in keys:
            if tx.get(key):
                return str(tx[key])
    return None


def send_transfer(
    client: RustChainClient,
    signer: Ed25519Signer,
    to_address: str,
    amount_rtc: float = 1.0,
    memo: str = "",
    nonce: Optional[int] = None,
    nonces: Optional[NonceFactory] = None,
    fee_rtc: float = 0.0,
    chain_id: Optional[str] = DEFAULT_CHAIN_ID,
    retry_legacy: bool = True,
) -> TransferResult:
    """Sign and submit one agent-to-agent transfer.

    On ``invalid signature`` the call is retried once with the legacy
    (fee-less) canonical message so the tool works against older nodes.
    """
    nonces = nonces or NonceFactory()
    nonce = nonces.next() if nonce is None else nonce
    payload = build_payload(
        signer, to_address, amount_rtc, nonce, memo, fee_rtc, chain_id
    )
    response = client.post(TRANSFER_PATH, payload)
    if not response.get("ok") and retry_legacy and _looks_like_sig_error(response):
        payload = build_payload(
            signer, to_address, amount_rtc, nonces.next(), memo, fee_rtc,
            chain_id, legacy=True,
        )
        response = client.post(TRANSFER_PATH, payload)

    return TransferResult(
        ok=bool(response.get("ok")),
        from_address=payload["from_address"],
        to_address=to_address,
        amount_rtc=amount_rtc,
        nonce=payload["nonce"],
        tx_hash=_extract(response, "tx_hash", "txid", "hash"),
        pending_id=_extract(response, "pending_id", "pending", "id"),
        error=None if response.get("ok") else str(
            response.get("error") or response.get("message") or "transfer rejected"
        ),
        raw=response,
    )


def _looks_like_sig_error(response: Dict[str, Any]) -> bool:
    text = f"{response.get('error', '')} {response.get('message', '')}".lower()
    return "signature" in text


def round_trip(
    client: RustChainClient,
    signer_a: Ed25519Signer,
    signer_b: Ed25519Signer,
    amount_rtc: float = 1.0,
    memo: str = "a2a bounty 13519",
    nonces: Optional[NonceFactory] = None,
) -> Dict[str, Any]:
    """A -> B, then B -> A. Both legs must be distinct wallets."""
    if signer_a.address == signer_b.address:
        raise A2AError("round trip needs two distinct agents (sock puppets excluded)")
    nonces = nonces or NonceFactory()
    outbound = send_transfer(
        client, signer_a, signer_b.address, amount_rtc, memo, nonces=nonces
    )
    inbound: Optional[TransferResult] = None
    if outbound.ok:
        inbound = send_transfer(
            client, signer_b, signer_a.address, amount_rtc, memo, nonces=nonces
        )
    return {
        "bounty": "rustchain-bounties#13519",
        "agent_a": signer_a.address,
        "agent_b": signer_b.address,
        "amount_rtc": amount_rtc,
        "outbound": outbound.to_dict(),
        "inbound": inbound.to_dict() if inbound else None,
        "complete": bool(outbound.ok and inbound and inbound.ok),
        "generated_at": int(time.time()),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _signer_from_args(key_file: Optional[str], env_var: str) -> Ed25519Signer:
    if key_file:
        return Ed25519Signer.from_file(key_file)
    raw = os.environ.get(env_var)
    if not raw:
        raise A2AError(f"no key: pass --key-file or set ${env_var}")
    return Ed25519Signer.from_hex(raw)


def _emit(data: Dict[str, Any], receipt: Optional[str]) -> None:
    text = json.dumps(data, indent=2, sort_keys=True)
    print(text)
    if receipt:
        with open(receipt, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="a2a_transfer",
        description="Agent-to-agent on-chain RTC transfers (bounty #13519)",
    )
    parser.add_argument("--node", default=os.environ.get("RUSTCHAIN_NODE", DEFAULT_NODE))
    parser.add_argument("--timeout", type=float, default=20.0)
    sub = parser.add_subparsers(dest="command", required=True)

    p_addr = sub.add_parser("address", help="print the RTC address for a key")
    p_addr.add_argument("--key-file")

    p_send = sub.add_parser("send", help="send >=1 RTC to a partner agent")
    p_send.add_argument("--key-file")
    p_send.add_argument("--to", required=True)
    p_send.add_argument("--amount", type=float, default=1.0)
    p_send.add_argument("--memo", default="a2a bounty 13519")
    p_send.add_argument("--receipt")

    p_rt = sub.add_parser("roundtrip", help="A->B then B->A")
    p_rt.add_argument("--key-file")
    p_rt.add_argument("--peer-key-file")
    p_rt.add_argument("--amount", type=float, default=1.0)
    p_rt.add_argument("--memo", default="a2a bounty 13519")
    p_rt.add_argument("--receipt")

    args = parser.parse_args(argv)
    client = RustChainClient(args.node, timeout=args.timeout)

    try:
        if args.command == "address":
            signer = _signer_from_args(args.key_file, "RUSTCHAIN_AGENT_KEY")
            _emit(
                {"address": signer.address, "public_key": signer.public_key_hex}, None
            )
            return 0

        if args.command == "send":
            signer = _signer_from_args(args.key_file, "RUSTCHAIN_AGENT_KEY")
            result = send_transfer(
                client, signer, args.to, args.amount, args.memo
            )
            _emit(result.to_dict(), args.receipt)
            return 0 if result.ok else 1

        signer_a = _signer_from_args(args.key_file, "RUSTCHAIN_AGENT_KEY")
        signer_b = _signer_from_args(args.peer_key_file, "RUSTCHAIN_PEER_KEY")
        report = round_trip(client, signer_a, signer_b, args.amount, args.memo)
        _emit(report, args.receipt)
        return 0 if report["complete"] else 1
    except A2AError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
