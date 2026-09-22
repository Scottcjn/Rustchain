#!/usr/bin/env python3
"""
Bridge RTC to wRTC and consolidate wallets.

This script uses the `rustchain` CLI to perform the following steps:

1. Bridge 70 RTC from the main wallet to the wRTC contract on Solana.
2. Transfer 20 RTC from the truncated wallet to the main wallet.
3. Transfer 30 RTC from the alias wallet to the main wallet.

Environment variables required:
- MAIN_WALLET: Address of the main wallet.
- TRUNCATED_WALLET: Address of the truncated wallet.
- ALIAS_WALLET: Address of the alias wallet.
- SOLANA_WALLET: Destination Solana wallet for wRTC.
- RUSTCHAIN_CLI: Path or name of the rustchain CLI binary (defaults to `rustchain`).
"""

import os
import subprocess
import sys
from typing import List


def run_cmd(cmd: List[str]) -> str:
    """Run a shell command and return its stdout."""
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def transfer(from_wallet: str, to_wallet: str, amount: float, token: str = "RTC") -> None:
    """Transfer tokens using the rustchain CLI."""
    cmd = [
        os.getenv("RUSTCHAIN_CLI", "rustchain"),
        "transfer",
        "--from",
        from_wallet,
        "--to",
        to_wallet,
        "--amount",
        str(amount),
        "--token",
        token,
    ]
    print(f"Executing: {' '.join(cmd)}")
    output = run_cmd(cmd)
    print(output)


def bridge_to_wrtc(wallet: str, amount: float, solana_wallet: str) -> None:
    """Bridge RTC to wRTC on Solana."""
    cmd = [
        os.getenv("RUSTCHAIN_CLI", "rustchain"),
        "bridge",
        "--from",
        wallet,
        "--to",
        solana_wallet,
        "--amount",
        str(amount),
        "--token",
        "RTC",
        "--destination",
        "wRTC",
    ]
    print(f"Executing: {' '.join(cmd)}")
    output = run_cmd(cmd)
    print(output)


def main() -> None:
    main_wallet = os.getenv("MAIN_WALLET")
    truncated_wallet = os.getenv("TRUNCATED_WALLET")
    alias_wallet = os.getenv("ALIAS_WALLET")
    solana_wallet = os.getenv("SOLANA_WALLET")

    if not all([main_wallet, truncated_wallet, alias_wallet, solana_wallet]):
        print("Error: Missing required environment variables.")
        sys.exit(1)

    # 1. Bridge 70 RTC from main wallet to wRTC on Solana
    bridge_to_wrtc(main_wallet, 70.0, solana_wallet)

    # 2. Consolidate 20 RTC from truncated wallet to main wallet
    transfer(truncated_wallet, main_wallet, 20.0)

    # 3. Consolidate 30 RTC from alias wallet to main wallet
    transfer(alias_wallet, main_wallet, 30.0)


if __name__ == "__main__":
    main()
