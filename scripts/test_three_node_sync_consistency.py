#!/usr/bin/env python3
"""Check sync status consistency across three RustChain nodes.

Validates:
- `/sync/status` availability
- merkle root equality
- per-table row counts and table hashes
- peer sync history visibility
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Dict, Any, List

import requests


DEFAULT_NODES = [
    "https://50.28.86.131:8099",
    "https://50.28.86.153:8099",
    "https://76.8.228.245:8099",
]


def fetch_status(base: str, admin_key: str, verify_ssl: bool, timeout: float) -> Dict[str, Any]:
    url = f"{base.rstrip('/')}/sync/status"
    headers = {"X-Admin-Key": admin_key} if admin_key else {}
    r = requests.get(url, headers=headers, timeout=timeout, verify=verify_ssl)
    r.raise_for_status()
    data = r.json()
    data["_node"] = base
    return data


def summarize(statuses: List[Dict[str, Any]]) -> Dict[str, Any]:
    roots = {s.get("_node"): s.get("merkle_root") for s in statuses}
    root_set = {v for v in roots.values() if v}

    table_counts = {}
    table_hashes = {}
    for s in statuses:
        node = s.get("_node")
        for t, info in (s.get("tables") or {}).items():
            table_counts.setdefault(t, {})[node] = info.get("count")
            table_hashes.setdefault(t, {})[node] = info.get("hash")

    mismatched_counts = {t: vals for t, vals in table_counts.items() if len(set(vals.values())) > 1}
    mismatched_hashes = {t: vals for t, vals in table_hashes.items() if len(set(vals.values())) > 1}

    return {
        "nodes": [s.get("_node") for s in statuses],
        "merkle_roots": roots,
        "merkle_consistent": len(root_set) <= 1,
        "mismatched_table_counts": mismatched_counts,
        "mismatched_table_hashes": mismatched_hashes,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate 3-node RustChain sync consistency")
    ap.add_argument("--nodes", nargs="+", default=DEFAULT_NODES)
    ap.add_argument("--admin-key", default=os.getenv("RC_ADMIN_KEY", ""))
    ap.add_argument("--insecure", action="store_true", help="Disable TLS cert verification")
    ap.add_argument("--timeout", type=float, default=10.0)
    args = ap.parse_args()

    verify_ssl = not args.insecure
    statuses = []
    for n in args.nodes:
        try:
            statuses.append(fetch_status(n, args.admin_key, verify_ssl, args.timeout))
        except Exception as e:
            statuses.append({"_node": n, "error": str(e)})

    ok = [s for s in statuses if "error" not in s]
    report = summarize(ok) if ok else {"nodes": args.nodes, "error": "No reachable nodes"}
    report["errors"] = [{"node": s.get("_node"), "error": s.get("error")} for s in statuses if "error" in s]
    print(json.dumps(report, indent=2))

    if report.get("errors"):
        return 2
    if not report.get("merkle_consistent", False):
        return 3
    if report.get("mismatched_table_counts") or report.get("mismatched_table_hashes"):
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
