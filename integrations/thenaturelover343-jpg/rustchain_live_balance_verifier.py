#!/usr/bin/env python3
"""Read and verify live RustChain balance data."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from typing import Any


DEFAULT_NODE_URL = "https://rustchain.org"
DEFAULT_WALLET = "RTC789488a6053e782d99d7242591603407ff515ce1"
MICRO_UNITS_PER_RTC = 1_000_000


class VerificationError(RuntimeError):
    """Raised when a live endpoint fails a verification check."""


def fetch_json(node_url: str, path: str, query: dict[str, str] | None = None) -> Any:
    base = node_url.rstrip("/")
    url = f"{base}{path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"

    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def verify_health(data: dict[str, Any]) -> str:
    if data.get("ok") is not True:
        raise VerificationError("/health did not report ok=true")
    return f"health: ok=true version={data.get('version', 'unknown')}"


def verify_epoch(data: dict[str, Any]) -> str:
    epoch = data.get("epoch")
    supply = data.get("total_supply_rtc")
    if not isinstance(epoch, int) or epoch < 0:
        raise VerificationError("/epoch did not return a non-negative epoch")
    if not isinstance(supply, (int, float)) or supply <= 0:
        raise VerificationError("/epoch did not return a positive total_supply_rtc")
    return f"epoch: {epoch} slot={data.get('slot')} supply={supply}"


def verify_miners(data: dict[str, Any]) -> str:
    miners = data.get("miners")
    if not isinstance(miners, list) or not miners:
        raise VerificationError("/api/miners did not return a non-empty miners list")
    first = miners[0].get("miner", "unknown") if isinstance(miners[0], dict) else "unknown"
    return f"miners: count={len(miners)} first={first}"


def verify_balance(data: dict[str, Any], wallet: str) -> str:
    returned_wallet = data.get("miner_id") or data.get("wallet_id")
    if returned_wallet != wallet:
        raise VerificationError(
            f"/wallet/balance returned {returned_wallet!r}, expected {wallet!r}"
        )

    amount_rtc = data.get("amount_rtc")
    amount_i64 = data.get("amount_i64")
    if not isinstance(amount_rtc, (int, float)):
        raise VerificationError("/wallet/balance missing numeric amount_rtc")
    if amount_i64 is not None:
        expected = int(round(float(amount_rtc) * MICRO_UNITS_PER_RTC))
        if int(amount_i64) != expected:
            raise VerificationError(
                f"amount_i64={amount_i64} does not match amount_rtc={amount_rtc}"
            )

    return f"balance: wallet={wallet} amount_rtc={amount_rtc} amount_i64={amount_i64}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify live RustChain balance data")
    parser.add_argument("--node-url", default=DEFAULT_NODE_URL, help="RustChain node URL")
    parser.add_argument("--wallet", default=DEFAULT_WALLET, help="Native RTC wallet/miner ID")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        health = fetch_json(args.node_url, "/health")
        epoch = fetch_json(args.node_url, "/epoch")
        miners = fetch_json(args.node_url, "/api/miners")
        balance = fetch_json(args.node_url, "/wallet/balance", {"miner_id": args.wallet})

        print("RustChain live balance verifier")
        print(f"node: {args.node_url.rstrip('/')}")
        print(verify_health(health))
        print(verify_epoch(epoch))
        print(verify_miners(miners))
        print(verify_balance(balance, args.wallet))
        print("verification: PASS")
        return 0
    except Exception as exc:
        print(f"verification: FAIL ({exc})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
