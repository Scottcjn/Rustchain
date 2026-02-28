#!/usr/bin/env python3
"""Server-side PoW proof adapters (focused, verifiable)."""

from __future__ import annotations

import json
from typing import Dict, Tuple, Any
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


def _json_get(url: str, timeout: float = 3.0, headers: Dict[str, str] | None = None) -> Dict[str, Any]:
    req = Request(url, headers=headers or {})
    with urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return json.loads(body)


def verify_ergo_node_rpc(evidence: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], str]:
    """Verify Ergo node mining proof via local node RPC."""
    endpoint = evidence.get("endpoint") or "http://127.0.0.1:9053/info"
    expected_is_mining = bool(evidence.get("is_mining", True))
    try:
        data = _json_get(endpoint, timeout=float(evidence.get("timeout_sec", 3.0)))
    except (URLError, HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as e:
        return False, {}, f"ergo_node_unreachable:{e}"

    is_mining = bool(data.get("isMining", False))
    height = int(data.get("fullHeight", 0) or 0)
    peers = int(data.get("peersCount", 0) or 0)
    best = data.get("bestFullHeaderId") or data.get("bestHeaderId") or ""

    if expected_is_mining and not is_mining:
        return False, {"isMining": is_mining, "height": height, "peers": peers}, "ergo_not_mining"
    if height <= 0:
        return False, {"isMining": is_mining, "height": height, "peers": peers}, "ergo_invalid_height"

    expected_best = (evidence.get("best_block_hash") or "").strip()
    if expected_best and best and expected_best != best:
        return False, {"isMining": is_mining, "height": height, "peers": peers, "best": best}, "ergo_best_block_mismatch"

    return True, {"isMining": is_mining, "height": height, "peers": peers, "best": best}, ""


def verify_ergo_pool(evidence: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], str]:
    """Verify pool-side hashrate/account presence for Ergo mining."""
    pool_url = (evidence.get("pool_api_url") or "").strip()
    if not pool_url:
        return False, {}, "missing_pool_api_url"

    try:
        data = _json_get(pool_url, timeout=float(evidence.get("timeout_sec", 3.0)))
    except (URLError, HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as e:
        return False, {}, f"ergo_pool_unreachable:{e}"

    # Tolerant extraction across common pool API styles
    hashrate = 0.0
    for k in ("hashrate", "currentHashrate", "reportedHashrate"):
        v = data.get(k)
        if v is not None:
            try:
                hashrate = float(v)
                break
            except Exception:
                pass

    if hashrate <= 0:
        nested = data.get("data") if isinstance(data.get("data"), dict) else {}
        for k in ("hashrate", "currentHashrate", "reportedHashrate"):
            v = nested.get(k)
            if v is not None:
                try:
                    hashrate = float(v)
                    break
                except Exception:
                    pass

    if hashrate <= 0:
        return False, {"hashrate": hashrate}, "ergo_pool_no_hashrate"

    miner = (evidence.get("miner") or evidence.get("wallet") or "").strip()
    if miner:
        blob = json.dumps(data, ensure_ascii=False)
        if miner not in blob:
            return False, {"hashrate": hashrate}, "ergo_pool_miner_not_found"

    return True, {"hashrate": hashrate}, ""


def verify_monero_node_rpc(evidence: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], str]:
    """Verify Monero node proof via JSON-RPC get_info."""
    endpoint = evidence.get("endpoint") or "http://127.0.0.1:18081/json_rpc"
    timeout = float(evidence.get("timeout_sec", 3.0))
    payload = {
        "jsonrpc": "2.0",
        "id": "0",
        "method": evidence.get("method") or "get_info",
        "params": evidence.get("params") or {},
    }
    body = json.dumps(payload).encode("utf-8")
    req = Request(endpoint, data=body, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (URLError, HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as e:
        return False, {}, f"monero_node_unreachable:{e}"

    result = data.get("result") if isinstance(data, dict) else None
    if not isinstance(result, dict):
        return False, {"raw": data}, "monero_invalid_rpc_result"

    synchronized = bool(result.get("synchronized", True))
    height = int(result.get("height", 0) or 0)
    incoming = int(result.get("incoming_connections_count", 0) or 0)
    outgoing = int(result.get("outgoing_connections_count", 0) or 0)

    if not synchronized:
        return False, {"synchronized": synchronized, "height": height}, "monero_not_synced"
    if height <= 0:
        return False, {"synchronized": synchronized, "height": height}, "monero_invalid_height"

    return True, {
        "synchronized": synchronized,
        "height": height,
        "incoming_connections": incoming,
        "outgoing_connections": outgoing,
    }, ""


def verify_monero_pool(evidence: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], str]:
    """Verify Monero pool hashrate/account evidence."""
    pool_url = (evidence.get("pool_api_url") or "").strip()
    if not pool_url:
        return False, {}, "missing_pool_api_url"

    try:
        data = _json_get(pool_url, timeout=float(evidence.get("timeout_sec", 3.0)))
    except (URLError, HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as e:
        return False, {}, f"monero_pool_unreachable:{e}"

    hashrate = 0.0
    for k in ("hashrate", "currentHashrate", "reportedHashrate"):
        v = data.get(k)
        if v is not None:
            try:
                hashrate = float(v)
                break
            except Exception:
                pass

    if hashrate <= 0 and isinstance(data.get("data"), dict):
        for k in ("hashrate", "currentHashrate", "reportedHashrate"):
            v = data["data"].get(k)
            if v is not None:
                try:
                    hashrate = float(v)
                    break
                except Exception:
                    pass

    if hashrate <= 0:
        return False, {"hashrate": hashrate}, "monero_pool_no_hashrate"

    miner = (evidence.get("miner") or evidence.get("wallet") or "").strip()
    if miner:
        blob = json.dumps(data, ensure_ascii=False)
        if miner not in blob:
            return False, {"hashrate": hashrate}, "monero_pool_miner_not_found"

    return True, {"hashrate": hashrate}, ""
