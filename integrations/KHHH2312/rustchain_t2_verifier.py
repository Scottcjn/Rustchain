#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Live RustChain T2 verifier.

The script reads a live RustChain node, picks or validates an enrolled miner,
and verifies the miner balance response against the documented micro-RTC unit
conversion.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import math
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_BASE_URL = "https://rustchain.org"
USER_AGENT = "KHHH2312-rustchain-t2-verifier/1.0"
MICRO_RTC = 1_000_000


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        raise urllib.error.HTTPError(req.full_url, code, "redirects are disabled", headers, fp)


OPENER = urllib.request.build_opener(NoRedirectHandler)


@dataclass(frozen=True)
class VerificationResult:
    health: dict[str, Any]
    epoch: dict[str, Any]
    miner_count: int
    selected_miner: str
    balance: dict[str, Any]
    slot_epoch_verified: bool
    selected_is_enrolled: bool
    balance_units_verified: bool

    @property
    def ok(self) -> bool:
        return (
            bool(self.health.get("ok"))
            and self.slot_epoch_verified
            and self.selected_is_enrolled
            and self.balance_units_verified
        )


def _is_local_host(hostname: str) -> bool:
    return hostname.lower() in {"localhost", "127.0.0.1", "::1"}


ResolvedAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


def _resolve_public_addresses(hostname: str, port: int) -> list[ResolvedAddress]:
    try:
        infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"could not resolve host {hostname!r}: {exc}") from exc

    addresses: list[ResolvedAddress] = []
    for info in infos:
        raw_address = info[4][0]
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError as exc:
            raise ValueError(f"invalid resolved address {raw_address!r}") from exc
        addresses.append(address)

    if not addresses:
        raise ValueError(f"host {hostname!r} resolved no addresses")
    return addresses


def validate_base_url(raw_url: str) -> str:
    parsed = urllib.parse.urlparse(raw_url)
    if parsed.username or parsed.password:
        raise ValueError("base URL must not include credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("base URL must not include query strings or fragments")
    if parsed.path not in {"", "/"}:
        raise ValueError("base URL must not include an API path")
    if not parsed.hostname:
        raise ValueError("base URL must include a hostname")

    scheme = parsed.scheme.lower()
    port = parsed.port or (443 if scheme == "https" else 80)
    hostname = parsed.hostname

    if _is_local_host(hostname):
        if scheme not in {"http", "https"}:
            raise ValueError("local development URLs must use http or https")
    else:
        if scheme != "https":
            raise ValueError("remote RustChain nodes must use https")
        for address in _resolve_public_addresses(hostname, port):
            if (
                address.is_private
                or address.is_loopback
                or address.is_link_local
                or address.is_multicast
                or address.is_reserved
                or address.is_unspecified
            ):
                raise ValueError(f"remote host resolved to non-public address {address}")

    netloc = hostname if parsed.port is None else f"{hostname}:{parsed.port}"
    return urllib.parse.urlunparse((scheme, netloc, "", "", "", "")).rstrip("/")


def fetch_json(base_url: str, path: str, *, timeout: float) -> dict[str, Any]:
    url = f"{base_url}{path}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with OPENER.open(request, timeout=timeout) as response:
            status = getattr(response, "status", response.getcode())
            if status != 200:
                raise RuntimeError(f"{path} returned HTTP {status}")
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type.lower():
                raise RuntimeError(f"{path} returned non-JSON content type {content_type!r}")
            payload = response.read(1_000_000)
    except urllib.error.HTTPError:
        raise
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{path} request failed: {exc}") from exc

    try:
        data = json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{path} returned invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"{path} returned {type(data).__name__}, expected object")
    return data


def verify_epoch_slot(epoch: dict[str, Any]) -> bool:
    try:
        epoch_number = int(epoch["epoch"])
        slot = int(epoch["slot"])
        blocks_per_epoch = int(epoch["blocks_per_epoch"])
    except (KeyError, TypeError, ValueError):
        return False
    return blocks_per_epoch > 0 and slot // blocks_per_epoch == epoch_number


def _extract_miners(raw: dict[str, Any]) -> list[dict[str, Any]]:
    miners = raw.get("miners", raw.get("data", []))
    if not isinstance(miners, list):
        raise RuntimeError("/api/miners did not return a miner list")
    return [miner for miner in miners if isinstance(miner, dict)]


def _miner_id(miner: dict[str, Any]) -> str | None:
    value = miner.get("miner") or miner.get("miner_id") or miner.get("wallet")
    return value if isinstance(value, str) and value else None


def select_miner(miners: list[dict[str, Any]], requested: str | None) -> str:
    available = [_miner_id(miner) for miner in miners]
    ids = [miner_id for miner_id in available if miner_id]
    if not ids:
        raise RuntimeError("no miner identifiers found in /api/miners")
    if requested:
        if requested not in ids:
            raise RuntimeError(f"requested miner {requested!r} is not enrolled")
        return requested
    return ids[0]


def verify_balance_units(balance: dict[str, Any], miner_id: str) -> bool:
    if balance.get("miner_id") != miner_id:
        return False
    try:
        amount_i64 = int(balance["amount_i64"])
        amount_rtc = float(balance["amount_rtc"])
    except (KeyError, TypeError, ValueError):
        return False
    return amount_i64 >= 0 and math.isclose(amount_i64 / MICRO_RTC, amount_rtc, rel_tol=0, abs_tol=1e-9)


def run_verification(base_url: str, miner_id: str | None, timeout: float) -> VerificationResult:
    health = fetch_json(base_url, "/health", timeout=timeout)
    epoch = fetch_json(base_url, "/epoch", timeout=timeout)
    miners_payload = fetch_json(base_url, "/api/miners", timeout=timeout)
    miners = _extract_miners(miners_payload)
    selected_miner = select_miner(miners, miner_id)
    selected_is_enrolled = any(_miner_id(miner) == selected_miner for miner in miners)

    query = urllib.parse.urlencode({"miner_id": selected_miner})
    balance = fetch_json(base_url, f"/wallet/balance?{query}", timeout=timeout)

    return VerificationResult(
        health=health,
        epoch=epoch,
        miner_count=len(miners),
        selected_miner=selected_miner,
        balance=balance,
        slot_epoch_verified=verify_epoch_slot(epoch),
        selected_is_enrolled=selected_is_enrolled,
        balance_units_verified=verify_balance_units(balance, selected_miner),
    )


def format_lines(result: VerificationResult) -> list[str]:
    return [
        "RustChain T2 live verification",
        (
            "health: "
            f"ok={result.health.get('ok')} "
            f"version={result.health.get('version')} "
            f"tip_age_slots={result.health.get('tip_age_slots')}"
        ),
        (
            "epoch: "
            f"epoch={result.epoch.get('epoch')} "
            f"slot={result.epoch.get('slot')} "
            f"blocks_per_epoch={result.epoch.get('blocks_per_epoch')} "
            f"verified_slot_epoch={result.slot_epoch_verified}"
        ),
        (
            "miners: "
            f"enrolled_epoch={result.epoch.get('enrolled_miners')} "
            f"listed={result.miner_count} "
            f"selected={result.selected_miner} "
            f"selected_is_enrolled={result.selected_is_enrolled}"
        ),
        (
            "balance: "
            f"miner={result.balance.get('miner_id')} "
            f"amount_i64={result.balance.get('amount_i64')} "
            f"amount_rtc={result.balance.get('amount_rtc')} "
            f"verified_micro_units={result.balance_units_verified}"
        ),
        (
            "verification: PASS - live miner enrollment and balance unit checks succeeded"
            if result.ok
            else "verification: FAIL - at least one live verification check failed"
        ),
    ]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify live RustChain miner balance state.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="RustChain node base URL")
    parser.add_argument("--miner-id", default=None, help="Specific enrolled miner to verify")
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        base_url = validate_base_url(args.base_url)
        result = run_verification(base_url, args.miner_id, args.timeout)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(
            json.dumps(
                {
                    "ok": result.ok,
                    "health": result.health,
                    "epoch": result.epoch,
                    "miner_count": result.miner_count,
                    "selected_miner": result.selected_miner,
                    "balance": result.balance,
                    "checks": {
                        "slot_epoch_verified": result.slot_epoch_verified,
                        "selected_is_enrolled": result.selected_is_enrolled,
                        "balance_units_verified": result.balance_units_verified,
                    },
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print("\n".join(format_lines(result)))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
