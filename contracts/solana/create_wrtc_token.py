#!/usr/bin/env python3
"""Create wRTC SPL Token on Solana — RIP-305 Cross-Chain Airdrop"""
import json, os, subprocess, sys

NETWORK = os.environ.get("SOLANA_NETWORK", "devnet")
DECIMALS = 6
TOKEN_NAME = "Wrapped RustChain Token"
TOKEN_SYMBOL = "wRTC"
TOKEN_DESCRIPTION = "Wrapped RTC from RustChain Proof-of-Antiquity blockchain"
TOKEN_IMAGE = "https://rustchain.org/elyan_logo.png"

def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result.stdout.strip()

def main():
    print(f"Creating wRTC SPL Token on Solana {NETWORK}")
    print("=" * 50)

    # Create token mint
    print("\n1. Creating token mint...")
    output = run(f"spl-token create-token --decimals {DECIMALS} --url {NETWORK}")
    mint_address = output.split("Creating token ")[1].split("\n")[0] if "Creating token" in output else "PARSE_ERROR"
    print(f"   Mint: {mint_address}")

    # Create token account
    print("\n2. Creating token account...")
    output = run(f"spl-token create-account {mint_address} --url {NETWORK}")
    print(f"   Account created")

    # Set metadata
    print("\n3. Setting token metadata...")
    metadata = {
        "name": TOKEN_NAME,
        "symbol": TOKEN_SYMBOL,
        "description": TOKEN_DESCRIPTION,
        "image": TOKEN_IMAGE,
        "external_url": "https://rustchain.org",
        "attributes": [
            {"trait_type": "chain", "value": "RustChain"},
            {"trait_type": "type", "value": "wrapped"},
            {"trait_type": "decimals", "value": str(DECIMALS)}
        ]
    }
    with open("wrtc_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"   Metadata saved to wrtc_metadata.json")

    # Mint initial supply (for testing)
    print("\n4. Minting test supply (1000 wRTC)...")
    run(f"spl-token mint {mint_address} 1000 --url {NETWORK}")

    print(f"\n{'=' * 50}")
    print(f"wRTC SPL Token Created!")
    print(f"Mint: {mint_address}")
    print(f"Network: {NETWORK}")
    print(f"Decimals: {DECIMALS}")

if __name__ == "__main__":
    main()
