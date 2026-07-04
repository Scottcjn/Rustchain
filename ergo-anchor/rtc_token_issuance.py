#!/usr/bin/env python3
"""
RTC Token Issuance on Ergo
===========================
Issue RustChain Token (RTC) as an Ergo native token following EIP-4 standard.

Token Metadata:
  - Name: RustChain Token
  - Symbol: RTC
  - Decimals: 6
  - Initial Supply: 100,000,000 (100M)

Usage:
  python rtc_token_issuance.py
"""

import os
import json
import time
import requests

ERGO_NODE = os.environ.get("ERGO_NODE", "http://localhost:9053")
ERGO_API_KEY = os.environ.get("ERGO_API_KEY", "")
ERGO_WALLET_PASSWORD = os.environ.get("ERGO_WALLET_PASSWORD", "")

RTC_TOKEN_NAME = "RustChain Token"
RTC_TOKEN_SYMBOL = "RTC"
RTC_DECIMALS = 6
RTC_INITIAL_SUPPLY = 100_000_000 * (10 ** RTC_DECIMALS)  # 100M tokens in base units
TOKEN_BOX_VALUE = 1_000_000_000  # 1 ERG minimum box value for token box


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

    def sign_transaction(self, unsigned_tx, inputs_raw, data_inputs_raw=None):
        payload = {
            "tx": unsigned_tx,
            "inputsRaw": inputs_raw,
            "dataInputsRaw": data_inputs_raw or [],
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


def build_token_metadata_register():
    """
    Build R4 register with EIP-4 token metadata.
    R4: Token name, symbol, description, decimals, extra fields.
    """
    name_bytes = RTC_TOKEN_NAME.encode("utf-8").hex()
    symbol_bytes = RTC_TOKEN_SYMBOL.encode("utf-8").hex()
    description_bytes = b"RustChain Token - cross-chain bridge token on Ergo".hex()
    extra_fields = "{}".encode("utf-8").hex()

    # EIP-4 token register encoding:
    # R4 = [name, description, decimals, linkToProject, extraFields]
    return {
        "R4": f"0e0a{symbol_bytes}",  # simplified: symbol in R4
        "R5": f"0e{len(name_bytes) // 2:02x}{name_bytes}",
        "R6": f"0e{len(description_bytes) // 2:02x}{description_bytes}",
    }


def issue_rtc_token():
    """Issue RTC as an Ergo native token."""
    client = ErgoClient()

    print("=" * 60)
    print("RTC Token Issuance on Ergo")
    print("=" * 60)

    if not client.unlock_wallet():
        print("ERROR: Wallet locked or unlock failed")
        return {"success": False, "error": "Wallet unlock failed"}

    height = client.get_height()
    balance = client.get_wallet_balance()
    print(f"Ergo Height: {height}")
    print(f"Wallet Balance: {balance / 1e9:.4f} ERG")

    if balance < 2 * TOKEN_BOX_VALUE:
        print(f"ERROR: Insufficient ERG. Need >= {2 * TOKEN_BOX_VALUE / 1e9:.4f} ERG")
        return {"success": False, "error": "Insufficient ERG balance"}

    boxes = client.get_unspent_boxes(min_confirmations=1)
    input_box = None
    for b in boxes:
        box = b.get("box", b)
        if box.get("value", 0) >= 2 * TOKEN_BOX_VALUE:
            input_box = box
            break

    if not input_box:
        return {"success": False, "error": "No UTXO with sufficient value"}

    print(f"Using input box: {input_box['boxId'][:16]}... ({input_box['value'] / 1e9:.4f} ERG)")

    input_val = input_box["value"]
    change_val = input_val - TOKEN_BOX_VALUE
    addresses = client.get_wallet_addresses()
    wallet_address = addresses[0] if addresses else ""

    unsigned_tx = {
        "inputs": [{"boxId": input_box["boxId"], "extension": {}}],
        "dataInputs": [],
        "outputs": [
            {
                "value": TOKEN_BOX_VALUE,
                "ergoTree": input_box["ergoTree"],
                "creationHeight": height,
                "assets": [
                    {
                        "tokenId": input_box["boxId"],
                        "amount": RTC_INITIAL_SUPPLY,
                    }
                ],
                "additionalRegisters": build_token_metadata_register(),
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

    print("\nSigning transaction...")
    signed = client.sign_transaction(unsigned_tx, inputs_raw)

    print("Broadcasting transaction...")
    tx_id = client.broadcast_transaction(signed)

    print(f"\nSUCCESS! Token issued.")
    print(f"Transaction: {tx_id}")
    print(f"Token ID: {input_box['boxId']}")
    print(f"Supply: {RTC_INITIAL_SUPPLY / (10 ** RTC_DECIMALS):,.0f} {RTC_TOKEN_SYMBOL}")
    print(f"Decimals: {RTC_DECIMALS}")

    result = {
        "success": True,
        "tx_id": tx_id,
        "token_id": input_box["boxId"],
        "token_name": RTC_TOKEN_NAME,
        "token_symbol": RTC_TOKEN_SYMBOL,
        "decimals": RTC_DECIMALS,
        "total_supply": RTC_INITIAL_SUPPLY,
        "height": height,
    }

    print(f"\nJSON: {json.dumps(result, indent=2)}")
    return result


if __name__ == "__main__":
    result = issue_rtc_token()
