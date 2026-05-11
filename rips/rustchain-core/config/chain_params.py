from decimal import Decimal

# Constants for Rustchain
BLOCK_REWARD = Decimal("1.5")
HALVING_INTERVAL_BLOCKS = 210000
HALVING_COUNT = 64

def calculate_block_reward(height: int) -> Decimal:
    """
    Calculates the block reward for a given height.
    Fix: Added validation to ensure height is non-negative.
    """
    if height < 0:
        raise ValueError(f"Block height cannot be negative: {height}")
        
    halvings = height // HALVING_INTERVAL_BLOCKS
    if halvings >= HALVING_COUNT:
        return BLOCK_REWARD / Decimal(2 ** HALVING_COUNT)
    return BLOCK_REWARD / Decimal(2 ** halvings)
