"""
Fix Agent Economy create_bounty to import timedelta
"""
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class BountyManager:
    """Manage bounties in Agent Economy"""
    
    def __init__(self, db_connection):
        self.db = db_connection
        self.created_bounties = []
    
    def create_bounty(self, 
                    creator: str, 
                    amount: float, 
                    description: str, 
                    deadline_hours: int = 24) -> Dict:
        """Create a new bounty"""
        # Fix: Import timedelta at the top of the file
        deadline = datetime.now() + timedelta(hours=deadline_hours)
        
        bounty = {
            'id': self._generate_id(),
            'creator': creator,
            'amount': amount,
            'description': description,
            'deadline': deadline.isoformat(),
            'status': 'open',
            'created_at': datetime.now().isoformat(),
            'claimed_by': None,
            'completed_at': None
        }
        
        # Save to database
        cursor = self.db.cursor()
        cursor.execute(
            "INSERT INTO bounties (id, creator, amount, description, deadline, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (bounty['id'], creator, amount, description, bounty['deadline'], 'open', bounty['created_at'])
        )
        self.db.commit()
        
        self.created_bounties.append(bounty)
        return bounty
    
    def claim_bounty(self, bounty_id: str, claimer: str) -> Dict:
        """Claim a bounty"""
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM bounties WHERE id = ? AND status = 'open'", (bounty_id,))
        row = cursor.fetchone()
        
        if not row:
            raise ValueError(f"Bounty {bounty_id} not found or already claimed")
        
        # Update bounty
        cursor.execute(
            "UPDATE bounties SET status = 'claimed', claimed_by = ?, claimed_at = ? WHERE id = ?",
            (claimer, datetime.now().isoformat(), bounty_id)
        )
        self.db.commit()
        
        return {
            'bounty_id': bounty_id,
            'claimer': claimer,
            'status': 'claimed'
        }
    
    def complete_bounty(self, bounty_id: str, completer: str) -> Dict:
        """Complete a bounty and release reward"""
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM bounties WHERE id = ? AND claimed_by = ?", (bounty_id, completer))
        row = cursor.fetchone()
        
        if not row:
            raise ValueError(f"Bounty {bounty_id} not found or not claimed by {completer}")
        
        # Update bounty
        cursor.execute(
            "UPDATE bounties SET status = 'completed', completed_at = ? WHERE id = ?",
            (datetime.now().isoformat(), bounty_id)
        )
        self.db.commit()
        
        # Release reward
        reward = row[2]  # amount is at index 2
        self._transfer_funds(row[1], completer, reward)  # creator, completer, amount
        
        return {
            'bounty_id': bounty_id,
            'completer': completer,
            'reward': reward,
            'status': 'completed'
        }
    
    def get_open_bounties(self) -> List[Dict]:
        """Get all open bounties"""
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM bounties WHERE status = 'open' ORDER BY created_at DESC")
        
        bounties = []
        for row in cursor.fetchall():
            bounties.append({
                'id': row[0],
                'creator': row[1],
                'amount': row[2],
                'description': row[3],
                'deadline': row[4],
                'status': row[5],
                'created_at': row[6]
            })
        
        return bounties
    
    def _generate_id(self) -> str:
        """Generate unique bounty ID"""
        import hashlib
        unique_str = f"{datetime.now().isoformat()}{len(self.created_bounties)}"
        return hashlib.sha256(unique_str.encode()).hexdigest()[:16]
    
    def _transfer_funds(self, from_user: str, to_user: str, amount: float):
        """Transfer funds between users"""
        # This would integrate with the blockchain/RTC system
        print(f"Transferring {amount} RTC from {from_user} to {to_user}")
        pass


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Bounty Manager')
    parser.add_argument('--create', action='store_true', help='Create a bounty')
    parser.add_argument('--claim', type=str, help='Claim a bounty by ID')
    parser.add_argument('--complete', type=str, help='Complete a bounty by ID')
    parser.add_argument('--list', action='store_true', help='List open bounties')
    
    args = parser.parse_args()
    
    # Mock database connection
    import sqlite3
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE bounties (id TEXT, creator TEXT, amount REAL, description TEXT, deadline TEXT, status TEXT, created_at TEXT)')
    
    manager = BountyManager(conn)
    
    if args.create:
        bounty = manager.create_bounty('test_creator', 100.0, 'Fix bug in module X')
        print(f"Created bounty: {bounty['id']}")
    elif args.claim:
        result = manager.claim_bounty(args.claim, 'test_claimer')
        print(f"Claimed: {result}")
    elif args.complete:
        result = manager.complete_bounty(args.complete, 'test_claimer')
        print(f"Completed: {result}")
    elif args.list:
        bounties = manager.get_open_bounties()
        print(f"Open bounties: {len(bounties)}")
        for b in bounties:
            print(f"  {b['id']}: {b['description']} ({b['amount']} RTC)")
    else:
        print("Please provide an action: --create, --claim, --complete, or --list")


if __name__ == '__main__':
    main()
