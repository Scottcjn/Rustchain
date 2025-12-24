#!/usr/bin/env python3
"""Raw Ergo TX builder - simplified version."""
import os, json, sqlite3, time, requests
from hashlib import blake2b

ERGO_NODE = "http://localhost:9053"
ERGO_API_KEY = os.environ.get("ERGO_API_KEY", "BE7YM1fYWrMQ9tSmxAc9jzLNw42nEXTX")
DB_PATH = "/root/rustchain/rustchain_v2.db"

def encode_coll_byte(hex_str):
    data = bytes.fromhex(hex_str)
    length = len(data)
    if length < 128:
        return "0e" + format(length, "02x") + hex_str
    return "0e" + format(0x80 | (length & 0x7f), "02x") + format(length >> 7, "02x") + hex_str

def encode_int_reg(n):
    zigzag = (n << 1) ^ (n >> 31) if n >= 0 else (((-n) << 1) - 1)
    if zigzag < 128:
        return "04" + format(zigzag, "02x")
    result = "04"
    while zigzag >= 128:
        result += format(0x80 | (zigzag & 0x7f), "02x")
        zigzag >>= 7
    result += format(zigzag, "02x")
    return result

class RawTxBuilder:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers["api_key"] = ERGO_API_KEY
        self.session.headers["Content-Type"] = "application/json"
    
    def get_unspent_box(self, min_value=2000000):
        resp = self.session.get(ERGO_NODE + "/wallet/boxes/unspent?minConfirmations=0")
        if resp.status_code == 200:
            for b in resp.json():
                if b.get("box", {}).get("value", 0) >= min_value:
                    return b
        return None
    
    def get_current_height(self):
        resp = self.session.get(ERGO_NODE + "/info")
        return resp.json().get("fullHeight", 0) if resp.status_code == 200 else 0
    
    def get_recent_miners(self, limit=10):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT miner, device_arch, ts_ok FROM miner_attest_recent ORDER BY ts_ok DESC LIMIT ?", (limit,))
        miners = [dict(row) for row in cur.fetchall()]
        conn.close()
        return miners
    
    def compute_commitment(self, miners):
        data = json.dumps(miners, sort_keys=True).encode()
        return blake2b(data, digest_size=32).hexdigest()
    
    def anchor_miners(self):
        miners = self.get_recent_miners(10)
        if not miners:
            return {"success": False, "error": "No miners"}
        
        box_data = self.get_unspent_box(3000000)
        if not box_data:
            return {"success": False, "error": "No UTXO"}
        
        box = box_data["box"]
        height = self.get_current_height()
        commitment = self.compute_commitment(miners)
        
        input_value = box["value"]
        min_box = 1000000  # Minimum box value
        fee = 1100000      # Fee (slightly higher)
        change_value = input_value - min_box - fee
        
        print("=== Anchoring " + str(len(miners)) + " miners ===")
        print("Input: " + str(input_value) + " nanoErg")
        print("Output box: " + str(min_box))
        print("Change: " + str(change_value))
        print("Fee: " + str(fee))
        print("Total out+fee: " + str(min_box + change_value + fee))
        print("Commitment: " + commitment[:32] + "...")
        
        # Minimal registers
        miner_str = ",".join(m.get("miner", "")[:6] for m in miners[:5])
        
        registers = {
            "R4": encode_coll_byte(commitment),
            "R5": encode_int_reg(len(miners))
        }
        
        unsigned_tx = {
            "inputs": [{"boxId": box["boxId"], "extension": {}}],
            "dataInputs": [],
            "outputs": [
                {
                    "value": min_box,
                    "ergoTree": box["ergoTree"],
                    "creationHeight": height,
                    "assets": [],
                    "additionalRegisters": registers
                },
                {
                    "value": change_value,
                    "ergoTree": box["ergoTree"],
                    "creationHeight": height,
                    "assets": [],
                    "additionalRegisters": {}
                }
            ]
        }
        
        print("Signing...")
        sign_resp = self.session.post(ERGO_NODE + "/wallet/transaction/sign", json={"tx": unsigned_tx})
        if sign_resp.status_code != 200:
            return {"success": False, "error": "Sign: " + sign_resp.text[:100]}
        
        signed_tx = sign_resp.json()
        
        # Debug: print signed tx values
        print("Signed TX outputs:")
        for i, out in enumerate(signed_tx.get("outputs", [])):
            print("  Output " + str(i) + ": " + str(out.get("value")))
        
        print("Broadcasting...")
        send_resp = self.session.post(ERGO_NODE + "/transactions", json=signed_tx)
        if send_resp.status_code == 200:
            tx_id = send_resp.json()
            if isinstance(tx_id, dict):
                tx_id = tx_id.get("id", str(tx_id))
            return {"success": True, "tx_id": str(tx_id)}
        
        return {"success": False, "error": "Broadcast: " + send_resp.text[:150]}

if __name__ == "__main__":
    result = RawTxBuilder().anchor_miners()
    print("\nResult: " + json.dumps(result, indent=2))
