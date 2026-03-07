#!/usr/bin/env python3
"""
RustChain Health Check CLI

Queries all 3 attestation nodes and displays health status.
Bounty: #1111 - 8 RTC Reward
"""

import argparse
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


ATTESTATION_NODES = [
    ("50.28.86.131", 443, True),
    ("50.28.86.153", 443, True),
    ("76.8.228.245", 8099, False),
]


def utc_iso(ts: Optional[float] = None) -> str:
    ts = time.time() if ts is None else ts
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _ssl_context(insecure: bool) -> Optional[ssl.SSLContext]:
    if not insecure:
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def http_json_get(url: str, timeout_s: int, insecure: bool) -> Tuple[bool, Any, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "rustchain-health-check/1.0"})
        with urllib.request.urlopen(req, timeout=timeout_s, context=_ssl_context(insecure)) as resp:
            body = resp.read(1024 * 1024).decode("utf-8", errors="replace")
            try:
                return True, json.loads(body), ""
            except Exception:
                return False, None, "invalid_json"
    except urllib.error.HTTPError as e:
        return False, None, f"http_{e.code}"
    except Exception as e:
        return False, None, "unreachable"


@dataclass
class NodeHealth:
    host: str
    port: int
    online: bool
    version: str = "N/A"
    uptime: str = "N/A"
    db_rw: str = "N/A"
    tip_age: str = "N/A"
    error: str = ""


def check_node(host: str, port: int, use_https: bool) -> NodeHealth:
    protocol = "https" if use_https else "http"
    url = f"{protocol}://{host}:{port}/health"
    
    health = NodeHealth(host=host, port=port, online=False)
    
    ok, data, err = http_json_get(url, timeout_s=10, insecure=True)
    
    if not ok:
        health.error = err
        return health
    
    health.online = True
    
    # Parse version
    if "version" in data:
        health.version = str(data["version"])
    elif "data" in data and "version" in data.get("data", {}):
        health.version = str(data["data"]["version"])
    
    # Parse uptime
    if "uptime" in data:
        health.uptime = str(data["uptime"])
    elif "data" in data and "uptime" in data.get("data", {}):
        health.uptime = str(data["data"]["uptime"])
    
    # Parse db_rw status
    if "db_rw" in data:
        health.db_rw = str(data["db_rw"])
    elif "data" in data and "db_rw" in data.get("data", {}):
        health.db_rw = str(data["data"]["db_rw"])
    
    # Parse tip age
    if "tip_age" in data:
        health.tip_age = str(data["tip_age"])
    elif "data" in data and "tip_age" in data.get("data", {}):
        health.tip_age = str(data["data"]["tip_age"])
    elif "data" in data and "tip" in data.get("data", {}):
        tip = data["data"]["tip"]
        if isinstance(tip, dict) and "age" in tip:
            health.tip_age = str(tip["age"])
    
    return health


def format_table(healths: List[NodeHealth]) -> str:
    # Header
    header = f"{'Host':<20} {'Port':<6} {'Status':<8} {'Version':<12} {'Uptime':<15} {'DB RW':<8} {'Tip Age':<15}"
    separator = "-" * len(header)
    
    lines = [header, separator]
    
    for h in healths:
        status = "ONLINE" if h.online else "OFFLINE"
        lines.append(
            f"{h.host:<20} {h.port:<6} {status:<8} {h.version:<12} {h.uptime:<15} {h.db_rw:<8} {h.tip_age:<15}"
        )
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="RustChain Health Check CLI")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed errors")
    args = parser.parse_args()
    
    results: List[NodeHealth] = []
    
    for host, port, use_https in ATTESTATION_NODES:
        health = check_node(host, port, use_https)
        results.append(health)
    
    if args.json:
        output = {
            "timestamp": utc_iso(),
            "nodes": []
        }
        for h in results:
            node_data = {
                "host": h.host,
                "port": h.port,
                "online": h.online,
                "version": h.version,
                "uptime": h.uptime,
                "db_rw": h.db_rw,
                "tip_age": h.tip_age,
            }
            if h.error:
                node_data["error"] = h.error
            output["nodes"].append(node_data)
        print(json.dumps(output, indent=2))
    else:
        print("RustChain Node Health Check")
        print(f"Timestamp: {utc_iso()}")
        print()
        print(format_table(results))
        
        if args.verbose:
            for h in results:
                if h.error:
                    print(f"\nError for {h.host}:{h.port}: {h.error}")
        
        # Summary
        online_count = sum(1 for h in results if h.online)
        print(f"\nSummary: {online_count}/{len(results)} nodes online")
    
    # Exit code: 0 if all online, 1 if any offline
    all_online = all(h.online for h in results)
    sys.exit(0 if all_online else 1)


if __name__ == "__main__":
    main()
