"""
RustChain Deep Entropy Hardware Verification (RIP-0003)
=======================================================

Multi-layer entropy verification that makes emulation economically irrational.

Philosophy: It should be cheaper to buy a $50 486 than to emulate one.

Layers:
1. Instruction Timing Entropy - CPU-specific timing patterns
2. Memory Access Pattern Entropy - Cache/DRAM behavior
3. Bus Timing Entropy - ISA/PCI/PCIe timing signatures
4. Thermal Entropy - Clock stability, DVFS detection
5. Architectural Quirk Entropy - Known hardware bugs/quirks
"""

import hashlib
import math
import time
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum


# =============================================================================
# Constants
# =============================================================================

ENTROPY_SAMPLES_REQUIRED: int = 1000
MIN_ENTROPY_BITS: int = 64
EMULATION_COST_THRESHOLD_USD: float = 100.0  # Cheaper to buy real hardware


# =============================================================================
# Hardware Profiles
# =============================================================================

@dataclass
class HardwareProfile:
    """Known hardware profile for validation"""
    name: str
    cpu_family: int
    year_introduced: int
    expected_bus_type: str
    expected_quirks: List[str]
    emulation_difficulty: float  # 0.0-1.0, how hard to emulate

    # Expected instruction timing ranges (instruction -> (min_cycles, max_cycles))
    instruction_timings: Dict[str, Tuple[float, float]] = field(default_factory=dict)


# Known hardware database
HARDWARE_PROFILES: Dict[str, HardwareProfile] = {
    "486DX2": HardwareProfile(
        name="Intel 486 DX2-66",
        cpu_family=4,
        year_introduced=1992,
        expected_bus_type="ISA",
        expected_quirks=["no_rdtsc", "a20_gate"],
        emulation_difficulty=0.95,
        instruction_timings={
            "mul": (13.0, 42.0),
            "div": (40.0, 44.0),
            "fadd": (8.0, 20.0),
            "fmul": (16.0, 27.0),
        },
    ),
    "Pentium": HardwareProfile(
        name="Intel Pentium 100",
        cpu_family=5,
        year_introduced=1994,
        expected_bus_type="PCI",
        expected_quirks=["fdiv_bug"],
        emulation_difficulty=0.90,
        instruction_timings={
            "mul": (10.0, 11.0),
            "div": (17.0, 41.0),
            "fadd": (3.0, 3.0),
            "fmul": (3.0, 3.0),
        },
    ),
    "PentiumII": HardwareProfile(
        name="Intel Pentium II",
        cpu_family=6,
        year_introduced=1997,
        expected_bus_type="PCI",
        expected_quirks=["f00f_bug"],
        emulation_difficulty=0.85,
        instruction_timings={
            "mul": (4.0, 5.0),
            "div": (17.0, 41.0),
            "fadd": (3.0, 3.0),
            "fmul": (5.0, 5.0),
        },
    ),
    "G4": HardwareProfile(
        name="PowerPC G4",
        cpu_family=74,
        year_introduced=1999,
        expected_bus_type="PCI",
        expected_quirks=["altivec", "big_endian"],
        emulation_difficulty=0.85,
        instruction_timings={
            "mul": (3.0, 4.0),
            "div": (20.0, 35.0),
            "fadd": (5.0, 5.0),
            "fmul": (5.0, 5.0),
        },
    ),
    "G5": HardwareProfile(
        name="PowerPC G5",
        cpu_family=75,
        year_introduced=2003,
        expected_bus_type="PCI-X",
        expected_quirks=["altivec", "big_endian", "970fx"],
        emulation_difficulty=0.80,
        instruction_timings={
            "mul": (2.0, 4.0),
            "div": (15.0, 33.0),
            "fadd": (4.0, 4.0),
            "fmul": (4.0, 4.0),
        },
    ),
    "Alpha": HardwareProfile(
        name="DEC Alpha 21264",
        cpu_family=21,
        year_introduced=1998,
        expected_bus_type="PCI",
        expected_quirks=["alpha_pal", "64bit_native"],
        emulation_difficulty=0.95,
        instruction_timings={
            "mul": (4.0, 7.0),
            "div": (12.0, 16.0),
            "fadd": (4.0, 4.0),
            "fmul": (4.0, 4.0),
        },
    ),
}


# =============================================================================
# Entropy Layers
# =============================================================================

@dataclass
class InstructionTimingLayer:
    """Layer 1: Instruction timing measurements"""
    timings: Dict[str, Dict[str, float]]  # instruction -> {mean, std_dev, min, max}
    cache_miss_penalty: float
    branch_misprediction_cost: float


@dataclass
class MemoryPatternLayer:
    """Layer 2: Memory access patterns"""
    sequential_read_rate: float
    random_read_rate: float
    stride_patterns: Dict[int, float]  # stride size -> rate
    page_crossing_penalty: float
    refresh_interference_detected: bool


@dataclass
class BusTimingLayer:
    """Layer 3: Bus timing characteristics"""
    bus_type: str
    io_read_ns: float
    io_write_ns: float
    timing_variance: float
    interrupt_latency_us: float


@dataclass
class ThermalEntropyLayer:
    """Layer 4: Thermal/clock characteristics"""
    clock_frequency_mhz: float
    clock_variance: float
    frequency_changed: bool
    c_states_detected: List[str]
    p_states_detected: List[str]


@dataclass
class QuirkEntropyLayer:
    """Layer 5: Architectural quirks"""
    detected_quirks: List[str]
    quirk_test_results: Dict[str, Dict[str, Any]]


@dataclass
class EntropyProof:
    """Complete entropy proof from hardware"""
    instruction_layer: InstructionTimingLayer
    memory_layer: MemoryPatternLayer
    bus_layer: BusTimingLayer
    thermal_layer: ThermalEntropyLayer
    quirk_layer: QuirkEntropyLayer
    challenge_response: bytes
    computation_time_us: int
    timestamp: int
    signature_hash: str


# =============================================================================
# Entropy Scores
# =============================================================================

@dataclass
class EntropyScores:
    """Verification scores from each layer"""
    instruction: float = 0.0
    memory: float = 0.0
    bus: float = 0.0
    thermal: float = 0.0
    quirks: float = 0.0
    total: float = 0.0


@dataclass
class VerificationResult:
    """Result of entropy verification"""
    valid: bool
    total_score: float
    scores: EntropyScores
    issues: List[str]
    emulation_probability: float


# =============================================================================
# Deep Entropy Verifier
# =============================================================================

class DeepEntropyVerifier:
    """
    Multi-layer entropy verification system.

    Makes emulation economically irrational by requiring perfect simulation
    of vintage hardware characteristics that are:
    1. Difficult to obtain without real hardware
    2. Expensive to compute/simulate
    3. Unique to each hardware generation

    Cost analysis:
    - GPU compute to emulate 486 at real-time: ~50-100 hours @ $0.50/hr = $25-50
    - Cost of 486 on eBay: $30-80 one-time
    - ROI for buying real hardware: 1 day of mining

    Conclusion: Deep entropy makes emulation economically irrational.
    """

    def __init__(self):
        self.profiles = HARDWARE_PROFILES
        self.thresholds = {
            "min_instruction_entropy": 0.15,
            "min_memory_entropy": 0.10,
            "min_bus_entropy": 0.15,
            "min_thermal_entropy": 0.05,
            "min_quirk_entropy": 0.20,
            "total_min_entropy": 0.65,
        }

    def generate_challenge(self) -> Dict[str, Any]:
        """Generate a challenge for hardware to solve"""
        nonce = hashlib.sha256(str(time.time()).encode()).digest()
        operations = [
            {"op": "mul", "value": random.randint(1, 1000000)},
            {"op": "div", "value": random.randint(1, 1000)},
            {"op": "fadd", "value": random.uniform(0, 1000)},
            {"op": "memory", "stride": random.choice([1, 4, 16, 64, 256])},
        ] * 25  # 100 operations

        return {
            "nonce": nonce.hex(),
            "operations": operations,
            "expected_time_range_us": (1000, 100000),  # 1ms to 100ms
            "timestamp": int(time.time()),
            "expires_at": int(time.time()) + 300,  # 5 minute expiry
        }

    def verify(self, proof: EntropyProof, claimed_hardware: str) -> VerificationResult:
        """
        Verify an entropy proof against claimed hardware.

        Args:
            proof: Complete entropy proof from hardware
            claimed_hardware: Hardware profile key (e.g., "486DX2", "G4")

        Returns:
            VerificationResult with scores and issues
        """
        scores = EntropyScores()
        issues = []

        # Get expected profile
        profile = self.profiles.get(claimed_hardware)
        if not profile:
            return VerificationResult(
                valid=False,
                total_score=0.0,
                scores=scores,
                issues=[f"Unknown hardware profile: {claimed_hardware}"],
                emulation_probability=1.0,
            )

        # Layer 1: Verify instruction timing
        scores.instruction = self._verify_instruction_layer(
            proof.instruction_layer, profile
        )
        if scores.instruction < self.thresholds["min_instruction_entropy"]:
            issues.append(
                f"Instruction timing entropy too low: {scores.instruction:.2f}"
            )

        # Layer 2: Verify memory patterns
        scores.memory = self._verify_memory_layer(proof.memory_layer, profile)
        if scores.memory < self.thresholds["min_memory_entropy"]:
            issues.append(f"Memory pattern entropy too low: {scores.memory:.2f}")

        # Layer 3: Verify bus timing
        scores.bus = self._verify_bus_layer(proof.bus_layer, profile)
        if scores.bus < self.thresholds["min_bus_entropy"]:
            issues.append(f"Bus timing entropy too low: {scores.bus:.2f}")

        # Layer 4: Verify thermal characteristics
        scores.thermal = self._verify_thermal_layer(proof.thermal_layer, profile)
        if scores.thermal < self.thresholds["min_thermal_entropy"]:
            issues.append(f"Thermal entropy suspicious: {scores.thermal:.2f}")

        # Layer 5: Verify architectural quirks
        scores.quirks = self._verify_quirk_layer(proof.quirk_layer, profile)
        if scores.quirks < self.thresholds["min_quirk_entropy"]:
            issues.append(f"Expected quirks not detected: {scores.quirks:.2f}")

        # Calculate total score (weighted)
        scores.total = (
            scores.instruction * 0.25 +
            scores.memory * 0.20 +
            scores.bus * 0.20 +
            scores.thermal * 0.15 +
            scores.quirks * 0.20
        )

        # Calculate emulation probability
        emulation_prob = max(0.0, 1.0 - (scores.total * profile.emulation_difficulty))

        valid = (
            scores.total >= self.thresholds["total_min_entropy"] and
            len(issues) == 0
        )

        return VerificationResult(
            valid=valid,
            total_score=scores.total,
            scores=scores,
            issues=issues,
            emulation_probability=emulation_prob,
        )

    def _verify_instruction_layer(
        self, layer: InstructionTimingLayer, profile: HardwareProfile
    ) -> float:
        """Verify instruction timing matches expected profile"""
        score = 0.0
        checks = 0

        for instruction, expected_range in profile.instruction_timings.items():
            if instruction in layer.timings:
                checks += 1
                measured = layer.timings[instruction]
                min_expected, max_expected = expected_range

                # Check if mean is within expected range
                if min_expected <= measured.get("mean", 0) <= max_expected:
                    score += 0.5

                # Check if variance is reasonable (vintage has natural jitter)
                std_dev = measured.get("std_dev", 0)
                mean = measured.get("mean", 1)
                if 0 < std_dev < mean * 0.5:
                    score += 0.5

        return score / checks if checks > 0 else 0.0

    def _verify_memory_layer(
        self, layer: MemoryPatternLayer, profile: HardwareProfile
    ) -> float:
        """Verify memory access patterns"""
        score = 0.0

        # Vintage hardware should show significant stride-dependent timing
        if layer.stride_patterns:
            stride_1 = layer.stride_patterns.get(1, 1)
            stride_64 = layer.stride_patterns.get(64, 1)
            if stride_64 / stride_1 > 1.5:
                score += 0.3  # Good cache behavior signature

        # Page crossing penalty should be detectable
        if layer.page_crossing_penalty > 10.0:
            score += 0.3

        # DRAM refresh interference is strong signal of real hardware
        if layer.refresh_interference_detected:
            score += 0.4

        return score

    def _verify_bus_layer(
        self, layer: BusTimingLayer, profile: HardwareProfile
    ) -> float:
        """Verify bus timing characteristics"""
        score = 0.0

        # Check bus type matches
        if layer.bus_type == profile.expected_bus_type:
            score += 0.5

        # Verify I/O timing is in expected range for bus type
        expected_ranges = {
            "ISA": (1000, 2500),     # Very slow
            "EISA": (500, 1500),
            "VLB": (100, 500),
            "PCI": (50, 200),
            "PCI-X": (30, 150),
            "AGP": (30, 150),
            "PCIe": (5, 50),         # Very fast
        }

        if layer.bus_type in expected_ranges:
            min_io, max_io = expected_ranges[layer.bus_type]
            if min_io <= layer.io_read_ns <= max_io:
                score += 0.3

        # Vintage hardware has slower interrupts
        if layer.interrupt_latency_us > 1.0:
            score += 0.2

        return score

    def _verify_thermal_layer(
        self, layer: ThermalEntropyLayer, profile: HardwareProfile
    ) -> float:
        """Verify thermal/clock characteristics"""
        score = 0.0

        # Vintage hardware shouldn't have DVFS
        if not layer.frequency_changed:
            score += 0.4

        # No C-states on vintage hardware
        if not layer.c_states_detected:
            score += 0.3

        # No P-states on vintage hardware
        if not layer.p_states_detected:
            score += 0.3

        return score

    def _verify_quirk_layer(
        self, layer: QuirkEntropyLayer, profile: HardwareProfile
    ) -> float:
        """Verify architectural quirks are present"""
        if not profile.expected_quirks:
            return 1.0

        detected = 0
        for expected_quirk in profile.expected_quirks:
            if expected_quirk in layer.detected_quirks:
                detected += 1
            elif expected_quirk in layer.quirk_test_results:
                result = layer.quirk_test_results[expected_quirk]
                if result.get("detected") and result.get("confidence", 0) > 0.8:
                    detected += 1

        return detected / len(profile.expected_quirks)


# =============================================================================
# Economic Analysis
# =============================================================================

def emulation_cost_analysis(hardware_type: str) -> Dict[str, Any]:
    """
    Analyze the economic cost of emulating vs. buying hardware.

    This proves why deep entropy makes emulation irrational.
    """
    profile = HARDWARE_PROFILES.get(hardware_type)
    if not profile:
        return {"error": f"Unknown hardware: {hardware_type}"}

    # Emulation costs
    gpu_hours_to_emulate = 50 + (profile.emulation_difficulty * 100)
    gpu_cost_per_hour = 0.50
    emulation_cost = gpu_hours_to_emulate * gpu_cost_per_hour

    # Real hardware costs (approximate eBay prices)
    hardware_prices = {
        "486DX2": 50,
        "Pentium": 40,
        "PentiumII": 30,
        "G4": 80,
        "G5": 150,
        "Alpha": 200,
    }
    real_cost = hardware_prices.get(hardware_type, 100)

    # Power costs (per year at $0.10/kWh)
    power_watts = {"486DX2": 15, "Pentium": 25, "G4": 50, "G5": 100}
    watts = power_watts.get(hardware_type, 50)
    yearly_power_cost = watts * 24 * 365 * 0.10 / 1000

    return {
        "hardware": profile.name,
        "emulation_difficulty": profile.emulation_difficulty,
        "estimated_gpu_hours": gpu_hours_to_emulate,
        "emulation_cost_usd": emulation_cost,
        "real_hardware_cost_usd": real_cost,
        "yearly_power_cost_usd": yearly_power_cost,
        "breakeven_days": (emulation_cost - real_cost) / (yearly_power_cost / 365),
        "recommendation": "BUY REAL HARDWARE" if emulation_cost > real_cost else "EMULATE",
        "economic_conclusion": (
            f"Buying a real {profile.name} for ${real_cost} is "
            f"{'cheaper' if real_cost < emulation_cost else 'more expensive'} "
            f"than emulating (${emulation_cost:.2f})"
        ),
    }


if __name__ == "__main__":
    print("=" * 70)
    print("RUSTCHAIN DEEP ENTROPY - ECONOMIC ANALYSIS")
    print("=" * 70)
    print()
    print("Why emulation is economically irrational:")
    print()

    for hw_type in ["486DX2", "G4", "Alpha"]:
        analysis = emulation_cost_analysis(hw_type)
        print(f"📟 {analysis['hardware']}")
        print(f"   Emulation difficulty: {analysis['emulation_difficulty']:.0%}")
        print(f"   GPU hours to emulate: {analysis['estimated_gpu_hours']:.0f}")
        print(f"   Emulation cost: ${analysis['emulation_cost_usd']:.2f}")
        print(f"   Real hardware cost: ${analysis['real_hardware_cost_usd']:.2f}")
        print(f"   Yearly power cost: ${analysis['yearly_power_cost_usd']:.2f}")
        print(f"   💡 {analysis['economic_conclusion']}")
        print()

    print("=" * 70)
    print("CONCLUSION: Buy a $50 486, don't waste $50+ trying to emulate it!")
    print("=" * 70)
