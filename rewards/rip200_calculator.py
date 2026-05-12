"""
Fix RIP-200 rewards to properly apply Warthog bonus before SQLite cursor closes
"""
import sqlite3
from contextlib import contextmanager
from typing import Optional, Dict


class RewardCalculator:
    """Calculate RIP-200 rewards with proper Warthog bonus handling"""
    
    def __init__(self, db_path: str = ':memory:'):
        self.db_path = db_path
        self._conn = None
    
    @contextmanager
    def get_db_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()
    
    def calculate_reward(self, block_height: int, miner_address: str) -> Dict:
        """Calculate reward for a block with Warthog bonus"""
        reward = {
            'base_reward': 50,  # Base reward in RTC
            'warthog_bonus': 0,
            'total_reward': 50,
            'mixer_multiplier': 1.0,
        }
        
        # Fetch Warthog bonus BEFORE closing cursor
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get Warthog bonus
            cursor.execute(
                "SELECT bonus FROM warthog_bonuses WHERE miner = ? AND block <= ? ORDER BY block DESC LIMIT 1",
                (miner_address, block_height)
            )
            row = cursor.fetchone()
            if row:
                reward['warthog_bonus'] = row[0]
            
            # Get mixer multiplier
            cursor.execute(
                "SELECT multiplier FROM mixers WHERE miner = ? AND active = 1",
                (miner_address,)
            )
            mixer_row = cursor.fetchone()
            if mixer_row:
                reward['mixer_multiplier'] = mixer_row[0]
        
        # Calculate total (AFTER cursor is closed, but data is already fetched)
        reward['total_reward'] = int(
            (reward['base_reward'] + reward['warthog_bonus']) * reward['mixer_multiplier']
        )
        
        return reward
    
    def batch_calculate_rewards(self, block_heights: list, miner_address: str) -> list:
        """Batch calculate rewards for multiple blocks"""
        rewards = []
        
        # Use a single connection for all calculations
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            for block_height in block_heights:
                # Fetch data for this block
                cursor.execute(
                    "SELECT bonus FROM warthog_bonuses WHERE miner = ? AND block <= ? ORDER BY block DESC LIMIT 1",
                    (miner_address, block_height)
                )
                row = cursor.fetchone()
                warthog_bonus = row[0] if row else 0
                
                cursor.execute(
                    "SELECT multiplier FROM mixers WHERE miner = ? AND active = 1",
                    (miner_address,)
                )
                mixer_row = cursor.fetchone()
                mixer_multiplier = mixer_row[0] if mixer_row else 1.0
                
                total = int((50 + warthog_bonus) * mixer_multiplier)
                rewards.append({
                    'block': block_height,
                    'bonus': warthog_bonus,
                    'multiplier': mixer_multiplier,
                    'total': total
                })
        
        return rewards


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='RIP-200 Reward Calculator')
    parser.add_argument('--block', type=int, help='Block height')
    parser.add_argument('--miner', type=str, help='Miner address')
    parser.add_argument('--batch', action='store_true', help='Batch calculate')
    
    args = parser.parse_args()
    
    calculator = RewardCalculator()
    
    if args.block and args.miner:
        reward = calculator.calculate_reward(args.block, args.miner)
        print(f"Block: {args.block}")
        print(f"Miner: {args.miner}")
        print(f"Base Reward: {reward['base_reward']} RTC")
        print(f"Warthog Bonus: {reward['warthog_bonus']} RTC")
        print(f"Mixer Multiplier: {reward['mixer_multiplier']}x")
        print(f"Total Reward: {reward['total_reward']} RTC")
    elif args.batch:
        blocks = [1, 2, 3, 4, 5]
        miner = args.miner or 'test_miner'
        rewards = calculator.batch_calculate_rewards(blocks, miner)
        print("Batch Rewards:")
        for r in rewards:
            print(f"  Block {r['block']}: {r['total']} RTC (bonus: {r['bonus']}, mult: {r['multiplier']}x)")
    else:
        print("Please provide --block and --miner, or use --batch")


if __name__ == '__main__':
    main()
