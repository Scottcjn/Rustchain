"""
RustChain Validator & Antiquity Score (RIP-0001, RIP-0003)
==========================================================

Hardware validation, Antiquity Score calculation, and drift lock management.

Security Mechanisms:
- Hardware fingerprinting via deep entropy
- Drift detection for behavioral anomalies
- Quarantine system for suspected emulators
- Reputation tracking for long-term behavior
"""

import hashlib
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

from ..config.chain_params import (
    CURRENT_YEAR,
    AS_MAX,
    AS_MIN,
    HARDWARE_TIERS,
    DRIFT_THRESHOLD,
    QUARANTINE_DURATION_BLOCKS,
    ENTROPY_WEIGHTS,
    EMULATION_PROBABILITY_THRESHOLD,
    MIN_ENTROPY_SCORE,
)


# =============================================================================
# Hardware Database
# =============================================================================

# Known CPU models with release years (for validation)
HARDWARE_DATABASE: Dict[str, Dict[str, Any]] = {
    # Ancient (30+ years) - 3.5x multiplier
    "486DX2": {"year": 1992, "family": "x86", "arch": "i486"},
    "486DX4": {"year": 1994, "family": "x86", "arch": "i486"},
    "68040": {"year": 1990, "family": "68k", "arch": "m68k"},

    # Sacred (25-29 years) - 3.0x multiplier
    "Pentium": {"year": 1993, "family": "x86", "arch": "P5"},
    "Pentium Pro": {"year": 1995, "family": "x86", "arch": "P6"},
    "Pentium II": {"year": 1997, "family": "x86", "arch": "P6"},
    "PowerPC 601": {"year": 1993, "family": "ppc", "arch": "POWER"},
    "PowerPC 603": {"year": 1994, "family": "ppc", "arch": "POWER"},
    "Alpha 21064": {"year": 1992, "family": "alpha", "arch": "EV4"},

    # Vintage (20-24 years) - 2.5x multiplier
    "Pentium III": {"year": 1999, "family": "x86", "arch": "P6"},
    "Pentium 4": {"year": 2000, "family": "x86", "arch": "NetBurst"},
    "PowerPC G4": {"year": 1999, "family": "ppc", "arch": "G4"},
    "Athlon": {"year": 1999, "family": "x86", "arch": "K7"},

    # Classic (15-19 years) - 2.0x multiplier
    "Core 2 Duo": {"year": 2006, "family": "x86", "arch": "Core"},
    "Core 2 Quad": {"year": 2007, "family": "x86", "arch": "Core"},
    "PowerPC G5": {"year": 2003, "family": "ppc", "arch": "G5"},
    "Athlon 64": {"year": 2003, "family": "x86", "arch": "K8"},
    "Opteron": {"year": 2003, "family": "x86", "arch": "K8"},

    # Retro (10-14 years) - 1.5x multiplier
    "Core i7 Nehalem": {"year": 2008, "family": "x86", "arch": "Nehalem"},
    "Core i5 Sandy Bridge": {"year": 2011, "family": "x86", "arch": "Sandy Bridge"},
    "FX-8350": {"year": 2012, "family": "x86", "arch": "Piledriver"},

    # Modern (5-9 years) - 1.0x multiplier
    "Core i7 Skylake": {"year": 2015, "family": "x86", "arch": "Skylake"},
    "Ryzen 7 1800X": {"year": 2017, "family": "x86", "arch": "Zen"},
    "Ryzen 9 3900X": {"year": 2019, "family": "x86", "arch": "Zen2"},

    # Recent (0-4 years) - 0.5x penalty
    "Core i9 12900K": {"year": 2021, "family": "x86", "arch": "Alder Lake"},
    "Ryzen 9 7950X": {"year": 2022, "family": "x86", "arch": "Zen4"},
    "Apple M1": {"year": 2020, "family": "arm", "arch": "Apple Silicon"},
    "Apple M3": {"year": 2023, "family": "arm", "arch": "Apple Silicon"},
}


# =============================================================================
# Hardware Validation
# =============================================================================

@dataclass
class HardwareInfo:
    """Validated hardware information"""
    cpu_model: str
    release_year: int
    uptime_days: int
    architecture: str = "x86"
    unique_id: str = ""
    tier: str = ""
    multiplier: float = 1.0
    age_years: int = 0

    def __post_init__(self):
        self.age_years = CURRENT_YEAR - self.release_year
        self.tier = self._compute_tier()
        self.multiplier = HARDWARE_TIERS.get(self.tier, {}).get("multiplier", 0.5)

    def _compute_tier(self) -> str:
        for tier_name, params in HARDWARE_TIERS.items():
            if params["min_age"] <= self.age_years <= params["max_age"]:
                return tier_name
        return "recent"

    def generate_hardware_hash(self) -> str:
        """Generate unique hardware fingerprint"""
        data = f"{self.cpu_model}:{self.architecture}:{self.unique_id}"
        return hashlib.sha256(data.encode()).hexdigest()


def validate_hardware_claim(model: str, claimed_year: int) -> Tuple[bool, str]:
    """
    Validate a hardware claim against known database.

    Security: Prevents false claims about hardware age.

    Args:
        model: CPU model string
        claimed_year: Year claimed by node

    Returns:
        (valid, message) tuple
    """
    # Check if model is in database
    for known_model, info in HARDWARE_DATABASE.items():
        if known_model.lower() in model.lower():
            actual_year = info["year"]
            # Allow 1-year tolerance for variants
            if abs(claimed_year - actual_year) <= 1:
                return True, f"Hardware validated: {known_model} ({actual_year})"
            else:
                return False, f"Year mismatch: claimed {claimed_year}, actual {actual_year}"

    # Unknown hardware - allow with warning
    return True, f"Unknown hardware: {model} - accepting claimed year {claimed_year}"


# =============================================================================
# Antiquity Score Calculator
# =============================================================================

def calculate_antiquity_score(release_year: int, uptime_days: int) -> float:
    """
    Calculate Antiquity Score per RIP-0001 spec.

    Formula: AS = (current_year - release_year) * log10(uptime_days + 1)

    This is NOT Proof of Work! Rewards:
    - Hardware preservation (age)
    - Node reliability (uptime)
    - NOT computational speed
    """
    age = max(0, CURRENT_YEAR - release_year)
    uptime_factor = math.log10(uptime_days + 1)
    return age * uptime_factor


def calculate_effective_score(base_score: float, tier: str, reputation: float = 1.0) -> float:
    """
    Calculate effective score with tier multiplier and reputation.

    Args:
        base_score: Raw Antiquity Score
        tier: Hardware tier
        reputation: Reputation multiplier (0.0 - 1.0)

    Returns:
        Effective score for mining weight
    """
    multiplier = HARDWARE_TIERS.get(tier, {}).get("multiplier", 0.5)
    return base_score * multiplier * reputation


# =============================================================================
# Drift Lock System (RIP-0003)
# =============================================================================

class DriftStatus(Enum):
    """Node drift status"""
    NORMAL = "normal"
    WARNING = "warning"
    QUARANTINED = "quarantined"


@dataclass
class DriftRecord:
    """Record of a node's behavioral drift"""
    wallet: str
    baseline_score: float
    current_score: float
    drift_percentage: float
    status: DriftStatus
    quarantine_until_block: Optional[int] = None
    violations: List[str] = field(default_factory=list)


class DriftLockManager:
    """
    Drift Lock System - detects emulation attempts via behavioral analysis.

    Security Principle: Real vintage hardware has consistent, predictable behavior.
    Emulators often show inconsistent timing, entropy, or performance patterns.

    When drift exceeds threshold:
    1. Node enters WARNING state
    2. Challenged to prove hardware authenticity
    3. Failed challenge = QUARANTINE
    4. Quarantine lasts QUARANTINE_DURATION_BLOCKS
    """

    def __init__(self):
        self._baselines: Dict[str, float] = {}
        self._history: Dict[str, List[float]] = {}
        self._drift_records: Dict[str, DriftRecord] = {}
        self._quarantined: set = set()

    def record_score(self, wallet: str, score: float):
        """Record a score observation for drift analysis"""
        if wallet not in self._history:
            self._history[wallet] = []
            self._baselines[wallet] = score

        self._history[wallet].append(score)

        # Keep last 100 observations
        if len(self._history[wallet]) > 100:
            self._history[wallet] = self._history[wallet][-100:]

        # Update baseline (rolling average)
        if len(self._history[wallet]) >= 10:
            self._baselines[wallet] = sum(self._history[wallet]) / len(self._history[wallet])

    def check_drift(self, wallet: str, current_score: float) -> DriftRecord:
        """
        Check if a node's behavior has drifted from baseline.

        Drift indicates possible:
        - Emulation attempt
        - Hardware swap
        - System instability
        """
        baseline = self._baselines.get(wallet, current_score)

        if baseline == 0:
            drift_pct = 0.0
        else:
            drift_pct = abs(current_score - baseline) / baseline

        violations = []
        status = DriftStatus.NORMAL

        if drift_pct > DRIFT_THRESHOLD:
            violations.append(f"Score drift: {drift_pct:.1%} > {DRIFT_THRESHOLD:.0%}")
            status = DriftStatus.WARNING

        if drift_pct > DRIFT_THRESHOLD * 2:
            status = DriftStatus.QUARANTINED
            self._quarantined.add(wallet)

        record = DriftRecord(
            wallet=wallet,
            baseline_score=baseline,
            current_score=current_score,
            drift_percentage=drift_pct,
            status=status,
            violations=violations,
        )

        self._drift_records[wallet] = record
        return record

    def quarantine_node(self, wallet: str, current_block: int, reason: str):
        """Place a node in quarantine"""
        self._quarantined.add(wallet)

        record = self._drift_records.get(wallet, DriftRecord(
            wallet=wallet,
            baseline_score=0,
            current_score=0,
            drift_percentage=0,
            status=DriftStatus.QUARANTINED,
        ))

        record.status = DriftStatus.QUARANTINED
        record.quarantine_until_block = current_block + QUARANTINE_DURATION_BLOCKS
        record.violations.append(reason)

        self._drift_records[wallet] = record
        print(f"Node {wallet[:16]}... QUARANTINED: {reason}")

    def release_from_quarantine(self, wallet: str, current_block: int) -> bool:
        """Check if node can be released from quarantine"""
        record = self._drift_records.get(wallet)
        if not record or record.status != DriftStatus.QUARANTINED:
            return True

        if record.quarantine_until_block and current_block >= record.quarantine_until_block:
            self._quarantined.discard(wallet)
            record.status = DriftStatus.NORMAL
            record.quarantine_until_block = None
            print(f"Node {wallet[:16]}... released from quarantine")
            return True

        return False

    def is_quarantined(self, wallet: str) -> bool:
        """Check if a node is currently quarantined"""
        return wallet in self._quarantined


# =============================================================================
# Deep Entropy Verification
# =============================================================================

@dataclass
class EntropyProof:
    """Entropy proof from hardware verification"""
    instruction_timing: float
    memory_patterns: float
    bus_timing: float
    thermal_signature: float
    architectural_quirks: float
    combined_score: float = 0.0
    signature_hash: str = ""

    def __post_init__(self):
        self.combined_score = self._calculate_combined()
        self.signature_hash = self._generate_hash()

    def _calculate_combined(self) -> float:
        """Calculate weighted combined score"""
        return (
            ENTROPY_WEIGHTS["instruction_timing"] * self.instruction_timing +
            ENTROPY_WEIGHTS["memory_patterns"] * self.memory_patterns +
            ENTROPY_WEIGHTS["bus_timing"] * self.bus_timing +
            ENTROPY_WEIGHTS["thermal_signature"] * self.thermal_signature +
            ENTROPY_WEIGHTS["architectural_quirks"] * self.architectural_quirks
        )

    def _generate_hash(self) -> str:
        data = f"{self.instruction_timing}:{self.memory_patterns}:{self.bus_timing}"
        return hashlib.sha256(data.encode()).hexdigest()


class EntropyVerifier:
    """
    Deep Entropy Verification System.

    Core Security Principle:
    "It's cheaper to buy a $50 486 than to emulate one"

    Verification Layers:
    1. Instruction Timing - CPU cycle variations
    2. Memory Patterns - Cache/RAM behavior
    3. Bus Timing - I/O timing characteristics
    4. Thermal Signature - Heat patterns under load
    5. Architectural Quirks - Known hardware bugs/features
    """

    def verify(self, proof: EntropyProof, hardware: HardwareInfo) -> Tuple[bool, float, str]:
        """
        Verify an entropy proof.

        Args:
            proof: Entropy proof to verify
            hardware: Claimed hardware info

        Returns:
            (valid, emulation_probability, message)
        """
        # Check minimum score
        if proof.combined_score < MIN_ENTROPY_SCORE:
            return False, 1.0, f"Entropy score {proof.combined_score:.2f} below minimum"

        # Calculate emulation probability
        # Real hardware has consistent, high entropy
        # Emulators typically fail on timing precision
        emulation_prob = self._estimate_emulation_probability(proof, hardware)

        if emulation_prob > EMULATION_PROBABILITY_THRESHOLD:
            return False, emulation_prob, f"High emulation probability: {emulation_prob:.1%}"

        return True, emulation_prob, "Hardware verification passed"

    def _estimate_emulation_probability(self, proof: EntropyProof, hardware: HardwareInfo) -> float:
        """
        Estimate probability that hardware is emulated.

        Factors:
        - Too-perfect timing = likely emulator
        - Too-uniform patterns = likely emulator
        - Missing quirks = likely emulator
        """
        prob = 0.0

        # Perfect timing is suspicious (real hardware has jitter)
        if proof.instruction_timing > 0.99:
            prob += 0.3  # Too perfect

        # Uniform memory patterns are suspicious
        if proof.memory_patterns > 0.99:
            prob += 0.2

        # Vintage hardware should have quirks
        if hardware.age_years >= 20 and proof.architectural_quirks < 0.5:
            prob += 0.3  # Old hardware without quirks = suspicious

        # Bus timing should vary
        if proof.bus_timing > 0.98:
            prob += 0.2

        return min(1.0, prob)


# =============================================================================
# Reputation System
# =============================================================================

@dataclass
class NodeReputation:
    """Node reputation tracking for long-term behavior"""
    wallet: str
    score: float = 50.0  # Start neutral (0-100)
    total_blocks: int = 0
    successful_validations: int = 0
    drift_violations: int = 0
    last_active: int = 0

    def update(self, block_validated: bool, drift_ok: bool):
        """Update reputation based on recent behavior"""
        self.total_blocks += 1
        self.last_active = int(time.time())

        if block_validated:
            self.successful_validations += 1
            self.score = min(100, self.score + 0.5)

        if not drift_ok:
            self.drift_violations += 1
            self.score = max(0, self.score - 5.0)

    @property
    def reliability_factor(self) -> float:
        """Get reliability factor (0.0 - 1.0) for scoring"""
        return self.score / 100.0


# =============================================================================
# Complete Validator
# =============================================================================

class HardwareValidator:
    """
    Complete hardware validation system combining all checks.

    Validates:
    1. Hardware claim authenticity
    2. Antiquity Score calculation
    3. Entropy proof verification
    4. Drift lock status
    5. Reputation
    """

    def __init__(self):
        self.drift_manager = DriftLockManager()
        self.entropy_verifier = EntropyVerifier()
        self.reputations: Dict[str, NodeReputation] = {}

    def validate_miner(
        self,
        wallet: str,
        hardware: HardwareInfo,
        entropy_proof: Optional[EntropyProof] = None,
        current_block: int = 0,
    ) -> Dict[str, Any]:
        """
        Complete validation of a miner.

        Returns:
            Validation result with score and eligibility
        """
        result = {
            "wallet": wallet,
            "eligible": True,
            "errors": [],
            "warnings": [],
        }

        # 1. Check quarantine status
        if self.drift_manager.is_quarantined(wallet):
            released = self.drift_manager.release_from_quarantine(wallet, current_block)
            if not released:
                result["eligible"] = False
                result["errors"].append("Node is quarantined")
                return result

        # 2. Validate hardware claim
        valid, msg = validate_hardware_claim(hardware.cpu_model, hardware.release_year)
        if not valid:
            result["eligible"] = False
            result["errors"].append(msg)
            return result

        # 3. Calculate Antiquity Score
        base_score = calculate_antiquity_score(hardware.release_year, hardware.uptime_days)
        if base_score < AS_MIN:
            result["eligible"] = False
            result["errors"].append(f"Antiquity Score {base_score:.2f} below minimum {AS_MIN}")
            return result

        # 4. Verify entropy proof if provided
        if entropy_proof:
            valid, emul_prob, msg = self.entropy_verifier.verify(entropy_proof, hardware)
            if not valid:
                result["eligible"] = False
                result["errors"].append(msg)
                return result
            result["emulation_probability"] = emul_prob

        # 5. Check drift
        drift = self.drift_manager.check_drift(wallet, base_score)
        if drift.status == DriftStatus.QUARANTINED:
            result["eligible"] = False
            result["errors"].append("Drift lock triggered")
            return result
        elif drift.status == DriftStatus.WARNING:
            result["warnings"].append(f"Drift warning: {drift.drift_percentage:.1%}")

        # 6. Get reputation
        rep = self.reputations.get(wallet, NodeReputation(wallet=wallet))

        # 7. Calculate final score
        effective_score = calculate_effective_score(
            base_score,
            hardware.tier,
            rep.reliability_factor
        )

        result["antiquity_score"] = base_score
        result["effective_score"] = effective_score
        result["tier"] = hardware.tier
        result["multiplier"] = hardware.multiplier
        result["reputation"] = rep.score

        return result


# =============================================================================
# Tests
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("RUSTCHAIN VALIDATOR - ANTIQUITY SCORE CALCULATOR")
    print("=" * 60)

    validator = HardwareValidator()

    test_cases = [
        ("RTC1Miner486", HardwareInfo("486DX2", 1992, 300)),
        ("RTC2MinerG4", HardwareInfo("PowerPC G4", 2002, 200)),
        ("RTC3MinerModern", HardwareInfo("Ryzen 9 7950X", 2022, 30)),
    ]

    for wallet, hardware in test_cases:
        result = validator.validate_miner(wallet, hardware)
        print(f"\n{wallet}:")
        print(f"  Hardware: {hardware.cpu_model} ({hardware.release_year})")
        print(f"  Age: {hardware.age_years} years")
        print(f"  Tier: {hardware.tier} ({hardware.multiplier}x)")
        print(f"  Eligible: {result['eligible']}")
        if result['eligible']:
            print(f"  Antiquity Score: {result['antiquity_score']:.2f}")
            print(f"  Effective Score: {result['effective_score']:.2f}")
        else:
            print(f"  Errors: {result['errors']}")
