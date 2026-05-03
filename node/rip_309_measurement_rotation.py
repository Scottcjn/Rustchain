import hashlib
import random

ALL_FP_CHECKS = [
    "clock_drift",
    "instruction_latency",
    "memory_throughput",
    "cpu_identity",
    "pci_fingerprint",
    "disk_io_pattern"
]

def get_active_checks(prev_block_hash: str, count: int = 4) -> list:
    """
    Deterministically selects active checks for the current epoch 
    based on the previous block hash.
    """
    # 1. Derive measurement nonce
    nonce_seed = prev_block_hash + "measurement_nonce"
    nonce = hashlib.sha256(nonce_seed.encode()).hexdigest()
    
    # 2. Seed PRNG for rotation
    rng = random.Random(nonce)
    
    # 3. Sample 4 of 6 checks
    active = rng.sample(ALL_FP_CHECKS, count)
    return active

def calculate_weighted_reward(miner_results: dict, active_checks: list) -> float:
    """
    Calculates the reward multiplier based on the pass rate 
    of the CURRENTLY active checks.
    """
    passed_count = 0
    for check in active_checks:
        if miner_results.get(check, False):
            passed_count += 1
            
    # Return normalized pass rate (0.0 to 1.0)
    return passed_count / len(active_checks)

# Example Usage:
# active = get_active_checks("0000000000000000000123...")
# multiplier = calculate_weighted_reward({"clock_drift": True, ...}, active)
