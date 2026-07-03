#!/usr/bin/env python3
"""ClawRTC CLI — wallet create with Windows-safe Unicode output.

This module provides the _wallet_create helper with a safe_print wrapper
that prevents UnicodeEncodeError on Windows consoles using legacy code
pages (e.g. cp850).

See: https://github.com/Scottcjn/Rustchain/issues/6899
"""

import json
import os
import sys
import textwrap
import time

__all__ = ["safe_print", "WALLET_DIR", "WALLET_FILE"]

INSTALL_DIR = os.path.join(os.path.expanduser("~"), ".clawrtc")
WALLET_DIR = os.path.join(INSTALL_DIR, "wallets")
WALLET_FILE = os.path.join(WALLET_DIR, "default.json")

# ANSI colors
CYAN = "\033[36m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
DIM = "\033[2m"
NC = "\033[0m"


def safe_print(text: str) -> None:
    """Print text safely, handling UnicodeEncodeError on legacy Windows consoles.

    On Windows with legacy code pages (e.g. cp850), Unicode box-drawing
    characters like ═══, ╔, ║, ╚ cannot be encoded. This function catches
    the error and falls back to an ASCII-safe representation.

    See: https://github.com/Scottcjn/Rustchain/issues/6899
    """
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        try:
            print(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))
        except Exception:
            print(text.encode("ascii", errors="replace").decode("ascii", errors="replace"))


def _wallet_create(args):
    """Generate a new Ed25519 RTC wallet with Windows-safe output."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        safe_print(f"{RED}[ERROR] cryptography package required. Install: pip install cryptography{NC}")
        return

    # Check for existing wallet
    if os.path.exists(WALLET_FILE) and not getattr(args, "force", False):
        try:
            with open(WALLET_FILE) as f:
                existing = json.load(f)
            safe_print(f"\n  {YELLOW}You already have an RTC wallet:{NC}")
            safe_print(f"  {GREEN}{BOLD}{existing['address']}{NC}\n")
            safe_print(f"  To create a new one (REPLACES existing), use:")
            safe_print(f"    clawrtc wallet create --force\n")
            return
        except (json.JSONDecodeError, KeyError):
            pass

    # Generate Ed25519 keypair
    safe_print(f"{CYAN}[clawrtc]{NC} Generating Ed25519 keypair...")
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    priv_bytes = private_key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    pub_bytes = public_key.public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )

    # Derive RTC address: RTC + sha256(pubkey)[:40]
    import hashlib
    address = "RTC" + hashlib.sha256(pub_bytes).hexdigest()[:40]

    wallet_data = {
        "address": address,
        "public_key": pub_bytes.hex(),
        "private_key": priv_bytes.hex(),
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "curve": "Ed25519",
        "network": "rustchain-mainnet",
    }

    # Save to disk
    os.makedirs(WALLET_DIR, exist_ok=True)
    with open(WALLET_FILE, "w") as f:
        json.dump(wallet_data, f, indent=2)
    os.chmod(WALLET_FILE, 0o600)

    # Also update the .wallet file so the miner uses this address
    wallet_marker = os.path.join(INSTALL_DIR, ".wallet")
    with open(wallet_marker, "w") as f:
        f.write(address)

    # Windows-safe banner — wraps in try/except for legacy code pages (#6899)
    banner = textwrap.dedent(f"""
    {GREEN}{BOLD}{"=" * 59}
      RTC WALLET CREATED
    {"=" * 59}{NC}

      {GREEN}Address (PUBLIC - paste this in bounty claims):{NC}
      {BOLD}{address}{NC}

      {RED}Private key saved to:{NC}
      {DIM}{WALLET_FILE}{NC}

    {RED}{BOLD}  +-------------------------------------------------------+
    |  SAVE YOUR PRIVATE KEY - IT CANNOT BE RECOVERED!  |
    |  Back up {WALLET_FILE}    |
    |  Anyone with this key can spend your RTC.         |
    +-------------------------------------------------------+{NC}

      {CYAN}Next steps:{NC}
        1. Copy your {BOLD}RTC...{NC} address above
        2. Paste it in GitHub bounty claims
        3. Start mining: clawrtc start
        4. Check balance: clawrtc wallet show

      {DIM}This is NOT a Solana/ETH/BTC address.
      For wRTC on Solana, bridge at https://bottube.ai/bridge{NC}
    """)
    safe_print(banner)
