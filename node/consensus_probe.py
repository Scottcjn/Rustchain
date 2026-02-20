#!/usr/bin/env python3
"""
Cross-node consistency probe for RustChain.

This is a read-only operational tool that compares public API snapshots across
multiple nodes and emits a machine-readable report with a non-zero exit code
on divergence.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from typing import Callable, List, Optional
from urllib.request import urlopen


Fetcher = Callable[..., dict]


@dataclass
class NodeSnapshot:
    node: str
    ok: bool
    version: Optional[str]
    enrolled_miners: Optional[int]
    miners_count: Optional[int]
    total_balance: Optional[float]
    error: Optional[str]


def _default_fetcher(url: str, timeout: int) -> dict:
    with urlopen(url, timeout=timeout) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _fetch_json(node_url: str, endpoint: str, timeout_s: int, fetcher: Fetcher):
    url = f"{node_url.rstrip('/')}{endpoint}"
    return fetcher(url, timeout=timeout_s)


def collect_snapshot(node_url: str, timeout_s: int = 8, fetcher: Fetcher = _default_fetcher) -> NodeSnapshot:
    try:
        health = _fetch_json(node_url, "/health", timeout_s, fetcher)
        epoch = _fetch_json(node_url, "/epoch", timeout_s, fetcher)
        stats = _fetch_json(node_url, "/api/stats", timeout_s, fetcher)
        miners = _fetch_json(node_url, "/api/miners", timeout_s, fetcher)

        miners_count = len(miners) if isinstance(miners, list) else 0

        return NodeSnapshot(
            node=node_url,
            ok=bool(health.get("ok", False)),
            version=health.get("version"),
            enrolled_miners=epoch.get("enrolled_miners"),
            miners_count=miners_count,
            total_balance=stats.get("total_balance"),
            error=None,
        )
    except Exception as exc:
        return NodeSnapshot(
            node=node_url,
            ok=False,
            version=None,
            enrolled_miners=None,
            miners_count=None,
            total_balance=None,
            error=str(exc),
        )


def _span(values: List[float]) -> float:
    return max(values) - min(values) if values else 0.0


def detect_divergence(snapshots: List[NodeSnapshot], balance_tolerance: float = 1e-6) -> List[str]:
    issues: List[str] = []

    failed = [s.node for s in snapshots if s.error]
    if failed:
        issues.append(f"unreachable_nodes:{','.join(failed)}")

    healthy = [s for s in snapshots if not s.error]
    if len(healthy) < 2:
        issues.append("insufficient_healthy_nodes")
        return issues

    versions = sorted({s.version for s in healthy if s.version})
    if len(versions) > 1:
        issues.append(f"version_mismatch:{','.join(versions)}")

    enrolled = [float(s.enrolled_miners) for s in healthy if s.enrolled_miners is not None]
    if enrolled and _span(enrolled) > 0:
        issues.append("divergence_enrolled_miners")

    miner_counts = [float(s.miners_count) for s in healthy if s.miners_count is not None]
    if miner_counts and _span(miner_counts) > 0:
        issues.append("divergence_miners_count")

    balances = [float(s.total_balance) for s in healthy if s.total_balance is not None]
    if balances and _span(balances) > balance_tolerance:
        issues.append("divergence_total_balance")

    return issues


def run_probe(nodes: List[str], timeout_s: int = 8, balance_tolerance: float = 1e-6):
    snapshots = [collect_snapshot(node, timeout_s=timeout_s) for node in nodes]
    issues = detect_divergence(snapshots, balance_tolerance=balance_tolerance)

    report = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "nodes": [asdict(s) for s in snapshots],
        "issues": issues,
    }

    if issues:
        if any(i.startswith("divergence") or i.startswith("version_mismatch") for i in issues):
            return 2, report
        return 1, report
    return 0, report


def parse_args():
    parser = argparse.ArgumentParser(description="RustChain cross-node consistency probe")
    parser.add_argument("--nodes", nargs="+", required=True, help="Node base URLs to compare")
    parser.add_argument("--timeout", type=int, default=8, help="HTTP timeout in seconds")
    parser.add_argument(
        "--balance-tolerance",
        type=float,
        default=1e-6,
        help="Allowed max delta for total_balance before flagging divergence",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    code, report = run_probe(args.nodes, timeout_s=args.timeout, balance_tolerance=args.balance_tolerance)
    if args.pretty:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(json.dumps(report, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
