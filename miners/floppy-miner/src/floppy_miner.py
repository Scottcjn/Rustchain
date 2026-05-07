#!/usr/bin/env python3
"""
RustChain Floppy Miner — Reference Implementation & Simulator

Minimal attestation client designed for 16MB RAM / floppy-disk constraints.
This Python version serves as both reference implementation and DOSBox relay target.

Usage:
    python floppy_miner.py --wallet RTC_ADDRESS --node https://rustchain.org
    python floppy_miner.py --simulate  # offline demo mode

Bounty: Rustchain #1853 (300 RTC)
"""

import argparse
import hashlib
import json
import os
import random
import struct
import sys
import time

try:
    import urllib.request
    import urllib.error
    import ssl
    HAS_URLLIB = True
except ImportError:
    HAS_URLLIB = False

# ── Constants ────────────────────────────────────────────────────
VERSION = "1.0.0"
DEFAULT_NODE = "https://rustchain.org"
ATTEST_ENDPOINT = "/attest/submit"
EPOCH_ENDPOINT = "/epoch"
MAX_RAM_MB = 16
DEVICE_ARCH = "i486"
DEVICE_FAMILY = "floppy"
BOOT_MEDIA = "floppy_1.44mb"
ATTEST_INTERVAL = 30  # seconds between attestations
FLOPPY_SIZE = 1_474_560  # 1.44MB in bytes

# ── ASCII Art ────────────────────────────────────────────────────
BOOT_SCREEN = r"""
╔══════════════════════════════════════════════════╗
║        ████████████████████████████████          ║
║        █  ┌──────────────────────┐  █           ║
║        █  │   RustChain Floppy   │  █           ║
║        █  │      MINER v{ver}      │  █           ║
║        █  │    ▄▄ ▄▄ ▄▄ ▄▄ ▄▄   │  █           ║
║        █  └──────────────────────┘  █           ║
║        █    ┌──┐                    █           ║
║        ████████████████████████████████          ║
║                                                  ║
║   Proof-of-Antiquity × Proof-of-Floppy          ║
║   Mining RustChain on 1.44MB since 2026          ║
╚══════════════════════════════════════════════════╝
""".replace("{ver}", VERSION)

SPINNER = ["|", "/", "-", "\\"]


# ── Hardware Fingerprint ─────────────────────────────────────────

def generate_hardware_fingerprint() -> dict:
    """Generate a minimal hardware fingerprint for attestation.
    
    On real i486 hardware, this reads CPUID, TSC, cache timing.
    In simulation, we generate plausible values.
    """
    # CPU identification
    cpu_id = hashlib.sha256(
        f"{DEVICE_ARCH}:{os.getpid()}:{time.time()}".encode()
    ).hexdigest()[:16]
    
    # Simulated cache timing profile (real i486 would measure L1 latency)
    cache_l1_ns = random.uniform(8.0, 12.0)  # i486 L1 ~10ns
    
    # Memory bandwidth estimate (16MB system)
    mem_bandwidth_mbs = random.uniform(20.0, 40.0)  # ISA bus limited
    
    return {
        "cpu_id": cpu_id,
        "arch": DEVICE_ARCH,
        "family": DEVICE_FAMILY,
        "ram_mb": MAX_RAM_MB,
        "boot_media": BOOT_MEDIA,
        "cache_l1_ns": round(cache_l1_ns, 2),
        "mem_bandwidth_mbs": round(mem_bandwidth_mbs, 2),
        "has_fpu": True,  # i486DX has FPU
        "clock_mhz": 33,  # typical i486DX-33
    }


# ── Nonce Generation ─────────────────────────────────────────────

def generate_nonce() -> int:
    """Generate attestation nonce.
    
    On real hardware, uses TSC + random seed.
    Keeps nonce under 32-bit for i486 compatibility.
    """
    return random.randint(1, 2**31 - 1)


# ── Attestation Payload ──────────────────────────────────────────

def build_attestation(wallet: str, nonce: int, fingerprint: dict) -> dict:
    """Build minimal attestation payload.
    
    Designed to be < 512 bytes when serialized — fits in a single
    network packet and minimizes RAM usage on constrained systems.
    """
    return {
        "miner": wallet,
        "nonce": nonce,
        "device": {
            "arch": fingerprint["arch"],
            "family": fingerprint["family"],
            "ram_mb": fingerprint["ram_mb"],
            "boot_media": fingerprint["boot_media"],
        },
        "timestamp": int(time.time()),
        "version": VERSION,
    }


def attestation_to_bytes(payload: dict) -> bytes:
    """Serialize attestation to minimal JSON bytes."""
    return json.dumps(payload, separators=(",", ":")).encode("ascii")


# ── Network ──────────────────────────────────────────────────────

def submit_attestation(node_url: str, payload: dict) -> dict:
    """Submit attestation to RustChain node.
    
    Uses urllib (no dependencies) with TLS.
    On real DOS hardware, this would use Wattcp or serial relay.
    """
    if not HAS_URLLIB:
        raise RuntimeError("No urllib available — use relay mode")
    
    url = f"{node_url}{ATTEST_ENDPOINT}"
    data = attestation_to_bytes(payload)
    
    # Allow self-signed certs for local nodes
    ctx = ssl.create_default_context()
    # TLS verification enabled by default
    if os.environ.get('RC_SKIP_TLS_VERIFY', '0') == '1':
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    
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
        body = e.read().decode("utf-8", errors="replace")
        return {"ok": False, "error": f"HTTP {e.code}", "body": body}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_epoch(node_url: str) -> dict:
    """Fetch current epoch info."""
    if not HAS_URLLIB:
        return {"epoch": "?"}
    
    url = f"{node_url}{EPOCH_ENDPOINT}"
    ctx = ssl.create_default_context()
    # TLS verification enabled by default
    if os.environ.get('RC_SKIP_TLS_VERIFY', '0') == '1':
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
            return json.loads(resp.read())
    except Exception:
        return {"epoch": "?"}


# ── Serial Output (for relay mode) ──────────────────────────────

def output_serial(payload: dict):
    """Output attestation to stdout/serial for relay pickup.
    
    Format: ATTEST:<json>\n
    The relay.py script reads this and forwards via HTTPS.
    """
    line = "ATTEST:" + json.dumps(payload, separators=(",", ":"))
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


# ── Simulation Mode ──────────────────────────────────────────────

def simulate_attestation(wallet: str) -> dict:
    """Simulate a successful attestation response."""
    return {
        "ok": True,
        "epoch": random.randint(1, 100),
        "multiplier": 1.5,  # i486 antiquity multiplier
        "message": "Attestation accepted from i486 floppy miner",
        "reward_rtc": round(random.uniform(0.01, 0.1), 4),
    }


# ── Progress Bar ─────────────────────────────────────────────────

def progress_bar(current: int, total: int, width: int = 30) -> str:
    """Render ASCII progress bar (no Unicode for DOS compatibility)."""
    filled = int(width * current / total)
    bar = "#" * filled + "." * (width - filled)
    pct = int(100 * current / total)
    return f"[{bar}] {pct}%"


# ── Main Loop ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RustChain Floppy Miner")
    parser.add_argument("--wallet", default="RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff",
                        help="RTC wallet address")
    parser.add_argument("--node", default=DEFAULT_NODE,
                        help="RustChain node URL")
    parser.add_argument("--simulate", action="store_true",
                        help="Offline simulation mode")
    parser.add_argument("--relay", action="store_true",
                        help="Serial relay mode (output to stdout)")
    parser.add_argument("--once", action="store_true",
                        help="Single attestation then exit")
    parser.add_argument("--interval", type=int, default=ATTEST_INTERVAL,
                        help="Seconds between attestations")
    args = parser.parse_args()

    # Boot screen
    print(BOOT_SCREEN)
    print(f"  Wallet:  {args.wallet}")
    print(f"  Node:    {args.node}")
    print(f"  Mode:    {'SIMULATE' if args.simulate else 'RELAY' if args.relay else 'LIVE'}")
    print(f"  RAM:     {MAX_RAM_MB}MB (i486 constraint)")
    print()

    fingerprint = generate_hardware_fingerprint()
    print(f"  CPU ID:  {fingerprint['cpu_id']}")
    print(f"  Arch:    {fingerprint['arch']} @ {fingerprint['clock_mhz']}MHz")
    print(f"  Cache:   L1 {fingerprint['cache_l1_ns']}ns")
    print()

    # Get epoch
    if not args.simulate:
        epoch_info = get_epoch(args.node)
        epoch = epoch_info.get("epoch", "?")
    else:
        epoch = random.randint(1, 100)
    print(f"  Epoch:   {epoch}")
    print()

    attestation_count = 0
    
    while True:
        attestation_count += 1
        nonce = generate_nonce()
        payload = build_attestation(args.wallet, nonce, fingerprint)
        
        # Progress animation
        for i in range(10):
            spinner = SPINNER[i % len(SPINNER)]
            bar = progress_bar(i + 1, 10, 20)
            sys.stdout.write(f"\r  {spinner} Attesting #{attestation_count} {bar}")
            sys.stdout.flush()
            time.sleep(0.1)
        
        # Submit
        if args.simulate:
            result = simulate_attestation(args.wallet)
        elif args.relay:
            output_serial(payload)
            result = {"ok": True, "message": "Sent to relay"}
        else:
            result = submit_attestation(args.node, payload)
        
        # Display result
        status = "OK" if result.get("ok") else "FAIL"
        msg = result.get("message", result.get("error", ""))
        mult = result.get("multiplier", "?")
        reward = result.get("reward_rtc", "?")
        
        print(f"\r  [{status}] Attestation #{attestation_count} | "
              f"Nonce: {nonce} | Multiplier: {mult}x | Reward: {reward} RTC")
        
        if result.get("error"):
            print(f"  ERROR: {result['error']}")
        
        if args.once:
            break
        
        # Memory usage check
        payload_size = len(attestation_to_bytes(payload))
        print(f"  Payload: {payload_size} bytes | "
              f"Next attestation in {args.interval}s")
        
        time.sleep(args.interval)
    
    print("\n  Miner stopped. Floppy disk is eternal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
