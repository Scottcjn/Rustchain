#!/usr/bin/env python3
"""
RustChain Linux Miner — Proof of Antiquity

Usage:
    python rustchain_linux_miner.py [--dry-run] [--show-payload] [--no-persist-key]

Flags:
    --dry-run          Simulate mining without modifying network state.
    --show-payload     Display the full payload that would be submitted.
    --no-persist-key   Do not persist the miner keypair to disk (ephemeral only).
"""

import argparse
import json
import os
import sys
import time
import hashlib
import platform
import subprocess
import tempfile
import shutil
from pathlib import Path

# Attempt to import cryptography
HAVE_CRYPTO = False
try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization
    HAVE_CRYPTO = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RUSTCHAIN_DIR = Path.home() / ".rustchain"
MINER_KEY_FILE = RUSTCHAIN_DIR / "miner_key.json"

# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------

def generate_ephemeral_keypair():
    """Generate an in-memory Ed25519 keypair. Returns (private_bytes, public_bytes)."""
    if not HAVE_CRYPTO:
        print("[ERROR] cryptography library not installed. Cannot generate keypair.")
        sys.exit(1)
    private_key = ed25519.Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    public_key = private_key.public_key()
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    return private_bytes, public_bytes


def load_or_create_keypair(persist=True):
    """
    Load existing keypair from disk, or create a new one.
    If persist=False, never write to disk; use ephemeral key.
    Returns (private_bytes, public_bytes).
    """
    if not HAVE_CRYPTO:
        print("[ERROR] cryptography library not installed. Cannot load/create keypair.")
        sys.exit(1)

    if persist and MINER_KEY_FILE.exists():
        try:
            with open(MINER_KEY_FILE, "r") as f:
                data = json.load(f)
            private_hex = data.get("private_key")
            public_hex = data.get("public_key")
            if private_hex and public_hex:
                private_bytes = bytes.fromhex(private_hex)
                public_bytes = bytes.fromhex(public_hex)
                print(f"[CRYPTO] Loaded existing keypair from {MINER_KEY_FILE}")
                return private_bytes, public_bytes
        except Exception as e:
            print(f"[WARN] Failed to load keypair from {MINER_KEY_FILE}: {e}")

    # Generate new keypair
    private_bytes, public_bytes = generate_ephemeral_keypair()

    if persist:
        # Ensure directory exists
        RUSTCHAIN_DIR.mkdir(parents=True, exist_ok=True)
        key_data = {
            "private_key": private_bytes.hex(),
            "public_key": public_bytes.hex(),
            "algorithm": "Ed25519",
            "created_at": time.time()
        }
        with open(MINER_KEY_FILE, "w") as f:
            json.dump(key_data, f, indent=2)
        print(f"[CRYPTO] Keypair saved to {MINER_KEY_FILE}")
    else:
        print("[CRYPTO] Using ephemeral in-memory keypair (not persisted)")

    return private_bytes, public_bytes


# ---------------------------------------------------------------------------
# Dry-run / simulation logic
# ---------------------------------------------------------------------------

def simulate_mining(private_bytes, public_bytes, show_payload=False):
    """
    Simulate the mining process without modifying any state.
    """
    print("[DRY-RUN] Starting dry-run simulation...")
    print(f"[DRY-RUN] Public key (hex): {public_bytes.hex()}")

    # Simulate some work
    for i in range(3):
        time.sleep(0.1)
        print(f"[DRY-RUN] Step {i+1}/3 complete")

    if show_payload:
        payload = {
            "public_key": public_bytes.hex(),
            "timestamp": time.time(),
            "nonce": 123456,
            "signature": "simulated_signature_hex",
            "dry_run": True
        }
        print(f"[DRY-RUN] Payload that would be submitted:")
        print(json.dumps(payload, indent=2))

    print("[DRY-RUN] No mining or network state will be modified")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="RustChain Linux Miner — Proof of Antiquity"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate mining without modifying network state"
    )
    parser.add_argument(
        "--show-payload",
        action="store_true",
        help="Display the full payload that would be submitted"
    )
    parser.add_argument(
        "--no-persist-key",
        action="store_true",
        help="Do not persist the miner keypair to disk (ephemeral only)"
    )

    args = parser.parse_args()

    # Determine if we should persist the keypair
    persist_key = not args.no_persist_key

    # If dry-run and no-persist-key is not explicitly set, default to ephemeral
    if args.dry_run and not args.no_persist_key:
        # Option 1 from issue: use ephemeral key during dry-run
        persist_key = False

    # Load or create keypair
    private_bytes, public_bytes = load_or_create_keypair(persist=persist_key)

    if args.dry_run:
        simulate_mining(private_bytes, public_bytes, show_payload=args.show_payload)
    else:
        # Normal mining mode (not dry-run)
        print("[INFO] Starting normal mining mode...")
        # In a real miner, this would loop and submit work
        print(f"[INFO] Public key: {public_bytes.hex()}")
        print("[INFO] Mining would start here (not implemented in this simulation)")


if __name__ == "__main__":
    main()
