"""
RustChain Proof of Antiquity Consensus (RIP-0001)
=================================================

Proof of Antiquity (PoA) is NOT Proof of Work!

PoA rewards:
- Hardware age (older = better)
- Node uptime (longer = better)
- Hardware authenticity (verified via deep entropy)

Formula: AS = (current_year - release_year) * log10(uptime_days + 1)
"""

import hashlib
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

from .core_types import (
    HardwareInfo,
    HardwareTier,
    WalletAddress,
    Block,
    BlockMiner,
    TokenAmount,
    BLOCK_REWARD,
    BLOCK_TIME_SECONDS,
    CURRENT_YEAR,
)


# =============================================================================
# Constants
# =============================================================================

AS_MAX: float = 100.0  # Maximum Antiquity Score for reward capping
AS_MIN: float = 1.0    # Minimum AS to participate in validation
MAX_MINERS_PER_BLOCK: int = 100
BLOCK_REWARD_AMOUNT: TokenAmount = TokenAmount.from_rtc(float(BLOCK_REWARD))


# =============================================================================
# Antiquity Score Calculation
# =============================================================================

def calculate_antiquity_score(release_year: int, uptime_days: int) -> float:
    """
    Calculate Antiquity Score per RIP-0001 spec.

    Formula: AS = (current_year - release_year) * log10(uptime_days + 1)

    Args:
        release_year: Year the hardware was manufactured
        uptime_days: Days since node started or last reboot

    Returns:
        Antiquity Score (AS)

    Examples:
        >>> calculate_antiquity_score(1992, 276)  # 486 DX2
        80.46  # (2025-1992) * log10(277) ≈ 33 * 2.44

        >>> calculate_antiquity_score(2002, 276)  # PowerPC G4
        56.10  # (2025-2002) * log10(277) ≈ 23 * 2.44

        >>> calculate_antiquity_score(2023, 30)   # Modern CPU
        2.96   # (2025-2023) * log10(31) ≈ 2 * 1.49
    """
    age = max(0, CURRENT_YEAR - release_year)
    uptime_factor = math.log10(uptime_days + 1)
    return age * uptime_factor


def calculate_reward(antiquity_score: float, total_reward: TokenAmount) -> TokenAmount:
    """
    Calculate reward based on Antiquity Score per RIP-0001.

    Formula: Reward = R * min(1.0, AS / AS_max)

    Args:
        antiquity_score: Node's AS value
        total_reward: Total block reward pool

    Returns:
        Calculated reward amount
    """
    reward_factor = min(1.0, antiquity_score / AS_MAX)
    reward_amount = int(total_reward.amount * reward_factor)
    return TokenAmount(reward_amount)


# =============================================================================
# Validated Proof
# =============================================================================

@dataclass
class ValidatedProof:
    """A validated mining proof ready for block inclusion"""
    wallet: WalletAddress
    hardware: HardwareInfo
    antiquity_score: float
    anti_emulation_hash: str
    validated_at: int
    entropy_proof: Optional[bytes] = None

    def to_dict(self):
        return {
            "wallet": self.wallet.address,
            "hardware": self.hardware.to_dict(),
            "antiquity_score": self.antiquity_score,
            "anti_emulation_hash": self.anti_emulation_hash,
            "validated_at": self.validated_at,
        }


# =============================================================================
# Proof Errors
# =============================================================================

class ProofError(Exception):
    """Base class for proof validation errors"""
    pass


class BlockWindowClosedError(ProofError):
    """Block window has closed"""
    pass


class DuplicateSubmissionError(ProofError):
    """Already submitted proof for this block"""
    pass


class BlockFullError(ProofError):
    """Block has reached maximum miners"""
    pass


class InsufficientAntiquityError(ProofError):
    """Antiquity Score below minimum threshold"""
    pass


class HardwareAlreadyRegisteredError(ProofError):
    """Hardware already registered to another wallet"""
    pass


class EmulationDetectedError(ProofError):
    """Emulation detected - hardware is not genuine"""
    pass


class DriftLockViolationError(ProofError):
    """Node behavior has drifted - quarantined per RIP-0003"""
    pass


# =============================================================================
# Proof of Antiquity Validator
# =============================================================================

class ProofOfAntiquity:
    """
    Proof of Antiquity consensus validator.

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
        self.known_hardware: Dict[str, WalletAddress] = {}  # hash -> wallet
        self.drifted_nodes: set = set()  # Quarantined nodes (RIP-0003)
        self.current_block_height: int = 0

    def submit_proof(
        self,
        wallet: WalletAddress,
        hardware: HardwareInfo,
        anti_emulation_hash: str,
        entropy_proof: Optional[bytes] = None,
    ) -> Dict:
        """
        Submit a mining proof for the current block.

        Args:
            wallet: Miner's wallet address
            hardware: Hardware information
            anti_emulation_hash: Hash from entropy verification
            entropy_proof: Optional detailed entropy proof

        Returns:
            Result dict with acceptance status

        Raises:
            Various ProofError subclasses on validation failure
        """
        current_time = int(time.time())
        elapsed = current_time - self.block_start_time

        # Check if block window is still open
        if elapsed >= BLOCK_TIME_SECONDS:
            raise BlockWindowClosedError("Block window has closed")

        # Check for drift lock (RIP-0003)
        if wallet.address in self.drifted_nodes:
            raise DriftLockViolationError(
                f"Node {wallet.address} is quarantined due to drift lock"
            )

        # Check for duplicate wallet submission
        existing = [p for p in self.pending_proofs if p.wallet == wallet]
        if existing:
            raise DuplicateSubmissionError(
                "Already submitted proof for this block"
            )

        # Check max miners
        if len(self.pending_proofs) >= MAX_MINERS_PER_BLOCK:
            raise BlockFullError("Block has reached maximum miners")

        # Calculate Antiquity Score
        antiquity_score = calculate_antiquity_score(
            hardware.release_year,
            hardware.uptime_days
        )

        # Check minimum AS threshold (RIP-0003)
        if antiquity_score < AS_MIN:
            raise InsufficientAntiquityError(
                f"Antiquity Score {antiquity_score:.2f} below minimum {AS_MIN}"
            )

        # Check for duplicate hardware
        hw_hash = hardware.generate_hardware_hash()
        if hw_hash in self.known_hardware:
            existing_wallet = self.known_hardware[hw_hash]
            if existing_wallet != wallet:
                raise HardwareAlreadyRegisteredError(
                    f"Hardware already registered to {existing_wallet.address}"
                )

        # Create validated proof
        validated = ValidatedProof(
            wallet=wallet,
            hardware=hardware,
            antiquity_score=antiquity_score,
            anti_emulation_hash=anti_emulation_hash,
            validated_at=current_time,
            entropy_proof=entropy_proof,
        )

        self.pending_proofs.append(validated)
        self.known_hardware[hw_hash] = wallet

        return {
            "success": True,
            "message": "Proof accepted, waiting for block completion",
            "pending_miners": len(self.pending_proofs),
            "your_antiquity_score": antiquity_score,
            "your_tier": hardware.tier.value,
            "block_completes_in": BLOCK_TIME_SECONDS - elapsed,
        }

    def process_block(self, previous_hash: str) -> Optional[Block]:
        """
        Process all pending proofs and create a new block.

        Uses weighted lottery based on Antiquity Score for validator selection.

        Args:
            previous_hash: Hash of previous block

        Returns:
            New block if proofs exist, None otherwise
        """
        if not self.pending_proofs:
            self._reset_block()
            return None

        # Calculate total AS for weighted distribution
        total_as = sum(p.antiquity_score for p in self.pending_proofs)

        # Calculate rewards for each miner (proportional to AS)
        miners = []
        total_distributed = 0

        for proof in self.pending_proofs:
            # Weighted share based on AS
            share = proof.antiquity_score / total_as
            reward = calculate_reward(
                proof.antiquity_score * share * len(self.pending_proofs),
                BLOCK_REWARD_AMOUNT
            )
            total_distributed += reward.amount

            miners.append(BlockMiner(
                wallet=proof.wallet,
                hardware=proof.hardware.cpu_model,
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
            total_reward=TokenAmount(total_distributed),
        )

        print(f"⛏️  Block #{block.height} created! "
              f"Reward: {block.total_reward.to_rtc()} RTC "
              f"split among {len(miners)} miners")

        # Reset for next block
        self._reset_block()

        return block

    def _reset_block(self):
        """Reset state for next block"""
        self.pending_proofs.clear()
        self.block_start_time = int(time.time())

    def get_status(self) -> Dict:
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

    def quarantine_node(self, wallet: WalletAddress, reason: str):
        """
        Quarantine a node due to drift lock violation (RIP-0003).

        Args:
            wallet: Node wallet to quarantine
            reason: Reason for quarantine
        """
        self.drifted_nodes.add(wallet.address)
        print(f"🚫 Node {wallet.address} quarantined: {reason}")

    def release_node(self, wallet: WalletAddress):
        """
        Release a node from quarantine after challenge passage (RIP-0003).

        Args:
            wallet: Node wallet to release
        """
        self.drifted_nodes.discard(wallet.address)
        print(f"✅ Node {wallet.address} released from quarantine")


# =============================================================================
# Validator Selection
# =============================================================================

def select_block_validator(proofs: List[ValidatedProof]) -> Optional[ValidatedProof]:
    """
    Select block validator using weighted lottery (RIP-0001).

    Higher Antiquity Score = higher probability of selection.

    Args:
        proofs: List of validated proofs

    Returns:
        Selected validator's proof, or None if no proofs
    """
    if not proofs:
        return None

    import random

    total_as = sum(p.antiquity_score for p in proofs)
    if total_as == 0:
        return random.choice(proofs)

    # Weighted random selection
    r = random.uniform(0, total_as)
    cumulative = 0

    for proof in proofs:
        cumulative += proof.antiquity_score
        if r <= cumulative:
            return proof

    return proofs[-1]


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    # Demo: Calculate AS for different hardware
    examples = [
        ("Intel 486 DX2-66", 1992, 276),
        ("PowerPC G4", 2002, 276),
        ("Core 2 Duo", 2006, 180),
        ("Ryzen 9 7950X", 2022, 30),
    ]

    print("=" * 60)
    print("RUSTCHAIN PROOF OF ANTIQUITY - ANTIQUITY SCORE CALCULATOR")
    print("=" * 60)
    print(f"Formula: AS = (2025 - release_year) * log10(uptime_days + 1)")
    print("=" * 60)
    print()

    for model, year, uptime in examples:
        hw = HardwareInfo(cpu_model=model, release_year=year, uptime_days=uptime)
        as_score = calculate_antiquity_score(year, uptime)
        tier = HardwareTier.from_release_year(year)

        print(f"📟 {model} ({year})")
        print(f"   Age: {CURRENT_YEAR - year} years")
        print(f"   Uptime: {uptime} days")
        print(f"   Tier: {tier.value.upper()} ({tier.multiplier}x)")
        print(f"   Antiquity Score: {as_score:.2f}")
        print()

    print("💡 Remember: This is NOT Proof of Work!")
    print("   Older hardware with longer uptime wins, not faster hardware.")
