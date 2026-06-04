#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify live RustChain wallet history without using wallet secrets."""

from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen


DEFAULT_NODE = "https://50.28.86.131"
DEFAULT_MINER_ID = "RTCe0961d6b54f2fa96db57a373c84d8ad8986153f8"
HEX_32 = re.compile(r"^[0-9a-fA-F]{32}$")
KNOWN_STATUSES = {"pending", "confirmed", "failed", "rejected"}


def fetch_json(url: str, *, strict_tls: bool) -> dict[str, Any]:
    context = None if strict_tls else ssl._create_unverified_context()
    with urlopen(url, timeout=15, context=context) as response:
        payload = response.read().decode("utf-8")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object from {url}")
    return data


def amount_as_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid transaction amount: {value!r}") from exc


def verify_history(history: dict[str, Any], miner_id: str) -> tuple[int, Decimal]:
    if history.get("ok") is not True:
        raise ValueError("wallet history did not return ok=true")
    if history.get("miner_id") != miner_id:
        raise ValueError("wallet history miner_id does not match request")

    transactions = history.get("transactions")
    if not isinstance(transactions, list) or not transactions:
        raise ValueError("wallet history must contain at least one transaction")

    pending_transfer_in = Decimal("0")
    verified_hashes = 0
    for index, tx in enumerate(transactions, start=1):
        if not isinstance(tx, dict):
            raise ValueError(f"transaction {index} is not an object")

        tx_hash = tx.get("tx_hash")
        if not isinstance(tx_hash, str) or not HEX_32.fullmatch(tx_hash):
            raise ValueError(f"transaction {index} has invalid tx_hash")
        verified_hashes += 1

        status = tx.get("status")
        if status not in KNOWN_STATUSES:
            raise ValueError(f"transaction {index} has unknown status {status!r}")

        amount = amount_as_decimal(tx.get("amount"))
        if amount < 0:
            raise ValueError(f"transaction {index} has negative amount")

        if tx.get("type") == "transfer_in" and status == "pending":
            pending_transfer_in += amount

    return verified_hashes, pending_transfer_in


def build_url(node: str, path: str, params: dict[str, Any] | None = None) -> str:
    base = node.rstrip("/")
    query = f"?{urlencode(params)}" if params else ""
    return f"{base}{path}{query}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", default=DEFAULT_NODE, help="RustChain node URL")
    parser.add_argument("--miner-id", default=DEFAULT_MINER_ID, help="RTC wallet/miner id")
    parser.add_argument("--limit", type=int, default=10, help="history row limit")
    parser.add_argument(
        "--strict-tls",
        action="store_true",
        help="require normal TLS certificate verification",
    )
    args = parser.parse_args()

    health = fetch_json(build_url(args.node, "/health"), strict_tls=args.strict_tls)
    if health.get("ok") is not True:
        raise ValueError("node health did not return ok=true")

    history = fetch_json(
        build_url(
            args.node,
            "/wallet/history",
            {"miner_id": args.miner_id, "limit": args.limit},
        ),
        strict_tls=args.strict_tls,
    )
    verified_hashes, pending_total = verify_history(history, args.miner_id)

    print("RustChain wallet history verifier")
    print(f"node ok: version={health.get('version', 'unknown')} db_rw={health.get('db_rw')}")
    print(f"wallet: {args.miner_id}")
    print(f"transactions: {len(history['transactions'])} returned, total field={history.get('total')}")
    print(f"pending transfer_in total: {pending_total} RTC")
    print(f"result: verified {verified_hashes} transaction hash(es)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - command-line verifier reports concise failures.
        print(f"verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
