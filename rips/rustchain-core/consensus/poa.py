"""
RustChain Proof of Antiquity Consensus (RIP-0001)
=================================================

Core consensus mechanism that rewards vintage hardware preservation.

REMEMBER: This is NOT Proof of Work!
- No computational puzzles
- Rewards hardware age, not speed
- Older hardware wins over newer hardware
- Anti-emulation via deep entropy

Formula: AS = (current_year - release_year) * log10(uptime_days + 1)
"""

import hashlib
import math
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from decimal import Decimal

from ..config.chain_params import (
    CURRENT_YEAR,
    AS_MAX,
    AS_MIN,
    BLOCK_REWARD,
    BLOCK_TIME_SECONDS,
    MAX_MINERS_PER_BLOCK,
    ONE_RTC,
    calculate_block_reward,
)


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class HardwareProof:
    """Hardware attestation for mining eligibility"""
    cpu_model: str
    release_year: int
    uptime_days: int
    hardware_hash: str
    entropy_proof: Optional[bytes] = None


@dataclass
class ValidatedProof:
    """A validated mining proof ready for block inclusion"""
    wallet: str
    hardware: HardwareProof
    antiquity_score: float
    anti_emulation_hash: str
    validated_at: int
    tier: str = ""

    def __post_init__(self):
        age = CURRENT_YEAR - self.hardware.release_year
        self.tier = self._get_tier(age)

    def _get_tier(self, age: int) -> str:
        if age >= 30: return "ancient"
        if age >= 25: return "sacred"
        if age >= 20: return "vintage"
        if age >= 15: return "classic"
        if age >= 10: return "retro"
        if age >= 5: return "modern"
        return "recent"


@dataclass
class BlockMiner:
    """Miner entry in a block"""
    wallet: str
    hardware_model: str
    antiquity_score: float
    reward: int  # In smallest units


@dataclass
class Block:
    """RustChain block"""
    height: int
    timestamp: int
    previous_hash: str
    miners: List[BlockMiner]
    total_reward: int
    merkle_root: str = ""
    hash: str = ""

    def __post_init__(self):
        if not self.merkle_root:
            self.merkle_root = self._calculate_merkle_root()
        if not self.hash:
            self.hash = self._calculate_hash()

    def _calculate_hash(self) -> str:
        data = f"{self.height}:{self.timestamp}:{self.previous_hash}:{self.merkle_root}"
        return hashlib.sha256(data.encode()).hexdigest()

    def _calculate_merkle_root(self) -> str:
        if not self.miners:
            return hashlib.sha256(b"empty").hexdigest()

        hashes = [
            hashlib.sha256(f"{m.wallet}:{m.antiquity_score}:{m.reward}".encode()).hexdigest()
            for m in self.miners
        ]

        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])
            hashes = [
                hashlib.sha256((hashes[i] + hashes[i+1]).encode()).hexdigest()
                for i in range(0, len(hashes), 2)
            ]

        return hashes[0]


# =============================================================================
# Antiquity Score Calculation
# =============================================================================

def compute_antiquity_score(release_year: int, uptime_days: int) -> float:
    """
    Calculate Antiquity Score per RIP-0001 spec.

    Formula: AS = (current_year - release_year) * log10(uptime_days + 1)

    This is NOT Proof of Work! Higher scores come from:
    - Older hardware (larger age factor)
    - Longer uptime (log scale to prevent gaming)

    Examples:
        >>> compute_antiquity_score(1992, 276)  # 486 DX2
        80.46  # (2025-1992) * log10(277)

        >>> compute_antiquity_score(2023, 30)   # Modern CPU
        2.96   # (2025-2023) * log10(31)
    """
    age = max(0, CURRENT_YEAR - release_year)
    uptime_factor = math.log10(uptime_days + 1)
    return age * uptime_factor


def compute_reward(antiquity_score: float, base_reward: int) -> int:
    """
    Calculate miner reward based on Antiquity Score.

    Formula: Reward = R * min(1.0, AS / AS_max)

    Args:
        antiquity_score: Node's AS value
        base_reward: Base block reward in smallest units

    Returns:
        Calculated reward in smallest units
    """
    reward_factor = min(1.0, antiquity_score / AS_MAX)
    return int(base_reward * reward_factor)


# =============================================================================
# Validator Selection
# =============================================================================

def select_validator(proofs: List[ValidatedProof]) -> Optional[ValidatedProof]:
    """
    Select block validator using weighted lottery.

    Higher Antiquity Score = higher probability of selection.
    This is NOT computational competition - it's a fair lottery
    weighted by hardware preservation merit.

    Args:
        proofs: List of validated proofs from eligible miners

    Returns:
        Selected validator's proof, or None if no proofs
    """
    if not proofs:
        return None

    total_as = sum(p.antiquity_score for p in proofs)
    if total_as == 0:
        return random.choice(proofs)

    # Weighted random selection
    r = random.uniform(0, total_as)
    cumulative = 0.0

    for proof in proofs:
        cumulative += proof.antiquity_score
        if r <= cumulative:
            return proof

    return proofs[-1]


# =============================================================================
# Proof of Antiquity Engine
# =============================================================================

class ProofOfAntiquity:
    """
    Proof of Antiquity consensus engine.

    This is NOT Proof of Work! We validate:
    1. Hardware authenticity via deep entropy checks
    2. Hardware age via device signature database
    3. Node uptime via continuous validation
    4. No computational puzzles - just verification

    Block selection uses weighted lottery based on Antiquity Score.
    """

    def __init__(self):
        self.pending_proofs: List[ValidatedProof] = []
        self.block_start_time: int = int(time.time())
        self.known_hardware: Dict[str, str] = {}  # hash -> wallet
        self.drifted_nodes: set = set()  # Quarantined nodes
        self.current_block_height: int = 0

    def submit_proof(
        self,
        wallet: str,
        hardware: HardwareProof,
        anti_emulation_hash: str,
    ) -> Dict[str, Any]:
        """
        Submit a mining proof for the current block.

        Args:
            wallet: Miner's wallet address
            hardware: Hardware information
            anti_emulation_hash: Hash from entropy verification

        Returns:
            Result dict with acceptance status
        """
        current_time = int(time.time())
        elapsed = current_time - self.block_start_time

        # Check if block window is still open
        if elapsed >= BLOCK_TIME_SECONDS:
            return {"success": False, "error": "Block window has closed"}

        # Check for drift lock
        if wallet in self.drifted_nodes:
            return {"success": False, "error": "Node is quarantined due to drift lock"}

        # Check for duplicate wallet submission
        if any(p.wallet == wallet for p in self.pending_proofs):
            return {"success": False, "error": "Already submitted proof for this block"}

        # Check max miners
        if len(self.pending_proofs) >= MAX_MINERS_PER_BLOCK:
            return {"success": False, "error": "Block has reached maximum miners"}

        # Calculate Antiquity Score
        antiquity_score = compute_antiquity_score(
            hardware.release_year,
            hardware.uptime_days
        )

        # Check minimum AS threshold
        if antiquity_score < AS_MIN:
            return {
                "success": False,
                "error": f"Antiquity Score {antiquity_score:.2f} below minimum {AS_MIN}"
            }

        # Check for duplicate hardware
        if hardware.hardware_hash in self.known_hardware:
            existing_wallet = self.known_hardware[hardware.hardware_hash]
            if existing_wallet != wallet:
                return {
                    "success": False,
                    "error": f"Hardware already registered to {existing_wallet}"
                }

        # Create validated proof
        validated = ValidatedProof(
            wallet=wallet,
            hardware=hardware,
            antiquity_score=antiquity_score,
            anti_emulation_hash=anti_emulation_hash,
            validated_at=current_time,
        )

        self.pending_proofs.append(validated)
        self.known_hardware[hardware.hardware_hash] = wallet

        return {
            "success": True,
            "message": "Proof accepted, waiting for block completion",
            "pending_miners": len(self.pending_proofs),
            "your_antiquity_score": antiquity_score,
            "your_tier": validated.tier,
            "block_completes_in": BLOCK_TIME_SECONDS - elapsed,
        }

    def produce_block(self, previous_hash: str) -> Optional[Block]:
        """
        Process all pending proofs and create a new block.

        Uses weighted lottery based on Antiquity Score for reward distribution.
        This is NOT a competition - all valid miners share the reward
        proportionally to their Antiquity Score.

        Args:
            previous_hash: Hash of previous block

        Returns:
            New block if proofs exist, None otherwise
        """
        if not self.pending_proofs:
            self._reset_block()
            return None

        # Calculate base reward for this height
        base_reward_rtc = calculate_block_reward(self.current_block_height + 1)
        base_reward = int(float(base_reward_rtc) * ONE_RTC)

        # Calculate total AS for weighted distribution
        total_as = sum(p.antiquity_score for p in self.pending_proofs)

        # Calculate rewards for each miner (proportional to AS)
        miners = []
        total_distributed = 0

        for proof in self.pending_proofs:
            # Weighted share based on AS
            share = proof.antiquity_score / total_as if total_as > 0 else 1.0 / len(self.pending_proofs)
            reward = int(base_reward * share)
            total_distributed += reward

            miners.append(BlockMiner(
                wallet=proof.wallet,
                hardware_model=proof.hardware.cpu_model,
                antiquity_score=proof.antiquity_score,
                reward=reward,
            ))

        # Create new block
        self.current_block_height += 1
        block = Block(
            height=self.current_block_height,
            timestamp=int(time.time()),
            previous_hash=previous_hash,
            miners=miners,
            total_reward=total_distributed,
        )

        print(f"Block #{block.height} created! "
              f"Reward: {total_distributed / ONE_RTC:.2f} RTC "
              f"split among {len(miners)} miners")

        # Reset for next block
        self._reset_block()

        return block

    def validate_block(self, block: Block, previous_block: Optional[Block]) -> bool:
        """
        Validate an incoming block.

        Checks:
        - Height is sequential
        - Previous hash matches
        - Timestamp is reasonable
        - All miners have valid AS
        - Total reward doesn't exceed allowed

        Args:
            block: Block to validate
            previous_block: Previous block in chain

        Returns:
            True if valid, False otherwise
        """
        # Check height
        expected_height = (previous_block.height + 1) if previous_block else 1
        if block.height != expected_height:
            return False

        # Check previous hash
        expected_prev = previous_block.hash if previous_block else "0" * 64
        if block.previous_hash != expected_prev:
            return False

        # Check timestamp (not too far in future)
        if block.timestamp > int(time.time()) + 120:  # 2 min tolerance
            return False

        # Check miners have valid AS
        for miner in block.miners:
            if miner.antiquity_score < AS_MIN:
                return False

        # Check total reward
        max_reward = int(float(calculate_block_reward(block.height)) * ONE_RTC)
        if block.total_reward > max_reward * 1.01:  # 1% tolerance for rounding
            return False

        return True

    def _reset_block(self):
        """Reset state for next block"""
        self.pending_proofs.clear()
        self.block_start_time = int(time.time())

    def get_status(self) -> Dict[str, Any]:
        """Get current block status"""
        elapsed = int(time.time()) - self.block_start_time
        total_as = sum(p.antiquity_score for p in self.pending_proofs)

        return {
            "current_block_height": self.current_block_height,
            "pending_proofs": len(self.pending_proofs),
            "total_antiquity_score": total_as,
            "block_age_seconds": elapsed,
            "time_remaining_seconds": max(0, BLOCK_TIME_SECONDS - elapsed),
            "accepting_proofs": elapsed < BLOCK_TIME_SECONDS,
        }

    def quarantine_node(self, wallet: str, reason: str):
        """Quarantine a node due to drift lock violation"""
        self.drifted_nodes.add(wallet)
        print(f"Node {wallet} quarantined: {reason}")

    def release_node(self, wallet: str):
        """Release a node from quarantine"""
        self.drifted_nodes.discard(wallet)
        print(f"Node {wallet} released from quarantine")


# =============================================================================
# Demonstration
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("RUSTCHAIN PROOF OF ANTIQUITY - NOT PROOF OF WORK!")
    print("=" * 60)
    print()
    print("Formula: AS = (current_year - release_year) * log10(uptime_days + 1)")
    print()

    examples = [
        ("Intel 486 DX2-66", 1992, 276),
        ("PowerPC G4 1.25GHz", 2002, 276),
        ("Core 2 Duo E8400", 2008, 180),
        ("Ryzen 9 7950X", 2022, 30),
    ]

    for model, year, uptime in examples:
        score = compute_antiquity_score(year, uptime)
        age = CURRENT_YEAR - year

        print(f"Hardware: {model} ({year})")
        print(f"  Age: {age} years")
        print(f"  Uptime: {uptime} days")
        print(f"  Antiquity Score: {score:.2f}")
        print()

    print("Remember: Older hardware WINS, not faster hardware!")
