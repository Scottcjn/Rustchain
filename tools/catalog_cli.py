#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Sell and buy agent services on the RustChain service catalog.

A small client for the node's ``/catalog`` API (node/service_catalog.py, see
docs/SERVICE_CATALOG.md). One Beacon identity both signs catalog requests and
pays for work, so RTC an agent earns can be spent on another agent's work::

    python tools/catalog_cli.py list --category review
    python tools/catalog_cli.py offer --title "Review one repo" --category review \\
        --price-rtc 2 --unit "per repo" --turnaround-hours 48
    python tools/catalog_cli.py order lst_0123456789abcdef --note "repo: ..."
    python tools/catalog_cli.py deliver ord_0123456789abcdef --file review.md
    python tools/catalog_cli.py accept ord_0123456789abcdef
    python tools/catalog_cli.py pay ord_0123456789abcdef          # dry run
    python tools/catalog_cli.py pay ord_0123456789abcdef --send   # really pays

The catalog holds no funds, moves no RTC and takes no fee. ``pay`` is the only
command that moves RTC: it signs a transfer from the buyer's own wallet to the
provider with memo ``svc:<order_id>``, through ``POST /wallet/transfer/signed``.
It is a dry run unless ``--send`` is given.

Identity: the Beacon agent key file written by ``beacon identity new``
(``~/.beacon/identity/agent.key``, or ``$BEACON_IDENTITY_PATH``, or
``--identity``). Encrypted key files read their password from
``$BEACON_IDENTITY_PASSWORD`` or a prompt. The agent must be registered in the
Beacon Atlas; the catalog refuses unregistered ids. Private keys are never
printed.

Dependencies: Python 3.9+ standard library and ``cryptography``. Payment
signing reuses wallet/rustchain_signed_transfer.py (chain-bound, the same
builder the secure wallet uses); this file contains no transfer signer.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import importlib.util
import json
import os
import secrets
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import ROUND_DOWN, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NODE = "https://rustchain.org"
DEFAULT_IDENTITY = Path.home() / ".beacon" / "identity" / "agent.key"
UNIT = 1_000_000  # uRTC per RTC, as in the node ledger
CATEGORIES = ("render", "review", "hw_test", "vision", "compute",
              "docs", "translation", "testing", "other")
PAYMENT_ENDPOINT = "/wallet/transfer/signed"
# Beacon keystore KDF (beacon_skill.identity.PBKDF2_ITERATIONS).
_BEACON_PBKDF2_ITERATIONS = 600_000


def _load_signed_transfer_module():
    """wallet/rustchain_signed_transfer.py: the repo's chain-bound transfer builder."""
    path = ROOT / "wallet" / "rustchain_signed_transfer.py"
    spec = importlib.util.spec_from_file_location("rustchain_signed_transfer", path)
    if spec is None or spec.loader is None:  # pragma: no cover - broken checkout
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


signed_transfer = _load_signed_transfer_module()


class CatalogError(Exception):
    """A refused request (HTTP error from the node, or a local safety check)."""

    def __init__(self, message: str, status: Optional[int] = None,
                 payload: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status = status
        self.payload = payload or {}


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

class AgentKey:
    """A Beacon Ed25519 identity.

    Signs catalog requests as ``bcn_<12 hex>`` and exposes the wallet API that
    ``rustchain_signed_transfer.build_signed_transfer`` expects (``address``,
    ``public_key``, ``sign_message``).
    """

    def __init__(self, private_key: Ed25519PrivateKey):
        self._key = private_key
        pub = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.public_key = pub.hex()
        self.agent_id = "bcn_" + hashlib.sha256(pub).hexdigest()[:12]
        self.rtc_address = "RTC" + hashlib.sha256(pub).hexdigest()[:40]

    @classmethod
    def from_seed_hex(cls, seed_hex: str) -> "AgentKey":
        seed = bytes.fromhex(seed_hex.strip().removeprefix("0x"))
        if len(seed) != 32:
            raise ValueError("Ed25519 private key must be 32 bytes (64 hex chars)")
        return cls(Ed25519PrivateKey.from_private_bytes(seed))

    @classmethod
    def load(cls, path: Optional[str] = None, password: Optional[str] = None) -> "AgentKey":
        """Load a Beacon ``agent.key`` (plain or encrypted JSON) or a raw 64-hex seed file."""
        key_path = Path(path or os.environ.get("BEACON_IDENTITY_PATH") or DEFAULT_IDENTITY)
        key_path = key_path.expanduser()
        if not key_path.exists():
            raise CatalogError(
                f"no Beacon identity at {key_path}; create one with "
                "`beacon identity new` and register it in the Beacon Atlas, "
                "or pass --identity")
        text = key_path.read_text(encoding="utf-8").strip()
        if not text.startswith("{"):
            return cls.from_seed_hex(text)
        data = json.loads(text)
        if data.get("encrypted"):
            if password is None:
                password = os.environ.get("BEACON_IDENTITY_PASSWORD")
            if password is None:
                password = getpass.getpass(f"Password for {key_path}: ")
            agent = cls(Ed25519PrivateKey.from_private_bytes(_decrypt_beacon_seed(data, password)))
        else:
            seed_hex = data.get("private_key_hex") or data.get("private_key") or data.get("seed")
            if not isinstance(seed_hex, str):
                raise CatalogError(f"{key_path} has no private_key_hex")
            agent = cls.from_seed_hex(seed_hex)
        stated = data.get("agent_id")
        if stated and stated != agent.agent_id:
            raise CatalogError(f"{key_path}: agent_id {stated} does not match its key")
        return agent

    def sign_message(self, message: bytes) -> str:
        return self._key.sign(message).hex()

    def payer(self, pay_from: str) -> "_Payer":
        """The wallet this identity pays from: its bcn_ id or its derived RTC address."""
        if pay_from == "bcn":
            return _Payer(self.agent_id, self.public_key, self.sign_message)
        if pay_from == "rtc":
            return _Payer(self.rtc_address, self.public_key, self.sign_message)
        raise ValueError("pay_from must be 'bcn' or 'rtc'")


class _Payer:
    """Wallet adapter for build_signed_transfer (address, public_key, sign_message)."""

    def __init__(self, address: str, public_key: str, sign: Callable[[bytes], str]):
        self.address = address
        self.public_key = public_key
        self.sign_message = sign


def _decrypt_beacon_seed(data: Dict[str, Any], password: str) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                     salt=bytes.fromhex(data["salt"]),
                     iterations=_BEACON_PBKDF2_ITERATIONS)
    aes_key = kdf.derive(password.encode("utf-8"))
    try:
        return AESGCM(aes_key).decrypt(bytes.fromhex(data["nonce"]),
                                       bytes.fromhex(data["ciphertext"]), None)
    except Exception:
        raise CatalogError("wrong password or corrupted Beacon keystore") from None


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

Transport = Callable[[str, str, bytes, Dict[str, str]], Tuple[int, Any]]


def urllib_transport(node: str, insecure: bool = False, timeout: float = 30.0) -> Transport:
    """HTTP(S) transport. ``insecure`` skips TLS verification (self-signed node IPs)."""
    base = node.rstrip("/")
    context = None
    if insecure:
        context = ssl.create_default_context()
        context.check_hostname = False
        # Explicit --insecure opt-in only.
        context.verify_mode = ssl.CERT_NONE  # nosec B501

    def send(method: str, path: str, body: bytes, headers: Dict[str, str]) -> Tuple[int, Any]:
        req = urllib.request.Request(base + path, data=body if method != "GET" else None,
                                     headers=headers, method=method)
        try:
            # The URL is the node the user chose (--node / $RUSTCHAIN_NODE).
            with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:  # nosec B310
                status, raw = resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            status, raw = exc.code, exc.read()
        try:
            return status, json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, ValueError):
            return status, {"error": "non-JSON response", "body": raw[:200].decode("utf-8", "replace")}

    return send


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

def _price_value(price_rtc: Any) -> float:
    """Validate an RTC price locally (positive, at most 6 decimals) and return it as a number."""
    try:
        dec = Decimal(str(price_rtc))
    except InvalidOperation:
        raise CatalogError(f"price must be a number of RTC, got {price_rtc!r}") from None
    if not dec.is_finite() or dec <= 0:
        raise CatalogError("price must be a positive number of RTC")
    if (dec * UNIT) != (dec * UNIT).to_integral_value():
        raise CatalogError("price supports at most 6 decimal places")
    return float(dec)


def _micro_rtc(amount: float) -> int:
    """How the node quantizes amount_rtc (payout_preflight: Decimal(str(x)) * 1e6, round down)."""
    return int((Decimal(str(amount)) * UNIT).to_integral_value(rounding=ROUND_DOWN))


class CatalogClient:
    """Calls the node's /catalog API, signing writes with a Beacon identity."""

    def __init__(self, transport: Transport, agent: Optional[AgentKey] = None):
        self._send = transport
        self.agent = agent

    # -- plumbing ----------------------------------------------------------

    def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None,
                 params: Optional[Dict[str, Any]] = None, signed: bool = False) -> Any:
        query = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        if query:
            path = f"{path}?{urllib.parse.urlencode(query)}"
        body = b"" if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if signed:
            headers.update(self._auth_headers(method, path, body))
        status, data = self._send(method, path, body, headers)
        if status >= 400:
            message = data.get("error") if isinstance(data, dict) else None
            raise CatalogError(f"{method} {path} -> HTTP {status}: {message or data}",
                               status=status, payload=data if isinstance(data, dict) else {})
        return data

    def _auth_headers(self, method: str, path: str, body: bytes) -> Dict[str, str]:
        """Beacon canonical request signature, as node/service_catalog.py verifies it:
        METHOD\\nPATH(+query)\\nsha256(body)\\ntimestamp\\nnonce\\nagent_id."""
        if self.agent is None:
            raise CatalogError("this command needs a Beacon identity (--identity)")
        timestamp = str(int(time.time()))
        nonce = secrets.token_hex(16)
        message = "\n".join([method.upper(), path, hashlib.sha256(body).hexdigest(),
                             timestamp, nonce, self.agent.agent_id]).encode("utf-8")
        return {
            "X-Agent-Id": self.agent.agent_id,
            "X-Agent-Timestamp": timestamp,
            "X-Agent-Nonce": nonce,
            "X-Agent-Signature": self.agent.sign_message(message),
        }

    # -- browse ------------------------------------------------------------

    def index(self) -> Dict[str, Any]:
        return self._request("GET", "/catalog")

    def listings(self, category: Optional[str] = None, provider: Optional[str] = None,
                 limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        return self._request("GET", "/catalog/listings", params={
            "category": category, "provider": provider, "limit": limit, "offset": offset})

    def listing(self, listing_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/catalog/listings/{_safe_id(listing_id)}")

    def provider(self, agent_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/catalog/providers/{_safe_id(agent_id)}")

    # -- provider ----------------------------------------------------------

    def offer(self, title: str, category: str, price_rtc: Any, description: str = "",
              unit: str = "per job", turnaround_hours: Optional[int] = None) -> Dict[str, Any]:
        if category not in CATEGORIES:
            raise CatalogError(f"category must be one of: {', '.join(CATEGORIES)}")
        payload: Dict[str, Any] = {"title": title, "description": description,
                                   "category": category, "price_rtc": _price_value(price_rtc),
                                   "unit": unit}
        if turnaround_hours is not None:
            payload["turnaround_hours"] = int(turnaround_hours)
        return self._request("POST", "/catalog/listings", payload, signed=True)

    def set_listing_status(self, listing_id: str, status: str) -> Dict[str, Any]:
        return self._request("POST", f"/catalog/listings/{_safe_id(listing_id)}/status",
                             {"status": status}, signed=True)

    def deliver(self, order_id: str, deliverable_hash: str,
                deliverable_uri: Optional[str] = None) -> Dict[str, Any]:
        payload = {"deliverable_hash": deliverable_hash.strip().lower()}
        if deliverable_uri:
            payload["deliverable_uri"] = deliverable_uri
        return self._request("POST", f"/catalog/orders/{_safe_id(order_id)}/deliver",
                             payload, signed=True)

    # -- buyer -------------------------------------------------------------

    def order(self, listing_id: str, note: str = "") -> Dict[str, Any]:
        payload = {"listing_id": listing_id}
        if note:
            payload["note"] = note
        return self._request("POST", "/catalog/orders", payload, signed=True)

    def accept(self, order_id: str) -> Dict[str, Any]:
        return self._request("POST", f"/catalog/orders/{_safe_id(order_id)}/accept", {},
                             signed=True)

    def reject(self, order_id: str, reason: str) -> Dict[str, Any]:
        return self._request("POST", f"/catalog/orders/{_safe_id(order_id)}/reject",
                             {"reason": reason}, signed=True)

    def cancel(self, order_id: str, reason: str = "") -> Dict[str, Any]:
        payload = {"reason": reason} if reason else {}
        return self._request("POST", f"/catalog/orders/{_safe_id(order_id)}/cancel",
                             payload, signed=True)

    def my_orders(self, role: str = "buyer", status: Optional[str] = None) -> Dict[str, Any]:
        return self._request("GET", "/catalog/orders", params={"role": role, "status": status},
                             signed=True)

    def get_order(self, order_id: str, signed: bool = True) -> Dict[str, Any]:
        return self._request("GET", f"/catalog/orders/{_safe_id(order_id)}", signed=signed)

    # -- payment -----------------------------------------------------------

    def chain_id(self) -> str:
        return signed_transfer.chain_id_from_network_info(self._request("GET", "/network/info"))

    def build_payment(self, order_id: str, pay_from: str = "bcn",
                      nonce: Optional[int] = None) -> Dict[str, Any]:
        """Sign (but do not send) the transfer that pays for an accepted order.

        Checks, before signing: this identity is the order's buyer, the order
        is accepted and not already paid, and the node's payment instructions
        name the order's provider, price and ``svc:<order_id>`` memo. The
        chain_id comes from this node's ``GET /network/info`` and must match
        the one in the instructions.
        """
        if self.agent is None:
            raise CatalogError("paying needs a Beacon identity (--identity)")
        order = self.get_order(order_id, signed=True)
        if order.get("buyer") != self.agent.agent_id:
            raise CatalogError(f"{self.agent.agent_id} is not the buyer of {order_id}")
        if order.get("status") != "accepted":
            raise CatalogError(
                f"order {order_id} is {order.get('status')!r}; pay after delivery, "
                "once you have accepted it (`accept`)")
        payment = order.get("payment")
        if not isinstance(payment, dict) or "state" not in payment:
            # An accepted order always carries its payment state; without it
            # we cannot rule out an earlier payment, so do not sign.
            raise CatalogError(f"order {order_id} has no payment state; not signing")
        state = payment["state"]
        if state in ("pending", "confirmed"):
            raise CatalogError(f"order {order_id} already has a {state} payment "
                               f"(tx {order['payment'].get('tx_hash')}); not paying twice")
        instr = order.get("payment_instructions")
        if not isinstance(instr, dict):
            raise CatalogError(f"order {order_id} has no payment instructions; not signing")
        memo = f"svc:{order['id']}"
        price = float(order["price_rtc"])
        problems = []
        if instr.get("endpoint") != PAYMENT_ENDPOINT:
            problems.append(f"endpoint {instr.get('endpoint')!r}")
        if instr.get("to_address") != order.get("provider"):
            problems.append("to_address is not the order's provider")
        if instr.get("memo") != memo:
            problems.append(f"memo {instr.get('memo')!r} != {memo!r}")
        if instr.get("amount_rtc") != price:
            problems.append(f"amount {instr.get('amount_rtc')!r} != price {price!r}")
        if problems:
            raise CatalogError("payment instructions do not match the order: " + "; ".join(problems))
        if _micro_rtc(price) <= 0:
            raise CatalogError(f"price {price!r} quantizes to zero")

        chain_id = self.chain_id()
        if instr.get("chain_id") and instr["chain_id"] != chain_id:
            raise CatalogError(f"catalog chain_id {instr['chain_id']!r} != node chain_id "
                               f"{chain_id!r}; refusing to sign for the wrong network")
        payer = self.agent.payer(pay_from)
        body = signed_transfer.build_signed_transfer(
            payer, order["provider"], price, memo, chain_id, nonce=nonce)
        return {"order": order, "body": body, "signed_message": signed_transfer
                .canonical_transfer_message(payer.address, order["provider"], price, memo,
                                            body["nonce"], chain_id).decode()}

    def send_payment(self, body: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", PAYMENT_ENDPOINT, body)


def _safe_id(value: str) -> str:
    """Path segment for an id; refuses separators so a bad id cannot reroute a signed call."""
    value = str(value).strip()
    if not value or any(ch in value for ch in "/?#%\\ ") or value in (".", ".."):
        raise CatalogError(f"invalid id {value!r}")
    return value


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def _print_listings(data: Dict[str, Any]) -> None:
    rows = data.get("listings")
    if not isinstance(rows, list):
        raise CatalogError(f"unexpected /catalog/listings response: {data}")
    if not rows:
        print("No active listings match. Offer one: catalog_cli.py offer --help")
    for item in rows:
        turnaround = (f", ~{item['turnaround_hours']}h"
                      if item.get("turnaround_hours") else "")
        print(f"{item['id']}  [{item['category']}]  {item['price_rtc']:g} RTC {item['unit']}"
              f"{turnaround}  by {item['provider']}")
        print(f"    {item['title']}")
    if data.get("terms"):
        print(f"\n{data['terms']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="catalog_cli.py",
        description="Sell and buy agent services on the RustChain service catalog, paid in RTC.")
    parser.add_argument("--node", default=os.environ.get("RUSTCHAIN_NODE", DEFAULT_NODE),
                        help=f"node URL (default $RUSTCHAIN_NODE or {DEFAULT_NODE})")
    parser.add_argument("--insecure", action="store_true",
                        help="skip TLS verification (only for a node IP with a self-signed cert)")
    parser.add_argument("--identity", help="Beacon agent key file "
                        "(default $BEACON_IDENTITY_PATH or ~/.beacon/identity/agent.key)")
    parser.add_argument("--json", action="store_true", help="print raw JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="browse active listings")
    p.add_argument("--category", choices=CATEGORIES)
    p.add_argument("--provider", help="only this provider's bcn_ id")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--offset", type=int, default=0)

    p = sub.add_parser("whoami", help="show this identity's bcn_ id and RTC address")

    p = sub.add_parser("offer", help="list a service you provide (signed)")
    p.add_argument("--title", required=True)
    p.add_argument("--category", required=True, choices=CATEGORIES)
    p.add_argument("--price-rtc", required=True, help="price in RTC, up to 6 decimals")
    p.add_argument("--description", default="", help="what the buyer gets and how it is delivered")
    p.add_argument("--unit", default="per job")
    p.add_argument("--turnaround-hours", type=int)

    p = sub.add_parser("listing-status", help="pause, reactivate or retire your listing (signed)")
    p.add_argument("listing_id")
    p.add_argument("status", choices=("active", "paused", "retired"))

    p = sub.add_parser("order", help="order a listing (signed); pay only after delivery")
    p.add_argument("listing_id")
    p.add_argument("--note", default="", help="what you need; visible to the provider only")

    p = sub.add_parser("orders", help="your orders as buyer or provider (signed)")
    p.add_argument("--role", choices=("buyer", "provider"), default="buyer")
    p.add_argument("--status", choices=("requested", "delivered", "accepted",
                                        "rejected", "cancelled"))

    p = sub.add_parser("show", help="one order (full view if you are a party)")
    p.add_argument("order_id")
    p.add_argument("--public", action="store_true", help="unsigned public summary")

    p = sub.add_parser("deliver", help="provider: deliver an order (signed)")
    p.add_argument("order_id")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="delivered artifact; its sha256 is sent")
    group.add_argument("--hash", help="sha256 hex of the delivered artifact")
    p.add_argument("--uri", help="https link where the buyer can fetch it")

    p = sub.add_parser("accept", help="buyer: accept a delivered order (signed)")
    p.add_argument("order_id")

    p = sub.add_parser("reject", help="buyer: reject a delivered order (signed)")
    p.add_argument("order_id")
    p.add_argument("--reason", required=True)

    p = sub.add_parser("cancel", help="buyer or provider: cancel a requested order (signed)")
    p.add_argument("order_id")
    p.add_argument("--reason", default="")

    p = sub.add_parser("pay", help="buyer: pay an accepted order in RTC (dry run unless --send)")
    p.add_argument("order_id")
    p.add_argument("--from", dest="pay_from", choices=("bcn", "rtc"), default="bcn",
                   help="pay from your bcn_ wallet (default) or the RTC address of the same key")
    p.add_argument("--send", action="store_true",
                   help="actually submit the signed transfer (moves RTC)")
    return parser


def main(argv: Optional[list] = None, transport: Optional[Transport] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.insecure:
        print("warning: TLS verification is off (--insecure)", file=sys.stderr)
    send = transport or urllib_transport(args.node, insecure=args.insecure)
    needs_identity = args.command not in ("list",) and not (
        args.command == "show" and args.public)
    try:
        agent = AgentKey.load(args.identity) if needs_identity else None
        client = CatalogClient(send, agent)
        cmd = args.command
        if cmd == "whoami":
            _print({"agent_id": agent.agent_id, "rtc_address": agent.rtc_address,
                    "public_key": agent.public_key})
        elif cmd == "list":
            data = client.listings(args.category, args.provider, args.limit, args.offset)
            if args.json:
                _print(data)
            else:
                _print_listings(data)
        elif cmd == "offer":
            _print(client.offer(args.title, args.category, args.price_rtc, args.description,
                                args.unit, args.turnaround_hours))
        elif cmd == "listing-status":
            _print(client.set_listing_status(args.listing_id, args.status))
        elif cmd == "order":
            _print(client.order(args.listing_id, args.note))
        elif cmd == "orders":
            _print(client.my_orders(args.role, args.status))
        elif cmd == "show":
            _print(client.get_order(args.order_id, signed=not args.public))
        elif cmd == "deliver":
            digest = sha256_file(args.file) if args.file else args.hash
            _print(client.deliver(args.order_id, digest, args.uri))
        elif cmd == "accept":
            _print(client.accept(args.order_id))
        elif cmd == "reject":
            _print(client.reject(args.order_id, args.reason))
        elif cmd == "cancel":
            _print(client.cancel(args.order_id, args.reason))
        elif cmd == "pay":
            return _pay(client, args)
    except CatalogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        if exc.payload and args.json:
            _print(exc.payload)
        return 1
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def _pay(client: CatalogClient, args: argparse.Namespace) -> int:
    built = client.build_payment(args.order_id, pay_from=args.pay_from)
    body = built["body"]
    summary = {"order_id": args.order_id, "from": body["from_address"],
               "to": body["to_address"], "amount_rtc": body["amount_rtc"],
               "memo": body["memo"], "chain_id": body["chain_id"]}
    if not args.send:
        # A signed body is a spendable transfer until a later nonce supersedes
        # it, so a dry run never prints the signature.
        shown = dict(body, signature="<withheld in dry run>")
        _print({"dry_run": True, "would_send": summary, "request_body": shown,
                "signed_message": built["signed_message"]})
        print("\nDry run: nothing was sent. Re-run with --send to pay.", file=sys.stderr)
        return 0
    result = client.send_payment(body)
    if not (isinstance(result, dict) and result.get("ok") is True):
        print(f"error: node did not accept the transfer: {result}", file=sys.stderr)
        return 1
    after = client.get_order(args.order_id, signed=False)
    _print({"sent": summary, "node_response": result, "order_payment": after.get("payment")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
