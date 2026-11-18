#!/usr/bin/env python3
import os
import sys
import requests
import time

NODE_URL = os.environ.get("RUSTCHAIN_NODE_URL", "http://localhost:8099").rstrip("/")

def _previous_settleable_epoch(epoch_info):
    if not isinstance(epoch_info, dict):
        raise ValueError("/epoch response must be a JSON object")

    current_epoch = epoch_info.get("epoch")
    if not isinstance(current_epoch, int) or isinstance(current_epoch, bool):
        raise ValueError("/epoch response field 'epoch' must be an integer")
    if current_epoch <= 0:
        raise ValueError("/epoch response field 'epoch' must be greater than zero")

    return current_epoch - 1

def trigger_settlement():
    try:
        resp = requests.get(f"{NODE_URL}/epoch", timeout=10)
        resp.raise_for_status()
        epoch_info = resp.json()
        prev_epoch = _previous_settleable_epoch(epoch_info)

        headers = {}
        admin_key = os.environ.get("RC_ADMIN_KEY") or os.environ.get("RC_SETTLE_KEY") or ""
        if admin_key:
            headers["X-Admin-Key"] = admin_key

        resp = requests.post(
            f"{NODE_URL}/rewards/settle",
            json={"epoch": prev_epoch},
            headers=headers,
            timeout=60,
        )
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] Settlement for epoch {prev_epoch}: {resp.status_code}")
        if resp.status_code != 200:
            print(f"Error: HTTP {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
            return None
        payload = resp.json()
        if not isinstance(payload, dict) or not payload.get("ok"):
            print(f"Error: settlement refused: {payload}", file=sys.stderr)
            return None
        return payload
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return None

if __name__ == "__main__":
    result = trigger_settlement()
    print(result)
    sys.exit(0 if isinstance(result, dict) and result.get("ok") else 1)
