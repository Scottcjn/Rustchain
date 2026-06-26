#!/usr/bin/env python3
"""Query the live RustChain health endpoint and print a compact summary."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def fetch_json(url: str) -> tuple[int, str, dict]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "RustChain-Integration-HealthCheck/1.0"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read().decode("utf-8")
        payload = json.loads(raw)
        return response.status, response.geturl(), payload


def main() -> int:
    parser = argparse.ArgumentParser(description="RustChain health check integration")
    parser.add_argument("--base-url", default="https://rustchain.org")
    parser.add_argument("--path", default="/health")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    url = args.base_url.rstrip("/") + args.path

    try:
        status, final_url, payload = fetch_json(url)
    except urllib.error.URLError as exc:
        print(f"error: failed to query {url}: {exc}", file=sys.stderr)
        return 1

    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    ok = payload.get("ok")
    node = payload.get("node") or payload.get("service") or payload.get("name") or "rustchain"
    epoch = payload.get("epoch") or payload.get("current_epoch") or "unknown"

    print(f"url: {final_url}")
    print(f"status: {status}")
    print(f"node: {node}")
    print(f"epoch: {epoch}")
    print(f"ok: {ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
