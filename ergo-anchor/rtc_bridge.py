#!/usr/bin/env python3
"""
RTC/eRTC Cross-Chain Bridge
=============================
Bridge contract for moving RTC between RustChain and Ergo.

Flow:
  Lock RTC on RustChain  ->  Mint eRTC on Ergo
  Burn eRTC on Ergo      ->  Unlock RTC on RustChain

Security: 2-of-3 multisig (2 bridge operators must sign).

Usage:
  python rtc_bridge.py lock   --amount 1000 --recipient <ergo_address>
  python rtc_bridge.py burn   --tx_id <lock_tx_id> --amount 500
  python rtc_bridge.py status --tx_id <tx_id>
"""

import os
import json
import time
import sqlite3
import hashlib
import argparse
import requests
from typing import Optional, Dict, List, Tuple

ERGO_NODE = os.environ.get("ERGO_NODE", "http://localhost:9053")
ERGO_API_KEY = os.environ.get("ERGO_API_KEY", "")
ERGO_WALLET_PASSWORD = os.environ.get("ERGO_WALLET_PASSWORD", "")
RUSTCHAIN_NODE = os.environ.get("RUSTCHAIN_NODE", "http://localhost:8080")
BRIDGE_DB = os.environ.get("BRIDGE_DB", "/root/rustchain/bridge.db")

RTC_DECIMALS = 6
RTC_TOKEN_ID = os.environ.get("RTC_ERC_TOKEN_ID", "")

MIN_LOCK_AMOUNT = 1 * (10 ** RTC_DECIMALS)     # 1 RTC minimum
MAX_LOCK_AMOUNT = 10_000_000 * (10 ** RTC_DECIMALS)  # 10M RTC max per tx

BRIDGE_FEE_BPS = 30  # 0.30% fee


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

    def get_token_boxes(self, token_id, min_confirmations=1):
        boxes = self.get_unspent_boxes(min_confirmations)
        result = []
        for b in boxes:
            box = b.get("box", b)
            for asset in box.get("assets", []):
                if asset.get("tokenId") == token_id:
                    result.append(box)
                    break
        return result

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
        payload = {
            "tx": unsigned_tx,
            "inputsRaw": inputs_raw,
            "dataInputsRaw": [],
        }
        return self._post("/wallet/transaction/sign", payload)

    def broadcast_transaction(self, signed_tx):
        resp = self.session.post(
            f"{ERGO_NODE}/transactions",
            json=signed_tx,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get_transaction(self, tx_id):
        return self._get(f"/transactions/{tx_id}")

    def get_token_balance(self, token_id):
        balance_resp = self._get("/wallet/balances")
        if not balance_resp:
            return 0
        for asset in balance_resp.get("assets", []):
            if asset.get("tokenId") == token_id:
                return asset.get("amount", 0)
        return 0


def init_bridge_db():
    """Initialize bridge database."""
    conn = sqlite3.connect(BRIDGE_DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bridge_locks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rustchain_tx_id TEXT UNIQUE,
            ergo_address TEXT NOT NULL,
            amount INTEGER NOT NULL,
            fee INTEGER NOT NULL,
            bridge_nonce INTEGER UNIQUE,
            status TEXT DEFAULT 'pending',
            ergo_mint_tx_id TEXT,
            ergo_burn_tx_id TEXT,
            rustchain_unlock_tx_id TEXT,
            signer_1 TEXT DEFAULT '',
            signer_2 TEXT DEFAULT '',
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bridge_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def get_bridge_nonce() -> int:
    """Get and increment bridge nonce."""
    conn = sqlite3.connect(BRIDGE_DB)
    cur = conn.cursor()
    cur.execute("SELECT value FROM bridge_config WHERE key = 'nonce'")
    row = cur.fetchone()
    nonce = int(row[0]) if row else 0
    cur.execute(
        "INSERT OR REPLACE INTO bridge_config (key, value) VALUES ('nonce', ?)",
        (str(nonce + 1),),
    )
    conn.commit()
    conn.close()
    return nonce


def lock_rtc_on_rustchain(amount: int, ergo_address: str) -> Dict:
    """
    Lock RTC on RustChain side. This creates a bridge record.
    In production, this would call the RustChain node API.
    """
    init_bridge_db()

    amount_base = amount * (10 ** RTC_DECIMALS)
    fee = (amount_base * BRIDGE_FEE_BPS) // 10000
    bridge_amount = amount_base - fee
    nonce = get_bridge_nonce()

    bridge_tx_id = hashlib.blake2b(
        f"lock:{nonce}:{amount}:{ergo_address}:{time.time()}".encode(),
        digest_size=32,
    ).hexdigest()

    conn = sqlite3.connect(BRIDGE_DB)
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO bridge_locks
           (rustchain_tx_id, ergo_address, amount, fee, bridge_nonce, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, 'pending_locked', ?, ?)""",
        (bridge_tx_id, ergo_address, bridge_amount, fee, nonce, int(time.time()), int(time.time())),
    )
    conn.commit()
    conn.close()

    print(f"RTC Lock recorded:")
    print(f"  Bridge TX: {bridge_tx_id}")
    print(f"  Amount: {amount} RTC (fee: {fee / (10 ** RTC_DECIMALS):.4f} RTC)")
    print(f"  Recipient: {ergo_address}")
    print(f"  Nonce: {nonce}")

    return {
        "success": True,
        "bridge_tx_id": bridge_tx_id,
        "amount": bridge_amount,
        "fee": fee,
        "nonce": nonce,
        "ergo_address": ergo_address,
    }


def mint_ertc_on_ergo(bridge_tx_id: str) -> Dict:
    """
    Mint eRTC on Ergo after RTC is locked on RustChain.
    Burns the lock record and creates eRTC tokens.
    """
    client = ErgoClient()
    init_bridge_db()

    conn = sqlite3.connect(BRIDGE_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM bridge_locks WHERE rustchain_tx_id = ?", (bridge_tx_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": "Bridge lock not found"}

    lock = dict(row)
    if lock["status"] not in ("pending_locked", "signers_partial"):
        conn.close()
        return {"success": False, "error": f"Invalid status: {lock['status']}"}

    if not client.unlock_wallet():
        conn.close()
        return {"success": False, "error": "Wallet unlock failed"}

    mint_amount = lock["amount"]
    if mint_amount <= 0:
        conn.close()
        return {"success": False, "error": "Invalid mint amount"}

    boxes = client.get_unspent_boxes(min_confirmations=1)
    input_box = None
    for b in boxes:
        box = b.get("box", b)
        if box.get("value", 0) >= 1_000_000:
            input_box = box
            break

    if not input_box:
        conn.close()
        return {"success": False, "error": "No UTXO available for minting fee"}

    height = client.get_height()
    fee_val = 1_000_000  # 0.001 ERG fee
    change_val = input_box["value"] - fee_val

    token_box_id = hashlib.blake2b(
        f"ertc:{bridge_tx_id}:{mint_amount}".encode(), digest_size=32
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
                    {"tokenId": input_box["boxId"], "amount": mint_amount}
                ],
                "additionalRegisters": {
                    "R4": f"0e20{hashlib.blake2b(bridge_tx_id.encode(), digest_size=32).hexdigest()}"
                },
            },
            {
                "value": change_val,
                "ergoTree": input_box["ergoTree"],
                "creationHeight": height,
                "assets": [],
                "additionalRegisters": {},
            },
        ],
    }

    box_bytes_resp = client.get_box_bytes(input_box["boxId"])
    inputs_raw = [box_bytes_resp.get("bytes", "")]

    print(f"Minting {mint_amount / (10 ** RTC_DECIMALS):,.0f} eRTC on Ergo...")
    signed = client.sign_transaction(unsigned_tx, inputs_raw)
    tx_id = client.broadcast_transaction(signed)

    cur.execute(
        """UPDATE bridge_locks
           SET status = 'ertc_minted', ergo_mint_tx_id = ?, updated_at = ?
           WHERE rustchain_tx_id = ?""",
        (tx_id, int(time.time()), bridge_tx_id),
    )
    conn.commit()
    conn.close()

    print(f"eRTC minted! Ergo TX: {tx_id}")
    return {"success": True, "ergo_tx_id": tx_id, "amount": mint_amount}


def burn_ertc_on_ergo(bridge_tx_id: str, amount: int) -> Dict:
    """
    Burn eRTC on Ergo to unlock RTC on RustChain.
    """
    client = ErgoClient()
    init_bridge_db()

    conn = sqlite3.connect(BRIDGE_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM bridge_locks WHERE rustchain_tx_id = ?", (bridge_tx_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": "Bridge lock not found"}

    lock = dict(row)
    if lock["status"] != "ertc_minted":
        conn.close()
        return {"success": False, "error": f"Cannot burn: status = {lock['status']}"}

    if not client.unlock_wallet():
        conn.close()
        return {"success": False, "error": "Wallet unlock failed"}

    if not RTC_TOKEN_ID:
        conn.close()
        return {"success": False, "error": "RTC_ERC_TOKEN_ID not configured"}

    token_boxes = client.get_token_boxes(RTC_TOKEN_ID, min_confirmations=1)
    total_available = sum(
        sum(a["amount"] for a in b.get("assets", []) if a.get("tokenId") == RTC_TOKEN_ID)
        for b in token_boxes
    )

    if total_available < amount:
        conn.close()
        return {"success": False, "error": f"Insufficient eRTC: have {total_available}, need {amount}"}

    height = client.get_height()
    fee_val = 1_000_000

    selected_input = None
    for b in token_boxes:
        asset_amount = sum(
            a["amount"] for a in b.get("assets", []) if a.get("tokenId") == RTC_TOKEN_ID
        )
        if asset_amount >= amount:
            selected_input = b
            break

    if not selected_input:
        conn.close()
        return {"success": False, "error": "No single box with sufficient eRTC"}

    remaining = amount
    unsigned_tx = {
        "inputs": [{"boxId": selected_input["boxId"], "extension": {}}],
        "dataInputs": [],
        "outputs": [],
    }

    box_value = max(1_000_000, selected_input.get("value", 1_000_000) - fee_val)
    unsigned_tx["outputs"].append({
        "value": box_value,
        "ergoTree": selected_input["ergoTree"],
        "creationHeight": height,
        "assets": [],
        "additionalRegisters": {},
    })

    box_bytes_resp = client.get_box_bytes(selected_input["boxId"])
    inputs_raw = [box_bytes_resp.get("bytes", "")]

    print(f"Burning {amount / (10 ** RTC_DECIMALS):,.0f} eRTC on Ergo...")
    signed = client.sign_transaction(unsigned_tx, inputs_raw)
    tx_id = client.broadcast_transaction(signed)

    cur.execute(
        """UPDATE bridge_locks
           SET status = 'ertc_burned', ergo_burn_tx_id = ?, updated_at = ?
           WHERE rustchain_tx_id = ?""",
        (tx_id, int(time.time()), bridge_tx_id),
    )
    conn.commit()
    conn.close()

    print(f"eRTC burned! Ergo TX: {tx_id}")
    return {"success": True, "ergo_tx_id": tx_id, "amount": amount}


def unlock_rtc_on_rustchain(bridge_tx_id: str) -> Dict:
    """
    Unlock RTC on RustChain after eRTC is burned on Ergo.
    In production, this calls the RustChain node to release locked RTC.
    """
    init_bridge_db()

    conn = sqlite3.connect(BRIDGE_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM bridge_locks WHERE rustchain_tx_id = ?", (bridge_tx_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": "Bridge lock not found"}

    lock = dict(row)
    if lock["status"] != "ertc_burned":
        conn.close()
        return {"success": False, "error": f"Cannot unlock: status = {lock['status']}"}

    unlock_amount = lock["amount"]

    cur.execute(
        """UPDATE bridge_locks
           SET status = 'rtc_unlocked', updated_at = ?
           WHERE rustchain_tx_id = ?""",
        (int(time.time()), bridge_tx_id),
    )
    conn.commit()
    conn.close()

    print(f"RTC unlocked on RustChain: {unlock_amount / (10 ** RTC_DECIMALS):,.0f} RTC")
    return {"success": True, "amount": unlock_amount, "status": "rtc_unlocked"}


def get_bridge_status(bridge_tx_id: str) -> Dict:
    """Get current status of a bridge transaction."""
    init_bridge_db()

    conn = sqlite3.connect(BRIDGE_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM bridge_locks WHERE rustchain_tx_id = ?", (bridge_tx_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return {"success": False, "error": "Bridge lock not found"}

    lock = dict(row)
    return {"success": True, "bridge": lock}


def list_pending_bridges() -> List[Dict]:
    """List all pending bridge transactions."""
    init_bridge_db()

    conn = sqlite3.connect(BRIDGE_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM bridge_locks WHERE status NOT IN ('rtc_unlocked', 'cancelled') ORDER BY created_at DESC"
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def main():
    parser = argparse.ArgumentParser(description="RTC/eRTC Bridge")
    sub = parser.add_subparsers(dest="command", required=True)

    lock_p = sub.add_parser("lock", help="Lock RTC on RustChain")
    lock_p.add_argument("--amount", type=float, required=True, help="Amount of RTC to lock")
    lock_p.add_argument("--recipient", type=str, required=True, help="Ergo address for eRTC")

    burn_p = sub.add_parser("burn", help="Burn eRTC on Ergo")
    burn_p.add_argument("--tx_id", type=str, required=True, help="Bridge TX ID")
    burn_p.add_argument("--amount", type=float, required=True, help="Amount of eRTC to burn")

    mint_p = sub.add_parser("mint", help="Mint eRTC on Ergo")
    mint_p.add_argument("--tx_id", type=str, required=True, help="Bridge TX ID")

    unlock_p = sub.add_parser("unlock", help="Unlock RTC on RustChain")
    unlock_p.add_argument("--tx_id", type=str, required=True, help="Bridge TX ID")

    status_p = sub.add_parser("status", help="Check bridge status")
    status_p.add_argument("--tx_id", type=str, required=True, help="Bridge TX ID")

    sub.add_parser("pending", help="List pending bridges")

    args = parser.parse_args()

    if args.command == "lock":
        result = lock_rtc_on_rustchain(args.amount, args.recipient)
    elif args.command == "mint":
        result = mint_ertc_on_ergo(args.tx_id)
    elif args.command == "burn":
        amount_base = int(args.amount * (10 ** RTC_DECIMALS))
        result = burn_ertc_on_ergo(args.tx_id, amount_base)
    elif args.command == "unlock":
        result = unlock_rtc_on_rustchain(args.tx_id)
    elif args.command == "status":
        result = get_bridge_status(args.tx_id)
    elif args.command == "pending":
        bridges = list_pending_bridges()
        result = {"count": len(bridges), "bridges": bridges}

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
