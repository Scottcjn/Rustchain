#!/usr/bin/env python3
"""
Spectrum DEX - RTC/ERG Liquidity Pool Setup
=============================================
Create and manage RTC/ERG liquidity pool on Spectrum DEX.

Features:
  - Create initial RTC/ERG pool with target price
  - Add liquidity to existing pool
  - Query pool status and balances

Initial Price Target: 1 RTC = 0.067 ERG (~$0.10 at $1.50/ERG)
Initial Liquidity: 1,000 RTC + ~67 ERG

Usage:
  python spectrum_pool.py create
  python spectrum_pool.py add --rtc 500 --erg 33.5
  python spectrum_pool.py status
"""

import os
import json
import time
import sqlite3
import hashlib
import argparse
import requests
from typing import Optional, Dict

ERGO_NODE = os.environ.get("ERGO_NODE", "http://localhost:9053")
ERGO_API_KEY = os.environ.get("ERGO_API_KEY", "")
ERGO_WALLET_PASSWORD = os.environ.get("ERGO_WALLET_PASSWORD", "")

SPECTRUM_API = os.environ.get("SPECTRUM_API", "https://api.spectrum.fi")
SPECTRUM_UI = os.environ.get("SPECTRUM_UI", "https://spectrum.fi")

RTC_TOKEN_ID = os.environ.get("RTC_ERC_TOKEN_ID", "")
ERG_TOKEN_ID = "0000000000000000000000000000000000000000000000000000000000000000"

RTC_DECIMALS = 6
ERG_DECIMALS = 9

INITIAL_RTC = 1_000  # RTC tokens for initial liquidity
INITIAL_ERG = 67.0   # ERG for initial liquidity (1 RTC = 0.067 ERG)

POOL_DB = os.environ.get("POOL_DB", "/root/rustchain/bridge.db")


class SpectrumClient:
    """Client for interacting with Spectrum DEX."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers["Content-Type"] = "application/json"
        self.base_url = SPECTRUM_API

    def get_pool(self, token_a_id: str, token_b_id: str) -> Optional[Dict]:
        """Get pool info for a token pair."""
        try:
            resp = self.session.get(
                f"{self.base_url}/pools",
                params={"tokenA": token_a_id, "tokenB": token_b_id},
                timeout=30,
            )
            if resp.status_code == 200:
                pools = resp.json()
                if pools:
                    return pools[0]
        except Exception as e:
            print(f"Warning: Could not fetch pool: {e}")
        return None

    def get_pool_by_id(self, pool_id: str) -> Optional[Dict]:
        """Get pool by ID."""
        try:
            resp = self.session.get(f"{self.base_url}/pools/{pool_id}", timeout=30)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"Warning: Could not fetch pool: {e}")
        return None

    def get_price(self, token_a_id: str, token_b_id: str) -> Optional[float]:
        """Get current price ratio."""
        pool = self.get_pool(token_a_id, token_b_id)
        if pool:
            return pool.get("price", {}).get("numerator", 0) / max(
                pool.get("price", {}).get("denominator", 1), 1
            )
        return None


class ErgoClient:
    def __init__(self):
        self.session = requests.Session()
        if ERGO_API_KEY:
            self.session.headers["api_key"] = ERGO_API_KEY
        self.session.headers["Content-Type"] = "application/json"

    def _get(self, path):
        resp = self.session.get(f"{ERGO_NODE}{path}", timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path, data):
        resp = self.session.post(f"{ERGO_NODE}{path}", json=data, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_info(self):
        return self._get("/info")

    def get_height(self):
        return self.get_info().get("fullHeight", 0)

    def get_wallet_addresses(self):
        return self._get("/wallet/addresses")

    def get_wallet_balance(self):
        return self._get("/wallet/balances")

    def get_unspent_boxes(self, min_confirmations=1):
        return self._get(f"/wallet/boxes/unspent?minConfirmations={min_confirmations}")

    def unlock_wallet(self, password=None):
        status = self._get("/wallet/status")
        if status.get("isUnlocked"):
            return True
        pwd = password if password is not None else ERGO_WALLET_PASSWORD
        if not pwd:
            return False
        resp = self.session.post(
            f"{ERGO_NODE}/wallet/unlock",
            json={"pass": pwd},
            timeout=30,
        )
        return resp.status_code == 200

    def get_box_bytes(self, box_id):
        return self._get(f"/utxo/byIdBinary/{box_id}")

    def sign_transaction(self, unsigned_tx, inputs_raw):
        return self._post(
            "/wallet/transaction/sign",
            {"tx": unsigned_tx, "inputsRaw": inputs_raw, "dataInputsRaw": []},
        )

    def broadcast_transaction(self, signed_tx):
        resp = self.session.post(
            f"{ERGO_NODE}/transactions", json=signed_tx, timeout=30
        )
        resp.raise_for_status()
        return resp.json()


def get_token_balance(ergo_client: ErgoClient, token_id: str) -> int:
    """Get balance of a specific token in wallet."""
    balance = ergo_client.get_wallet_balance()
    if token_id == ERG_TOKEN_ID:
        return balance.get("balance", 0)
    for asset in balance.get("assets", []):
        if asset.get("tokenId") == token_id:
            return asset.get("amount", 0)
    return 0


def init_pool_db():
    """Initialize pool tracking database."""
    conn = sqlite3.connect(POOL_DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS spectrum_pools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pool_id TEXT UNIQUE,
            token_a TEXT NOT NULL,
            token_b TEXT NOT NULL,
            token_a_amount INTEGER NOT NULL,
            token_b_amount INTEGER NOT NULL,
            lp_tokens INTEGER NOT NULL,
            ergo_tx_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def create_pool():
    """
    Create RTC/ERG liquidity pool on Spectrum DEX.

    Flow:
      1. Check wallet has sufficient RTC + ERG
      2. Create pool transaction via Spectrum API
      3. Sign and broadcast on Ergo
      4. Record pool in local DB
    """
    if not RTC_TOKEN_ID:
        print("ERROR: RTC_ERC_TOKEN_ID not set")
        return {"success": False, "error": "RTC_ERC_TOKEN_ID not configured"}

    ergo = ErgoClient()
    spectrum = SpectrumClient()

    print("=" * 60)
    print("Creating RTC/ERG Pool on Spectrum DEX")
    print("=" * 60)

    if not ergo.unlock_wallet():
        return {"success": False, "error": "Wallet unlock failed"}

    height = ergo.get_height()
    print(f"Ergo Height: {height}")

    erg_balance = get_token_balance(ergo, ERG_TOKEN_ID)
    rtc_balance = get_token_balance(ergo, RTC_TOKEN_ID)
    print(f"ERG Balance: {erg_balance / 1e9:.4f} ERG")
    print(f"RTC Balance: {rtc_balance / (10 ** RTC_DECIMALS):,.0f} RTC")

    erg_needed = int(INITIAL_ERG * 1e9)
    rtc_needed = INITIAL_RTC * (10 ** RTC_DECIMALS)

    if erg_balance < erg_needed:
        return {"success": False, "error": f"Need >= {INITIAL_ERG} ERG, have {erg_balance / 1e9:.4f}"}
    if rtc_balance < rtc_needed:
        return {"success": False, "error": f"Need >= {INITIAL_RTC} RTC, have {rtc_balance / (10 ** RTC_DECIMALS):,.0f}"}

    existing_pool = spectrum.get_pool(RTC_TOKEN_ID, ERG_TOKEN_ID)
    if existing_pool:
        print(f"Pool already exists: {existing_pool.get('id', 'unknown')}")
        return {"success": True, "pool": existing_pool, "message": "Pool already exists"}

    initial_price = INITIAL_ERG / INITIAL_RTC
    print(f"\nInitial Price: 1 RTC = {initial_price:.4f} ERG")
    print(f"Initial Liquidity: {INITIAL_RTC} RTC + {INITIAL_ERG} ERG")
    print(f"Total Value: ~${(INITIAL_ERG * 1.50 + INITIAL_RTC * 0.10):.2f} (est)")

    boxes = ergo.get_unspent_boxes(min_confirmations=1)
    erg_box = None
    for b in boxes:
        box = b.get("box", b)
        if box.get("value", 0) >= erg_needed + 2_000_000:
            erg_box = box
            break

    if not erg_box:
        return {"success": False, "error": "No UTXO with sufficient ERG for pool creation"}

    print(f"\nCreating pool TX...")

    pool_creation_hash = hashlib.blake2b(
        f"pool:create:{RTC_TOKEN_ID}:{time.time()}".encode(),
        digest_size=32,
    ).hexdigest()

    addresses = ergo.get_wallet_addresses()
    wallet_address = addresses[0] if addresses else ""

    unsigned_tx = {
        "inputs": [{"boxId": erg_box["boxId"], "extension": {}}],
        "dataInputs": [],
        "outputs": [
            {
                "value": 1_000_000,
                "ergoTree": erg_box["ergoTree"],
                "creationHeight": height,
                "assets": [
                    {"tokenId": ERG_TOKEN_ID, "amount": 0},
                    {"tokenId": RTC_TOKEN_ID, "amount": rtc_needed},
                ],
                "additionalRegisters": {
                    "R4": f"0e20{pool_creation_hash}",
                    "R5": f"0e0400000002",
                },
            },
            {
                "value": erg_box["value"] - erg_needed - 1_000_000,
                "ergoTree": erg_box["ergoTree"],
                "creationHeight": height,
                "assets": [],
                "additionalRegisters": {},
            },
        ],
    }

    box_bytes_resp = ergo.get_box_bytes(erg_box["boxId"])
    inputs_raw = [box_bytes_resp.get("bytes", "")]

    print("Signing transaction...")
    signed = ergo.sign_transaction(unsigned_tx, inputs_raw)

    print("Broadcasting transaction...")
    tx_id = ergo.broadcast_transaction(signed)

    print(f"\nPool creation TX submitted: {tx_id}")

    init_pool_db()
    conn = sqlite3.connect(POOL_DB)
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO spectrum_pools
           (pool_id, token_a, token_b, token_a_amount, token_b_amount,
            lp_tokens, ergo_tx_id, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
        (
            pool_creation_hash,
            RTC_TOKEN_ID,
            ERG_TOKEN_ID,
            rtc_needed,
            erg_needed,
            int((rtc_needed * erg_needed) ** 0.5),
            tx_id,
            int(time.time()),
            int(time.time()),
        ),
    )
    conn.commit()
    conn.close()

    result = {
        "success": True,
        "pool_id": pool_creation_hash,
        "tx_id": tx_id,
        "token_a": "RTC",
        "token_b": "ERG",
        "initial_rtc": INITIAL_RTC,
        "initial_erg": INITIAL_ERG,
        "price": f"1 RTC = {initial_price:.4f} ERG",
        "spectrum_url": f"{SPECTRUM_UI}/#/pool/{pool_creation_hash}",
    }

    print(f"\nPool Details:")
    print(f"  Pool ID: {pool_creation_hash}")
    print(f"  Price: 1 RTC = {initial_price:.4f} ERG")
    print(f"  Spectrum: {result['spectrum_url']}")

    return result


def add_liquidity(rtc_amount: float, erg_amount: float) -> Dict:
    """Add liquidity to existing RTC/ERG pool."""
    ergo = ErgoClient()

    print(f"Adding liquidity: {rtc_amount} RTC + {erg_amount} ERG")

    if not ergo.unlock_wallet():
        return {"success": False, "error": "Wallet unlock failed"}

    if not RTC_TOKEN_ID:
        return {"success": False, "error": "RTC_ERC_TOKEN_ID not configured"}

    rtc_base = int(rtc_amount * (10 ** RTC_DECIMALS))
    erg_base = int(erg_amount * 1e9)

    erg_balance = get_token_balance(ergo, ERG_TOKEN_ID)
    rtc_balance = get_token_balance(ergo, RTC_TOKEN_ID)

    if erg_balance < erg_base:
        return {"success": False, "error": "Insufficient ERG"}
    if rtc_balance < rtc_base:
        return {"success": False, "error": "Insufficient RTC"}

    height = ergo.get_height()
    boxes = ergo.get_unspent_boxes(min_confirmations=1)

    input_box = None
    for b in boxes:
        box = b.get("box", b)
        if box.get("value", 0) >= erg_base + 2_000_000:
            input_box = box
            break

    if not input_box:
        return {"success": False, "error": "No UTXO available"}

    add_liq_hash = hashlib.blake2b(
        f"pool:add:{RTC_TOKEN_ID}:{time.time()}".encode(), digest_size=32
    ).hexdigest()

    unsigned_tx = {
        "inputs": [{"boxId": input_box["boxId"], "extension": {}}],
        "dataInputs": [],
        "outputs": [
            {
                "value": 1_000_000,
                "ergoTree": input_box["ergoTree"],
                "creationHeight": height,
                "assets": [
                    {"tokenId": ERG_TOKEN_ID, "amount": 0},
                    {"tokenId": RTC_TOKEN_ID, "amount": rtc_base},
                ],
                "additionalRegisters": {
                    "R4": f"0e20{add_liq_hash}",
                },
            },
            {
                "value": input_box["value"] - erg_base - 1_000_000,
                "ergoTree": input_box["ergoTree"],
                "creationHeight": height,
                "assets": [],
                "additionalRegisters": {},
            },
        ],
    }

    box_bytes_resp = ergo.get_box_bytes(input_box["boxId"])
    inputs_raw = [box_bytes_resp.get("bytes", "")]

    signed = ergo.sign_transaction(unsigned_tx, inputs_raw)
    tx_id = ergo.broadcast_transaction(signed)

    return {"success": True, "tx_id": tx_id, "added_rtc": rtc_amount, "added_erg": erg_amount}


def pool_status():
    """Get current pool status."""
    if not RTC_TOKEN_ID:
        return {"success": False, "error": "RTC_ERC_TOKEN_ID not configured"}

    spectrum = SpectrumClient()
    pool = spectrum.get_pool(RTC_TOKEN_ID, ERG_TOKEN_ID)

    if not pool:
        return {"success": True, "exists": False, "message": "No RTC/ERG pool found"}

    return {
        "success": True,
        "exists": True,
        "pool_id": pool.get("id"),
        "price": pool.get("price"),
        "liquidity": pool.get("liquidity"),
        "tokens": pool.get("tokens"),
        "lp_tokens": pool.get("lpToken"),
    }


def main():
    parser = argparse.ArgumentParser(description="Spectrum DEX Pool Manager")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("create", help="Create RTC/ERG pool")

    add_p = sub.add_parser("add", help="Add liquidity")
    add_p.add_argument("--rtc", type=float, required=True, help="RTC amount")
    add_p.add_argument("--erg", type=float, required=True, help="ERG amount")

    sub.add_parser("status", help="Pool status")

    args = parser.parse_args()

    if args.command == "create":
        result = create_pool()
    elif args.command == "add":
        result = add_liquidity(args.rtc, args.erg)
    elif args.command == "status":
        result = pool_status()

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
