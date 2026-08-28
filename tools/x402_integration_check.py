#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run reproducible x402 deployment checks and retain raw HTTP evidence.

The checker delegates HTTP to curl so reports contain the verbose request and
response headers operators use when diagnosing deployments. Authenticated wallet
linking is opt-in, and credentials are redacted from all report output.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_STATUS_MARKER = "__RUSTCHAIN_HTTP_STATUS__:"
_SENSITIVE_HEADER_NAMES = frozenset(
    {
        "authorization",
        "cookie",
        "proxy-authorization",
        "set-cookie",
        "x-admin-key",
        "x-api-key",
        "x-payment",
    }
)
_SENSITIVE_HEADER_LINE = re.compile(
    r"^([<>] (?:authorization|cookie|proxy-authorization|set-cookie|"
    r"x-admin-key|x-api-key|x-payment):).*$",
    re.IGNORECASE | re.MULTILINE,
)
_BASE_ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")


@dataclass(frozen=True)
class Endpoint:
    name: str
    method: str
    url: str
    expected_statuses: frozenset[int]
    json_body: dict | None = None
    requires_credentials: bool = False


@dataclass(frozen=True)
class CheckResult:
    endpoint: Endpoint
    outcome: str
    http_status: int | None
    reason: str
    evidence: str


ENDPOINTS = (
    Endpoint(
        "bottube_x402_status",
        "GET",
        "https://bottube.ai/api/x402/status",
        frozenset({200}),
    ),
    Endpoint(
        "bottube_premium_videos",
        "GET",
        "https://bottube.ai/api/premium/videos",
        frozenset({200, 402}),
    ),
    Endpoint(
        "bottube_premium_analytics",
        "GET",
        "https://bottube.ai/api/premium/analytics/sophia-elya",
        frozenset({200, 402}),
    ),
    Endpoint(
        "bottube_trending_export",
        "GET",
        "https://bottube.ai/api/premium/trending/export",
        frozenset({200, 402}),
    ),
    Endpoint(
        "bottube_wallet_link",
        "POST",
        "https://bottube.ai/api/agents/me/coinbase-wallet",
        frozenset({200, 201}),
        requires_credentials=True,
    ),
    Endpoint(
        "beacon_x402_status",
        "GET",
        "https://rustchain.org/beacon/api/x402/status",
        frozenset({200}),
    ),
    Endpoint(
        "beacon_premium_reputation",
        "GET",
        "https://rustchain.org/beacon/api/premium/reputation",
        frozenset({200, 402}),
    ),
    Endpoint(
        "beacon_contracts_export",
        "GET",
        "https://rustchain.org/beacon/api/premium/contracts/export",
        frozenset({200, 402}),
    ),
    Endpoint(
        "node_swap_info",
        "GET",
        "https://rustchain.org/wallet/swap-info",
        frozenset({200}),
    ),
    Endpoint(
        "beacon_compute_inference",
        "POST",
        "https://rustchain.org/beacon/api/compute/inference",
        frozenset({402}),
        json_body={"prompt": "x402 integration check"},
    ),
    Endpoint(
        "beacon_x402_pricing",
        "GET",
        "https://rustchain.org/beacon/api/x402/pricing",
        frozenset({200}),
    ),
    Endpoint(
        "beacon_compute_catalog",
        "GET",
        "https://rustchain.org/beacon/api/compute/catalog",
        frozenset({200}),
    ),
)


def _redact(text: str, secrets: Iterable[str] = ()) -> str:
    redacted = _SENSITIVE_HEADER_LINE.sub(r"\1 [REDACTED]", text)
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def _display_command(command: Sequence[str]) -> str:
    safe_args = []
    previous = ""
    for argument in command:
        displayed = argument
        if previous in ("--header", "-H"):
            header_name, separator, _ = argument.partition(":")
            if separator and header_name.strip().lower() in _SENSITIVE_HEADER_NAMES:
                displayed = f"{header_name}: [REDACTED]"
        safe_args.append(displayed)
        previous = argument
    return " ".join(shlex.quote(argument) for argument in safe_args)


def _curl_command(
    endpoint: Endpoint,
    timeout: int,
    api_key: str,
    wallet_address: str,
    insecure: bool,
) -> list[str]:
    command = [
        "curl",
        "--silent",
        "--show-error",
        "--verbose",
        "--max-time",
        str(timeout),
        "--request",
        endpoint.method,
        "--header",
        "Accept: application/json",
    ]
    if insecure:
        command.append("--insecure")

    body = endpoint.json_body
    if endpoint.requires_credentials:
        command.extend(["--header", f"X-API-Key: {api_key}"])
        body = {"coinbase_address": wallet_address}

    if body is not None:
        command.extend(
            [
                "--header",
                "Content-Type: application/json",
                "--data",
                json.dumps(body, separators=(",", ":"), sort_keys=True),
            ]
        )

    command.extend(
        [
            "--write-out",
            f"\n{_STATUS_MARKER}%{{http_code}}\n",
            endpoint.url,
        ]
    )
    return command


def _split_body_and_status(stdout: str) -> tuple[str, int | None]:
    body, marker, status_text = stdout.rpartition(_STATUS_MARKER)
    if not marker:
        return stdout, None
    status_lines = status_text.strip().splitlines()
    status_line = status_lines[0] if status_lines else ""
    if not status_line.isdigit():
        return body.rstrip("\n"), None
    return body.rstrip("\n"), int(status_line)


def _expected_status_text(statuses: frozenset[int]) -> str:
    return " or ".join(str(status) for status in sorted(statuses))


def run_endpoint(
    endpoint: Endpoint,
    timeout: int,
    api_key: str = "",
    wallet_address: str = "",
    insecure: bool = False,
) -> CheckResult:
    """Run one endpoint check without allowing an HTTP error to look successful."""
    if endpoint.requires_credentials and (not api_key or not wallet_address):
        return CheckResult(
            endpoint=endpoint,
            outcome="SKIP",
            http_status=None,
            reason="wallet linking requires both --api-key and --wallet-address",
            evidence="Authenticated, state-changing request was not sent.",
        )
    if endpoint.requires_credentials and not _BASE_ADDRESS.fullmatch(wallet_address):
        return CheckResult(
            endpoint=endpoint,
            outcome="FAIL",
            http_status=None,
            reason="wallet address must be 0x followed by 40 hexadecimal characters",
            evidence="Authenticated, state-changing request was not sent.",
        )

    command = _curl_command(endpoint, timeout, api_key, wallet_address, insecure)
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout + 5,
            check=False,
        )
    except FileNotFoundError:
        return CheckResult(
            endpoint, "FAIL", None, "curl executable was not found", "$ curl"
        )
    except subprocess.TimeoutExpired as exc:
        evidence = _redact(
            f"$ {_display_command(command)}\n\n"
            f"--- verbose output ---\n{exc.stderr or ''}\n"
            f"--- response body ---\n{exc.stdout or ''}",
            (api_key,),
        )
        return CheckResult(endpoint, "FAIL", None, "request timed out", evidence)

    body, http_status = _split_body_and_status(completed.stdout)
    evidence = _redact(
        f"$ {_display_command(command)}\n\n"
        f"--- verbose output (curl stderr) ---\n{completed.stderr.rstrip()}\n\n"
        f"--- response body (curl stdout) ---\n{body}",
        (api_key,),
    )

    if completed.returncode != 0:
        return CheckResult(
            endpoint,
            "FAIL",
            http_status,
            f"curl exited with status {completed.returncode}",
            evidence,
        )
    if http_status is None:
        return CheckResult(
            endpoint,
            "FAIL",
            None,
            "curl did not report an HTTP status",
            evidence,
        )
    if http_status not in endpoint.expected_statuses:
        expected = _expected_status_text(endpoint.expected_statuses)
        return CheckResult(
            endpoint,
            "FAIL",
            http_status,
            f"expected HTTP {expected}, got {http_status}",
            evidence,
        )

    try:
        json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return CheckResult(
            endpoint,
            "FAIL",
            http_status,
            "response body is not valid JSON",
            evidence,
        )

    return CheckResult(
        endpoint, "PASS", http_status, "expected JSON response", evidence
    )


def render_report(results: Sequence[CheckResult], generated_at: str) -> str:
    """Render one authoritative result and complete evidence block per request."""
    lines = [
        "# x402 integration check",
        "",
        f"Generated: {generated_at}",
        "",
        "| Endpoint | Method | HTTP | Result | Detail |",
        "|---|---:|---:|---:|---|",
    ]
    for result in results:
        http_status = str(result.http_status) if result.http_status is not None else "-"
        lines.append(
            f"| {result.endpoint.name} | {result.endpoint.method} | {http_status} "
            f"| {result.outcome} | {result.reason} |"
        )

    lines.extend(["", "## Raw request/response evidence", ""])
    for result in results:
        lines.extend(
            [
                f"### {result.endpoint.name}",
                "",
                "```text",
                result.evidence.rstrip(),
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check RustChain ecosystem x402 routes with redacted verbose evidence."
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="per-request timeout in seconds",
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="BoTTube API key for the optional wallet-link request",
    )
    parser.add_argument(
        "--api-key-env",
        default="",
        metavar="NAME",
        help="read the optional BoTTube API key from environment variable NAME",
    )
    parser.add_argument(
        "--wallet-address",
        default="",
        help="Base wallet address for the optional wallet-link request",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="disable TLS certificate checks",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="write the Markdown report to this path",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")

    api_key = args.api_key
    if args.api_key_env:
        api_key = os.environ.get(args.api_key_env, "")

    results = [
        run_endpoint(
            endpoint,
            timeout=args.timeout,
            api_key=api_key,
            wallet_address=args.wallet_address,
            insecure=args.insecure,
        )
        for endpoint in ENDPOINTS
    ]
    generated_at = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    report = render_report(results, generated_at)

    if args.output:
        args.output.write_text(report, encoding="utf-8")
        print(f"Wrote x402 evidence report to {args.output}")
    else:
        print(report, end="")

    failed = sum(result.outcome == "FAIL" for result in results)
    skipped = sum(result.outcome == "SKIP" for result in results)
    passed = sum(result.outcome == "PASS" for result in results)
    print(
        f"x402 checks: {passed} passed, {failed} failed, {skipped} skipped",
        file=sys.stderr,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
