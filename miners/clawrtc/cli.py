#!/usr/bin/env python3
"""ClawRTC CLI — wallet unbind command for hardware binding reset.

Provides the `wallet unbind` subcommand that allows users to release
their hardware binding so they can re-register with a different wallet.

See: https://github.com/Scottcjn/Rustchain/issues/969
"""

import json
import os
import sys
import textwrap

__all__ = ["safe_print", "WALLET_DIR", "WALLET_FILE"]

INSTALL_DIR = os.path.join(os.path.expanduser("~"), ".clawrtc")
WALLET_DIR = os.path.join(INSTALL_DIR, "wallets")
WALLET_FILE = os.path.join(WALLET_DIR, "default.json")

NODE_URL = "https://rustchain.org"

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


def _wallet_unbind(args):
    """Release hardware binding so the user can re-register with a new wallet.

    Calls POST /wallet/hardware/unbind on the RustChain node. The user must
    provide their current wallet address to prove ownership of the binding.

    See: https://github.com/Scottcjn/Rustchain/issues/969
    """
    wallet = None
    if os.path.exists(WALLET_FILE):
        try:
            with open(WALLET_FILE) as f:
                wallet = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    if not wallet:
        safe_print(f"\n  {YELLOW}No RTC wallet found.{NC}")
        safe_print(f"  Create one: clawrtc wallet create\n")
        return

    address = wallet.get("address", "")
    if not address:
        safe_print(f"{RED}[ERROR] Wallet file is missing the 'address' field.{NC}")
        return

    safe_print(f"\n{CYAN}[clawrtc]{NC} Unbinding hardware for wallet {BOLD}{address}{NC}...")
    safe_print(f"  {DIM}This will remove all hardware bindings for this wallet.{NC}")
    safe_print(f"  {DIM}You will need to re-attest to bind to new hardware.{NC}\n")

    try:
        import urllib.request
        import ssl

        payload = json.dumps({"wallet_address": address}).encode("utf-8")
        req = urllib.request.Request(
            f"{NODE_URL}/wallet/hardware/unbind",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            result = json.loads(resp.read().decode())

        if result.get("ok"):
            removed = result.get("removed", 0)
            safe_print(f"  {GREEN}SUCCESS{NC} — Removed {removed} hardware binding(s)")
            safe_print(f"  {DIM}You can now mine with a different wallet on this machine.{NC}")
            safe_print(f"  {DIM}Re-attest with: clawrtc start{NC}\n")
        else:
            error = result.get("error", "unknown")
            message = result.get("message", "")
            safe_print(f"  {RED}FAILED{NC}: {error}")
            if message:
                safe_print(f"  {DIM}{message}{NC}")
            safe_print()

    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
            msg = body.get("message", body.get("error", str(e)))
        except Exception:
            msg = str(e)
        safe_print(f"  {RED}ERROR{NC} (HTTP {e.code}): {msg}\n")
    except Exception as e:
        safe_print(f"  {RED}ERROR{NC}: {e}\n")
