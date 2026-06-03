import sqlite3
import hashlib
import json
import time

def setup_mock_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE utxo_boxes (
            box_id TEXT PRIMARY KEY,
            value_nrtc INTEGER NOT NULL,
            spent_at INTEGER,
            owner_address TEXT,
            proposition TEXT,
            creation_height INTEGER,
            transaction_id TEXT,
            output_index INTEGER,
            tokens_json TEXT,
            registers_json TEXT,
            created_at INTEGER
        )
    """)
    return conn

def simulate_dust_inflation():
    conn = setup_mock_db()
    DUST_THRESHOLD = 1000
    
    # 1. Attacker has 10,000 nanoRTC
    conn.execute("INSERT INTO utxo_boxes (box_id, value_nrtc, owner_address, spent_at) VALUES ('box1', 10000, 'attacker', NULL)")
    
    print("Initial Total Supply (UTXO): 10,000 nRTC")
    
    # 2. Attacker sends 9,500 nRTC to themselves
    # target_nrtc = 9500
    # total = 10000
    # change = 10000 - 9500 = 500
    # Since 500 < DUST_THRESHOLD, change becomes 0.
    
    amount_to_send = 9500
    # Simulation of coin_select logic
    total_input = 10000
    change = total_input - amount_to_send
    if change < DUST_THRESHOLD:
        effective_change = 0
    else:
        effective_change = change
        
    print(f"Sending {amount_to_send} nRTC. Raw change: {change}. Effective change: {effective_change}")
    
    # Apply transaction
    conn.execute("UPDATE utxo_boxes SET spent_at = 123 WHERE box_id = 'box1'")
    conn.execute("INSERT INTO utxo_boxes (box_id, value_nrtc, owner_address, spent_at) VALUES ('box2', 9500, 'attacker', NULL)")
    
    # Integrity check
    supply = conn.execute("SELECT SUM(value_nrtc) FROM utxo_boxes WHERE spent_at IS NULL").fetchone()[0]
    print(f"Total Supply after tx: {supply} nRTC")
    print(f"Supply change: {supply - 10000} nRTC (Inflation/Deflation)")

if __name__ == "__main__":
    simulate_dust_inflation()
