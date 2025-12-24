#!/usr/bin/env python3
"""
RustChain Node Wallet System
============================
Each node gets a unique wallet for receiving node operator rewards.
Wallet is deterministic based on node_id, stored locally.
"""

import hashlib
import os
import json
import socket
from pathlib import Path

# Node wallet storage
NODE_WALLET_FILE = os.path.expanduser("~/.rustchain_node_wallet.json")

def generate_node_wallet(node_id: str) -> dict:
    """
    Generate deterministic node wallet from node_id.
    Returns dict with wallet address and node info.
    """
    # Create deterministic wallet address
    seed = f"node-wallet-{node_id}"
    wallet_hash = hashlib.sha256(seed.encode()).hexdigest()[:40]
    wallet_address = f"{wallet_hash}RTC"

    return {
        "node_id": node_id,
        "wallet_address": wallet_address,
        "created_at": None,  # Will be set on first save
        "type": "node_operator"
    }

def load_or_create_node_wallet(node_id: str = None) -> dict:
    """
    Load existing node wallet or create new one.
    If node_id not provided, auto-detect from hostname.
    """
    # Try to load existing wallet
    if os.path.exists(NODE_WALLET_FILE):
        try:
            with open(NODE_WALLET_FILE, 'r') as f:
                wallet = json.load(f)
                print(f"[NodeWallet] Loaded existing wallet: {wallet['wallet_address']}")
                return wallet
        except Exception as e:
            print(f"[NodeWallet] Error loading wallet: {e}")

    # Generate node_id if not provided
    if not node_id:
        hostname = socket.gethostname()
        # Create unique node_id from hostname
        node_id = f"node-{hostname}"

    # Create new wallet
    import time
    wallet = generate_node_wallet(node_id)
    wallet["created_at"] = int(time.time())

    # Save wallet
    save_node_wallet(wallet)
    print(f"[NodeWallet] Created new wallet: {wallet['wallet_address']}")

    return wallet

def save_node_wallet(wallet: dict):
    """Save node wallet to file."""
    wallet_dir = os.path.dirname(NODE_WALLET_FILE)
    if wallet_dir and not os.path.exists(wallet_dir):
        os.makedirs(wallet_dir)

    with open(NODE_WALLET_FILE, 'w') as f:
        json.dump(wallet, f, indent=2)

    # Secure the file
    os.chmod(NODE_WALLET_FILE, 0o600)

def get_node_wallet_address() -> str:
    """Quick helper to get just the wallet address."""
    wallet = load_or_create_node_wallet()
    return wallet["wallet_address"]

# Integration with node startup
def register_node_wallet_endpoints(app, db_path: str):
    """
    Register Flask endpoints for node wallet operations.
    Call this from the main node script.
    """
    from flask import jsonify

    @app.route('/node/wallet', methods=['GET'])
    def get_node_wallet():
        """Return this node's wallet info."""
        wallet = load_or_create_node_wallet()
        return jsonify({
            "ok": True,
            "node_id": wallet["node_id"],
            "wallet_address": wallet["wallet_address"],
            "type": wallet["type"]
        })

    @app.route('/node/info', methods=['GET'])
    def get_node_info():
        """Return full node information."""
        import platform
        wallet = load_or_create_node_wallet()
        return jsonify({
            "ok": True,
            "node_id": wallet["node_id"],
            "wallet_address": wallet["wallet_address"],
            "hostname": socket.gethostname(),
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "db_path": db_path
        })

    print(f"[NodeWallet] Endpoints registered: /node/wallet, /node/info")

if __name__ == "__main__":
    # Test/demo
    print("RustChain Node Wallet System")
    print("=" * 40)

    wallet = load_or_create_node_wallet()
    print(f"\nNode ID: {wallet['node_id']}")
    print(f"Wallet:  {wallet['wallet_address']}")
    print(f"Type:    {wallet['type']}")
    print(f"File:    {NODE_WALLET_FILE}")
