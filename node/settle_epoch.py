#!/usr/bin/env python3
"""Trigger settlement of the previous epoch on the local node.

Exit status matters: this script is run unattended (cron/systemd timer), and
the only signal the scheduler gets is the exit code. Before this it exited 0
on every failure — node unreachable, malformed /epoch, HTTP 500 from
/rewards/settle — so a broken settlement pipeline looked healthy for months.
Now: 0 only when /rewards/settle returned 200 with a JSON object that does not
say ``ok: false``; 1 otherwise. Logging is unchanged (stdout), plus a final
SETTLEMENT FAILED line on the failure path.
"""
import os
import sys

import requests
import time

NODE_URL = os.environ.get("RC_NODE_URL", "http://localhost:8099")

EXIT_OK = 0
EXIT_SETTLEMENT_FAILED = 1

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
    """Returns the settle response JSON (dict) on HTTP 200, the truncated
    response text (str) on any other status, or None if anything raised."""
    try:
        resp = requests.get(f"{NODE_URL}/epoch", timeout=10)
        epoch_info = resp.json()
        prev_epoch = _previous_settleable_epoch(epoch_info)

        resp = requests.post(f"{NODE_URL}/rewards/settle",
                           json={"epoch": prev_epoch},
                           timeout=60)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] Settlement for epoch {prev_epoch}: {resp.status_code}")
        if resp.status_code == 200:
            return resp.json()
        return resp.text[:200]
    except Exception as e:
        print(f"Error: {e}")
        return None

def settlement_succeeded(result) -> bool:
    """True only for a 200 JSON-object response that does not report ok=false.

    None  -> an exception (unreachable node, bad /epoch shape) -> failure.
    str   -> non-200 status (text body)                         -> failure.
    dict  -> success unless the node itself says {"ok": false}.
    """
    if not isinstance(result, dict):
        return False
    return result.get("ok", True) is not False

def main() -> int:
    result = trigger_settlement()
    print(result)
    if settlement_succeeded(result):
        return EXIT_OK
    print("SETTLEMENT FAILED (non-zero exit so the scheduler notices)", file=sys.stderr)
    return EXIT_SETTLEMENT_FAILED

if __name__ == "__main__":
    sys.exit(main())
