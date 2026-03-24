# rustchain-wallet-wrap.py
# A wrapper tool to embed RustChain PoA fingerprint metadata into Ergo-compatible wallet JSON

import json
import argparse
import base64
import hashlib
import os

def load_wallet(wallet_path):
    try:
        with open(wallet_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"[!] Error loading wallet: {e}")
        exit(1)

def embed_poa_metadata(wallet_data, fingerprint_path):
    try:
        with open(fingerprint_path, 'r') as f:
            fingerprint = f.read().strip()
    except Exception as e:
        print(f"[!] Error reading fingerprint file: {e}")
        exit(1)

    fingerprint_b64 = base64.b64encode(fingerprint.encode()).decode()
    fingerprint_hash = hashlib.sha256(fingerprint.encode()).hexdigest()

    poa_meta = {
        "fingerprint_b64": fingerprint_b64,
        "fingerprint_sha256": fingerprint_hash,
        "message": "Embedded by RustChain PoA wrapper",
        "validated": True
    }

    wallet_data["rustchain_poa"] = poa_meta
    return wallet_data

def save_wallet(wallet_data, output_path):
    try:
        with open(output_path, 'w') as f:
            json.dump(wallet_data, f, indent=2)
        print(f"[✓] Updated wallet saved to: {output_path}")
    except Exception as e:
        print(f"[!] Error saving wallet: {e}")
        exit(1)

def main():
    parser = argparse.ArgumentParser(description="RustChain Wallet PoA Metadata Wrapper")
    parser.add_argument('--wallet', required=True, help="Path to Ergo wallet JSON file")
    parser.add_argument('--fingerprint', required=True, help="Path to PoA fingerprint text")
    parser.add_argument('--output', default="wallet_poa.json", help="Output wallet path (default: wallet_poa.json)")

    args = parser.parse_args()

    wallet_data = load_wallet(args.wallet)
    updated_wallet = embed_poa_metadata(wallet_data, args.fingerprint)
    save_wallet(updated_wallet, args.output)

if __name__ == "__main__":
    main()
