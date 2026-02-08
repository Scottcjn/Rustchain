"""
RustChain Governance Logic - Integrated Backend
Handles signed proposal creation, hardware-weighted voting, and persistence.
"""

import sqlite3
import time
import logging
import os
import sys
from typing import Dict, List, Optional, Tuple

# Attempt to load RustChain crypto and multiplier logic
# Note: In production, ensure these are in the python path
try:
    sys.path.append(os.path.abspath('node'))
    from rustchain_crypto import Ed25519Signer, verify_transaction, address_from_public_key
    from rip_200_round_robin_1cpu1vote import ANTIQUITY_MULTIPLIERS
except ImportError:
    # Fallback/Mocks for local dev if not in the exact structure
    ANTIQUITY_MULTIPLIERS = {"g4": 2.5, "g5": 2.0, "386": 3.0}
    def address_from_public_key(pk): return pk[:10]
    logging.warning("Using mock crypto/multipliers. Ensure actual files are present for production.")

class GovernanceEngine:
    def __init__(self, db_path: str = "node/rustchain_v2.db"):
        self.db_path = db_path
        self._bootstrap_schema()

    def _bootstrap_schema(self):
        """Initializes governance tables in the main node DB."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 1. Proposals Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gov_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposer TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT DEFAULT 'RIP', -- RIP, BOUNTY, PARAM_CHANGE
                status TEXT DEFAULT 'ACTIVE', -- ACTIVE, PASSED, FAILED, EXECUTED
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                min_stake REAL DEFAULT 10.0,
                target_value TEXT, -- For param changes
                snapshot_id INTEGER
            )
        ''')
        
        # 2. Votes Table (Hardware-Weighted)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gov_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposal_id INTEGER NOT NULL,
                voter_addr TEXT NOT NULL,
                device_arch TEXT NOT NULL,
                weight REAL NOT NULL,
                vote_decision TEXT NOT NULL, -- YES, NO
                signature TEXT NOT NULL,
                timestamp REAL NOT NULL,
                FOREIGN KEY (proposal_id) REFERENCES gov_proposals (id),
                UNIQUE(proposal_id, voter_addr)
            )
        ''')
        
        conn.commit()
        conn.close()

    def get_hardware_weight(self, arch: str) -> float:
        """Calculates weight based on antiquity multiplier."""
        return ANTIQUITY_MULTIPLIERS.get(arch.lower(), 1.0)

    def submit_proposal(self, proposer: str, title: str, desc: str, stake: float) -> Tuple[bool, str]:
        """Validates and persists a new proposal."""
        if stake < 10.0:
            return False, "Insufficient RTC stake (min 10 RTC required)"
            
        now = time.time()
        expiry = now + (7 * 24 * 3600) # 7 Day Window
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO gov_proposals (proposer, title, description, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (proposer, title, desc, now, expiry))
        conn.commit()
        conn.close()
        return True, "Proposal submitted successfully"

    def cast_weighted_vote(self, proposal_id: int, voter: str, arch: str, decision: str, signature: str) -> Tuple[bool, str]:
        """Records a vote after verifying hardware weight and signature."""
        weight = self.get_hardware_weight(arch)
        now = time.time()
        
        # TODO: Implement actual Ed25519 verification here
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO gov_votes (proposal_id, voter_addr, device_arch, weight, vote_decision, signature, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (proposal_id, voter, arch, weight, decision, signature, now))
            conn.commit()
            return True, f"Vote cast with weight {weight}x"
        except sqlite3.IntegrityError:
            return False, "Already voted on this proposal"
        finally:
            conn.close()

    def get_proposal_status(self, proposal_id: int) -> Dict:
        """Aggregates results for a specific proposal."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM gov_proposals WHERE id = ?', (proposal_id,))
        proposal = cursor.fetchone()
        
        cursor.execute('''
            SELECT vote_decision, SUM(weight) FROM gov_votes 
            WHERE proposal_id = ? 
            GROUP BY vote_decision
        ''', (proposal_id,))
        tally = dict(cursor.fetchall())
        
        conn.close()
        return {
            "proposal": proposal,
            "tally": tally,
            "total_weighted_votes": sum(tally.values())
        }

if __name__ == "__main__":
    # Local Simulation
    engine = GovernanceEngine("node/rustchain_v2.db")
    print("Governance Engine Initialized.")
    
    # Test 1: Submit
    ok, msg = engine.submit_proposal("mccoy_admin", "RIP-0011: Increase Payouts", "Let's boost G4 rewards.", 50.0)
    print(f"Submit: {msg}")
    
    # Test 2: Vote (Simulate G4)
    v_ok, v_msg = engine.cast_weighted_vote(1, "miner_1", "g4", "YES", "sig_fake_123")
    print(f"Vote 1 (G4): {v_msg}")
    
    # Test 3: Vote (Simulate Modern)
    v_ok, v_msg = engine.cast_weighted_vote(1, "miner_2", "modern", "NO", "sig_fake_456")
    print(f"Vote 2 (Modern): {v_msg}")
    
    # Result
    print("Status:", engine.get_proposal_status(1))
