#!/usr/bin/env python3
"""
RustChain AI Agent Wallet CLI (bounty #30)

Generates an Ed25519 keypair for an agent, computes a hardware binding hash
from a fingerprint JSON blob, optionally mines a vanity nonce, and registers
the agent on a RustChain node via POST /agent/register.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests
from nacl.signing import SigningKey


def canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def hw_hash(fingerprint: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(fingerprint)).hexdigest()[:16]


def wallet_id(agent_name: str, hw: str, nonce: str) -> str:
    suffix = hashlib.sha256(f"{agent_name}|{hw}|{nonce}".encode()).hexdigest()[:6]
    return f"RTC-{agent_name}-{suffix}"


def mine_nonce(agent_name: str, hw: str, want_prefix: str, max_tries: int) -> Tuple[str, str]:
    want = (want_prefix or "").lower()
    if not want:
        return "0", wallet_id(agent_name, hw, "0")

    start = int(time.time())
    for i in range(max_tries):
        nonce = str(i)
        wid = wallet_id(agent_name, hw, nonce)
        if wid.lower().startswith(f"rtc-{agent_name.lower()}-{want}"):
            return nonce, wid
        if i and i % 50000 == 0:
            dt = max(1, int(time.time()) - start)
            rate = int(i / dt)
            print(f"[mine] tries={i} rate={rate}/s", file=sys.stderr)
    raise RuntimeError("vanity_not_found")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--node", default="https://50.28.86.131", help="RustChain node base URL")
    ap.add_argument("--insecure", action="store_true", help="Disable TLS verification (self-signed)")
    ap.add_argument("--agent", required=True, help="Agent name (3-20 alphanumeric)")
    ap.add_argument("--fingerprint", required=True, help="Path to hardware fingerprint JSON")
    ap.add_argument("--want", default="", help="Vanity suffix prefix to mine (e.g. a7f)")
    ap.add_argument("--max-tries", type=int, default=250000, help="Max nonce tries for vanity mining")
    ap.add_argument("--out", default="agent_wallet.json", help="Write keypair + wallet info to JSON file")
    args = ap.parse_args()

    fp_path = Path(args.fingerprint)
    fp = json.loads(fp_path.read_text(encoding="utf-8"))
    hw = hw_hash(fp)

    sk = SigningKey.generate()
    pub_hex = sk.verify_key.encode().hex()
    sk_hex = sk.encode().hex()

    nonce, wid = mine_nonce(args.agent, hw, args.want, args.max_tries)

    payload = {
        "agent_name": args.agent,
        "agent_pubkey_hex": pub_hex,
        "hardware_fingerprint": fp,
        "vanity_nonce": nonce,
    }

    r = requests.post(
        args.node.rstrip("/") + "/agent/register",
        json=payload,
        timeout=15,
        verify=(not args.insecure),
    )
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}

    print("status", r.status_code)
    print(json.dumps(data, indent=2, sort_keys=True))

    out = {
        "agent_name": args.agent,
        "wallet_id": wid,
        "hw_hash": hw,
        "vanity_nonce": nonce,
        "agent_pubkey_hex": pub_hex,
        "agent_seckey_hex": sk_hex,
    }
    Path(args.out).write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if r.status_code in (200, 201) else 1


if __name__ == "__main__":
    raise SystemExit(main())

