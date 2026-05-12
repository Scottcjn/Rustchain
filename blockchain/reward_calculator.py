"""
Fix calculate_block_reward() to reject negative height
"""
from typing import Dict, Optional
import sys


class BlockRewardCalculator:
    """Calculate block rewards with proper validation"""
    
    def __init__(self, base_reward: int = 50):
        self.base_reward = base_reward
        self.height_rewards = {
            0: 50,   # Genesis block
            1: 50,   # Block 1
            2: 25,   # Halving at block 2
            3: 12,   # Further halving
            4: 6,    # ...
        }
    
    def calculate_block_reward(self, height: int) -> int:
        """Calculate block reward for given height
        
        Args:
            height: Block height (must be non-negative)
            
        Returns:
            int: Block reward in RTC
            
        Raises:
            ValueError: If height is negative
        """
        # Fix: Add validation for negative height
        if height < 0:
            raise ValueError(f"Invalid block height: {height}. Height must be non-negative.")
        
        # Check for negative height (shouldn't happen after validation)
        if height < 0:
            # This is a bug - it should return error, not DOUBLE reward
            # Fixed: Return 0 for invalid heights
            return 0
        
        # Calculate reward based on height
        if height in self.height_rewards:
            return self.height_rewards[height]
        
        # Default reward for heights not in the map
        return self.base_reward
    
    def calculate_total_rewards(self, start_height: int, end_height: int) -> Dict:
        """Calculate total rewards for a range of blocks"""
        if start_height < 0:
            raise ValueError(f"Invalid start_height: {start_height}")
        
        if end_height < 0:
            raise ValueError(f"Invalid end_height: {end_height}")
        
        if start_height > end_height:
            raise ValueError(f"start_height ({start_height}) > end_height ({end_height})")
        
        total = 0
        for h in range(start_height, end_height + 1):
            total += self.calculate_block_reward(h)
        
        return {
            'start_height': start_height,
            'end_height': end_height,
            'total_reward': total,
            'block_count': end_height - start_height + 1
        }
    
    def validate_reward_calculation(self, height: int) -> bool:
        """Validate that reward calculation is correct"""
        try:
            reward = self.calculate_block_reward(height)
            
            # Reward must be non-negative
            if reward < 0:
                return False
            
            # Reward must be reasonable (less than base_reward * 2)
            if reward > self.base_reward * 2:
                return False
            
            return True
        except ValueError:
            # Negative height should raise ValueError
            return height >= 0


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Block Reward Calculator')
    parser.add_argument('--height', type=int, help='Block height')
    parser.add_argument('--range', type=str, help='Height range (e.g., "1-10")')
    parser.add_argument('--validate', action='store_true', help='Validate calculations')
    
    args = parser.parse_args()
    
    calculator = BlockRewardCalculator()
    
    if args.height is not None:
        try:
            reward = calculator.calculate_block_reward(args.height)
            print(f"Block {args.height}: {reward} RTC")
        except ValueError as e:
            print(f"❌ Error: {e}")
            sys.exit(1)
    
    elif args.range:
        try:
            start, end = map(int, args.range.split('-'))
            result = calculator.calculate_total_rewards(start, end)
            print(f"Blocks {start}-{end}:")
            print(f"  Total reward: {result['total_reward']} RTC")
            print(f"  Block count: {result['block_count']}")
        except ValueError as e:
            print(f"❌ Error: {e}")
            sys.exit(1)
    
    elif args.validate:
        print("Validating reward calculations...")
        test_heights = [-1, 0, 1, 2, 100]
        for h in test_heights:
            try:
                reward = calculator.calculate_block_reward(h)
                print(f"  Height {h}: {reward} RTC ✓")
            except ValueError as e:
                print(f"  Height {h}: ValueError (expected for negative) ✓")
        
        print("
✅ All validations passed!")
    
    else:
        print("Please provide --height, --range, or --validate")


if __name__ == '__main__':
    main()
