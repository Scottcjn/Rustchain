#!/usr/bin/env python3
"""Ergo Miner Anchor - Zero-fee anchor TX with miner commitments in registers."""
import os, json, sqlite3, time, requests
from hashlib import blake2b

ERGO_NODE = os.environ.get("ERGO_NODE", "http://localhost:9053")
ERGO_API_KEY = os.environ.get("ERGO_API_KEY", "")
ERGO_WALLET_PASSWORD = os.environ.get("ERGO_WALLET_PASSWORD", "")
DB_PATH = "/root/rustchain/rustchain_v2.db"
ANCHOR_VALUE = 1000000  # 0.001 ERG min box size

class ErgoMinerAnchor:
    def __init__(self):
        self.session = requests.Session()
        if ERGO_API_KEY:
            self.session.headers["api_key"] = ERGO_API_KEY
        self.session.headers["Content-Type"] = "application/json"
    
    def unlock_wallet(self, password=None):
        """Unlock wallet if needed."""
        status_resp = self.session.get(ERGO_NODE + "/wallet/status")
        if status_resp.status_code != 200:
            return False
        status = status_resp.json()
        if not status.get("isUnlocked"):
            pwd = password if password is not None else ERGO_WALLET_PASSWORD
            if not pwd:
                return False
            unlock_resp = self.session.post(ERGO_NODE + "/wallet/unlock", json={"pass": pwd})
            return unlock_resp.status_code == 200
        return True
    
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
    
    def get_rc_slot(self):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT MAX(slot) FROM headers")
        row = cur.fetchone()
        conn.close()
        return row[0] if row and row[0] else 0
    
    def create_anchor_tx(self, miners):
        """Create zero-fee anchor TX with miner data in registers."""
        if not ERGO_API_KEY:
            return {"success": False, "error": "ERGO_API_KEY not configured"}
        if not self.unlock_wallet():
            return {"success": False, "error": "Wallet locked or unlock failed"}
        
        commitment = self.compute_commitment(miners)
        rc_slot = self.get_rc_slot()
        
        # Get UTXO
        boxes = self.session.get(ERGO_NODE + "/wallet/boxes/unspent?minConfirmations=1").json()
        input_box = None
        for b in boxes:
            box = b.get("box", {})
            if box.get("value", 0) >= 2 * ANCHOR_VALUE:
                input_box = box
                break
        
        if not input_box:
            return {"success": False, "error": "No UTXO"}
        
        box_bytes = self.session.get(ERGO_NODE + "/utxo/byIdBinary/" + input_box["boxId"]).json().get("bytes")
        height = self.session.get(ERGO_NODE + "/info").json().get("fullHeight", 0)
        
        input_val = input_box["value"]
        change_val = input_val - ANCHOR_VALUE  # Zero fee
        
        print("Creating anchor TX:")
        print("  Commitment:", commitment[:32] + "...")
        print("  Miners:", len(miners))
        print("  RC Slot:", rc_slot)
        print("  Input:", input_val / 1e9, "ERG")
        
        unsigned_tx = {
            "inputs": [{"boxId": input_box["boxId"], "extension": {}}],
            "dataInputs": [],
            "outputs": [
                {
                    "value": ANCHOR_VALUE,
                    "ergoTree": input_box["ergoTree"],
                    "creationHeight": height,
                    "assets": [],
                    "additionalRegisters": {
                        "R4": "0e20" + commitment  # 32-byte commitment
                    }
                },
                {
                    "value": change_val,
                    "ergoTree": input_box["ergoTree"],
                    "creationHeight": height,
                    "assets": [],
                    "additionalRegisters": {}
                }
            ]
        }
        
        # Sign
        sign_resp = self.session.post(ERGO_NODE + "/wallet/transaction/sign",
            json={"tx": unsigned_tx, "inputsRaw": [box_bytes], "dataInputsRaw": []})
        
        if sign_resp.status_code != 200:
            return {"success": False, "error": "Sign failed: " + sign_resp.text[:100]}
        
        signed = sign_resp.json()
        
        # Broadcast
        send_resp = self.session.post(ERGO_NODE + "/transactions", json=signed)
        
        if send_resp.status_code == 200:
            tx_id = send_resp.json()
            print("  SUCCESS! TX:", tx_id)
            
            # Save to DB
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS ergo_anchors (
                id INTEGER PRIMARY KEY, tx_id TEXT, commitment TEXT, 
                miner_count INTEGER, rc_slot INTEGER, created_at INTEGER)""")
            cur.execute("INSERT INTO ergo_anchors (tx_id, commitment, miner_count, rc_slot, created_at) VALUES (?, ?, ?, ?, ?)",
                       (str(tx_id), commitment, len(miners), rc_slot, int(time.time())))
            conn.commit()
            conn.close()
            
            return {"success": True, "tx_id": tx_id, "commitment": commitment}
        else:
            return {"success": False, "error": send_resp.text[:150]}
    
    def anchor_miners(self):
        miners = self.get_recent_miners(10)
        if not miners:
            return {"success": False, "error": "No miners"}
        
        print("\n=== Anchoring", len(miners), "miners to Ergo ===")
        for m in miners:
            print("  -", m.get("miner", "?")[:20] + ":", m.get("device_arch", "?"))
        
        return self.create_anchor_tx(miners)

if __name__ == "__main__":
    anchor = ErgoMinerAnchor()
    result = anchor.anchor_miners()
    print("\nResult:", json.dumps(result, indent=2))
