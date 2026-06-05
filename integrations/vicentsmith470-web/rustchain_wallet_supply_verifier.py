#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify live RustChain wallet balance and token supply unit consistency."""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Any


DEFAULT_BASE_URL = "https://rustchain.org"
MICRO_RTC = Decimal("1000000")


def fetch_json(base_url: str, path: str, params: dict[str, str] | None, timeout: float) -> dict[str, Any]:
    query = ""
    if params:
        query = "?" + urllib.parse.urlencode(params)
    url = base_url.rstrip("/") + path + query

    request = urllib.request.Request(url, headers={"User-Agent": "rustchain-wallet-supply-verifier/1.0"})
    context = ssl.create_default_context()

    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"request failed for {url}: {exc}") from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"non-JSON response from {url}") from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"expected JSON object from {url}")
    return data


def as_decimal(value: Any, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise RuntimeError(f"{field} is not numeric: {value!r}") from exc


def verify_wallet_balance(balance: dict[str, Any], miner_id: str) -> dict[str, Any]:
    returned_miner = balance.get("miner_id")
    if returned_miner != miner_id:
        raise RuntimeError(f"wallet endpoint returned miner_id {returned_miner!r}, expected {miner_id!r}")

    amount_rtc = as_decimal(balance.get("amount_rtc"), "amount_rtc")
    amount_i64 = as_decimal(balance.get("amount_i64"), "amount_i64")
    expected_i64 = int((amount_rtc * MICRO_RTC).to_integral_value())
    actual_i64 = int(amount_i64)

    if actual_i64 != expected_i64:
        raise RuntimeError(f"amount_i64 {actual_i64} does not match amount_rtc {amount_rtc}")

    return {
        "miner_id": miner_id,
        "amount_rtc": str(amount_rtc),
        "amount_i64": actual_i64,
        "verified_micro_units": True,
    }


def verify_tokenomics(tokenomics: dict[str, Any]) -> dict[str, Any]:
    total_supply_rtc = as_decimal(tokenomics.get("total_supply_rtc"), "total_supply_rtc")
    total_supply_urtc = as_decimal(tokenomics.get("total_supply_urtc"), "total_supply_urtc")
    expected_urtc = int((total_supply_rtc * MICRO_RTC).to_integral_value())
    actual_urtc = int(total_supply_urtc)

    if actual_urtc != expected_urtc:
        raise RuntimeError(
            f"total_supply_urtc {actual_urtc} does not match total_supply_rtc {total_supply_rtc}"
        )

    return {
        "chain_id": tokenomics.get("chain_id"),
        "total_supply_rtc": str(total_supply_rtc),
        "total_supply_urtc": actual_urtc,
        "reference_rate_usd": tokenomics.get("reference_rate_usd"),
        "verified_supply_units": True,
    }


def run(base_url: str, miner_id: str, timeout: float) -> dict[str, Any]:
    health = fetch_json(base_url, "/health", None, timeout)
    if health.get("ok") is not True:
        raise RuntimeError(f"node health check failed: {health}")

    balance = fetch_json(base_url, "/wallet/balance", {"miner_id": miner_id}, timeout)
    tokenomics = fetch_json(base_url, "/api/tokenomics", None, timeout)

    return {
        "health": {
            "ok": health.get("ok"),
            "version": health.get("version"),
            "tip_age_slots": health.get("tip_age_slots"),
        },
        "balance": verify_wallet_balance(balance, miner_id),
        "tokenomics": verify_tokenomics(tokenomics),
    }


def print_text_report(result: dict[str, Any]) -> None:
    health = result["health"]
    balance = result["balance"]
    tokenomics = result["tokenomics"]

    print("RustChain wallet supply verifier")
    print(
        "health: "
        f"ok={health['ok']} version={health['version']} tip_age_slots={health['tip_age_slots']}"
    )
    print(
        "balance: "
        f"miner={balance['miner_id']} amount_i64={balance['amount_i64']} "
        f"amount_rtc={balance['amount_rtc']} verified_micro_units={balance['verified_micro_units']}"
    )
    print(
        "tokenomics: "
        f"chain_id={tokenomics['chain_id']} total_supply_rtc={tokenomics['total_supply_rtc']} "
        f"total_supply_urtc={tokenomics['total_supply_urtc']} "
        f"verified_supply_units={tokenomics['verified_supply_units']} "
        f"reference_rate_usd={tokenomics['reference_rate_usd']}"
    )
    print("verification: PASS - live wallet balance and token supply unit checks succeeded")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="RustChain node base URL")
    parser.add_argument("--miner-id", required=True, help="RTC wallet/miner id to verify")
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = run(args.base_url, args.miner_id, args.timeout)
    except RuntimeError as exc:
        print(f"verification: FAIL - {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print_text_report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
