#!/usr/bin/env python3
"""
RustChain Floppy Miner — Serial/Stdout Relay Bridge

Reads ATTEST: lines from stdin or serial port and forwards them
to the RustChain node via HTTPS.

Usage:
    # Pipe from DOSBox stdout
    dosbox -c "miner.com" | python relay.py

    # Serial port relay (real hardware)
    python relay.py --serial /dev/ttyUSB0 --baud 9600

    # Test mode
    echo 'ATTEST:{"miner":"test","nonce":1,"device":{"arch":"i486"}}' | python relay.py
"""

import argparse
import json
import ssl
import sys
import time
import urllib.request
import urllib.error

DEFAULT_NODE = "https://rustchain.org"
ATTEST_ENDPOINT = "/attest/submit"


def create_ssl_context():
    """Create SSL context that accepts self-signed certs."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def forward_attestation(node_url: str, payload: dict) -> dict:
    """Forward attestation payload to RustChain node."""
    url = f"{node_url}{ATTEST_ENDPOINT}"
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ctx = create_ssl_context()

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}", "body": e.read().decode()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def read_serial(port: str, baud: int):
    """Read lines from serial port. Requires pyserial."""
    try:
        import serial
    except ImportError:
        print("ERROR: pyserial not installed. Run: pip install pyserial", file=sys.stderr)
        sys.exit(1)

    ser = serial.Serial(port, baud, timeout=1)
    print(f"[RELAY] Listening on {port} @ {baud} baud")

    while True:
        line = ser.readline().decode("ascii", errors="replace").strip()
        if line:
            yield line


def read_stdin():
    """Read lines from stdin (piped from DOSBox)."""
    print("[RELAY] Reading from stdin (pipe from DOSBox or echo)")
    for line in sys.stdin:
        yield line.strip()


def main():
    parser = argparse.ArgumentParser(description="Floppy Miner Relay Bridge")
    parser.add_argument("--node", default=DEFAULT_NODE, help="RustChain node URL")
    parser.add_argument("--serial", default=None, help="Serial port (e.g., /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=9600, help="Serial baud rate")
    args = parser.parse_args()

    print(f"[RELAY] RustChain Floppy Miner Relay v1.0")
    print(f"[RELAY] Forwarding to {args.node}")

    source = read_serial(args.serial, args.baud) if args.serial else read_stdin()
    count = 0

    for line in source:
        if not line.startswith("ATTEST:"):
            continue

        json_str = line[7:]  # Strip "ATTEST:" prefix
        try:
            payload = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"[RELAY] Bad JSON: {e}", file=sys.stderr)
            continue

        count += 1
        print(f"[RELAY] #{count} Forwarding attestation from {payload.get('miner', '?')}")

        result = forward_attestation(args.node, payload)
        status = "OK" if result.get("ok") else "FAIL"
        print(f"[RELAY] #{count} Result: {status} — {result.get('message', result.get('error', ''))}")


if __name__ == "__main__":
    main()
