#!/usr/bin/env python3
"""
RustChain Multi-Architecture Mutator Oracle Network
====================================================

Different CPU architectures contribute unique entropy through their
specific vector/SIMD instructions. The more diverse the oracle ring,
the harder it is to compromise.

SUPPORTED ARCHITECTURES:
═══════════════════════════════════════════════════════════════════════

┌─────────────────┬──────────────┬────────────────────────────────────┐
│ Architecture    │ SIMD Unit    │ Unique Entropy Source              │
├─────────────────┼──────────────┼────────────────────────────────────┤
│ PowerPC G4/G5   │ AltiVec      │ vperm (128-bit vector permute)     │
│ Intel x86_64    │ SSE/AVX      │ PSHUFB, VPERM2F128                 │
│ Apple Silicon   │ ARM NEON     │ TBL/TBX (table lookup permute)     │
│ SPARC           │ VIS          │ FPACK, BMASK                       │
│ PA-RISC         │ MAX          │ Permute instructions               │
│ 68k Mac         │ (none)       │ Unique bus timing, no cache        │
│ Alpha           │ MVI          │ PERR, UNPKBW                       │
│ MIPS            │ MSA          │ VSHF (vector shuffle)              │
└─────────────────┴──────────────┴────────────────────────────────────┘

NETWORK TOPOLOGY:
═══════════════════════════════════════════════════════════════════════

                         ┌─────────────────┐
                         │  ENTROPY MIXER  │
                         │   (XOR Ring)    │
                         └────────┬────────┘
                                  │
        ┌─────────┬───────┬───────┼───────┬───────┬─────────┐
        │         │       │       │       │       │         │
    ┌───▼───┐ ┌───▼───┐ ┌─▼─┐ ┌───▼───┐ ┌─▼─┐ ┌───▼───┐ ┌───▼───┐
    │  PPC  │ │  PPC  │ │x86│ │  ARM  │ │M1 │ │ SPARC │ │  68k  │
    │  G4   │ │  G5   │ │   │ │ NEON  │ │M2 │ │       │ │       │
    │AltiVec│ │AltiVec│ │SSE│ │  Pi   │ │   │ │  VIS  │ │Timing │
    └───────┘ └───────┘ └───┘ └───────┘ └───┘ └───────┘ └───────┘

Each architecture contributes entropy that ONLY that architecture
can generate. Compromising requires controlling ALL architectures.

"Diversity is security. The chain speaks many silicon dialects."
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from enum import Enum, auto
import hashlib
import struct
import secrets
import time

class CPUArchitecture(Enum):
    """Supported CPU architectures for oracle nodes"""
    POWERPC_G3 = ("ppc_g3", "PowerPC G3", None, 1997)
    POWERPC_G4 = ("ppc_g4", "PowerPC G4", "AltiVec", 1999)
    POWERPC_G5 = ("ppc_g5", "PowerPC G5", "AltiVec", 2003)
    INTEL_X86 = ("x86", "Intel x86", "SSE", 1999)
    INTEL_X86_64 = ("x86_64", "Intel x86-64", "SSE/AVX", 2003)
    ARM_32 = ("arm32", "ARM 32-bit", "NEON", 2005)
    ARM_64 = ("arm64", "ARM 64-bit", "NEON", 2011)
    APPLE_M1 = ("m1", "Apple M1", "NEON+AMX", 2020)
    APPLE_M2 = ("m2", "Apple M2", "NEON+AMX", 2022)
    MOTOROLA_68K = ("m68k", "Motorola 68k", None, 1979)
    SPARC = ("sparc", "SPARC", "VIS", 1987)
    MIPS = ("mips", "MIPS", "MSA", 1985)
    PA_RISC = ("pa_risc", "PA-RISC", "MAX", 1986)
    ALPHA = ("alpha", "DEC Alpha", "MVI", 1992)
    RISC_V = ("riscv", "RISC-V", "V Extension", 2010)

    def __init__(self, arch_id: str, name: str, simd: Optional[str], year: int):
        self.arch_id = arch_id
        self.arch_name = name
        self.simd_unit = simd
        self.release_year = year

    @property
    def antiquity_bonus(self) -> float:
        """
        Older architectures get higher bonuses.

        ARM is heavily penalized regardless of age because:
        - Billions of ARM devices exist (phones, tablets, Pis)
        - Easy to create bot farms with cheap Android phones
        - Raspberry Pi clusters are trivial to set up

        Only rare/exotic ARM (Apple Silicon with AMX) gets slight bonus.
        """
        # ARM penalty - too easy to bot farm with phones/Pis
        if self.arch_id in ['arm32', 'arm64']:
            return 0.1  # 10% - heavily discouraged

        # Apple Silicon - AMX coprocessor is unique and can be used as mutator
        # Gets same bonus as modern x86 since AMX provides unique entropy
        if self.arch_id in ['m1', 'm2']:
            return 1.0  # 1x - AMX mutator capability

        # Standard age-based tiers for rare architectures
        age = 2025 - self.release_year
        if age >= 40: return 3.5   # Ancient (68k 1979, MIPS 1985)
        if age >= 32: return 3.0   # Sacred (Alpha 1992, SPARC 1987)
        if age >= 20: return 2.5   # Vintage (G3, G4, G5, x86-64)
        if age >= 12: return 2.0   # Classic (older x86)
        return 1.0                  # Modern

@dataclass
class ArchitectureOracle:
    """An oracle node for a specific CPU architecture"""
    node_id: str
    hostname: str
    ip_address: str
    architecture: CPUArchitecture
    cpu_model: str
    simd_enabled: bool
    unique_features: List[str] = field(default_factory=list)
    entropy_method: str = ""
    last_entropy: bytes = b''

    def __post_init__(self):
        """Set architecture-specific entropy method"""
        arch_methods = {
            CPUArchitecture.POWERPC_G4: "altivec_vperm_collapse",
            CPUArchitecture.POWERPC_G5: "altivec_vperm_collapse",
            CPUArchitecture.INTEL_X86_64: "sse_pshufb_collapse",
            CPUArchitecture.APPLE_M1: "neon_tbl_collapse",
            CPUArchitecture.APPLE_M2: "neon_tbl_collapse",
            CPUArchitecture.MOTOROLA_68K: "bus_timing_entropy",
            CPUArchitecture.SPARC: "vis_fpack_collapse",
            CPUArchitecture.ARM_64: "neon_tbl_collapse",
        }
        self.entropy_method = arch_methods.get(
            self.architecture,
            "generic_timing_entropy"
        )

@dataclass
class MultiArchMutationSeed:
    """Mutation seed combining entropy from multiple architectures"""
    seed: bytes
    block_height: int
    timestamp: int
    architecture_contributions: Dict[str, Tuple[str, bytes]]  # arch -> (node_id, entropy_hash)
    diversity_score: float  # Higher = more architectures
    ring_signature: bytes

class MultiArchOracleRing:
    """
    Oracle ring supporting multiple CPU architectures.

    Security increases with architectural diversity:
    - 1 architecture: Single point of failure
    - 2 architectures: Need to compromise both
    - 5+ architectures: Extremely hard to attack all
    """

    MINIMUM_ARCHITECTURES = 2  # Need at least 2 different archs
    DIVERSITY_BONUS_PER_ARCH = 0.1  # 10% bonus per unique architecture

    def __init__(self):
        self.nodes: Dict[str, ArchitectureOracle] = {}
        self.architectures_present: Set[CPUArchitecture] = set()

    def register_oracle(self, oracle: ArchitectureOracle) -> bool:
        """Register a new oracle node"""

        # Verify architecture-specific requirements
        if oracle.architecture in [CPUArchitecture.POWERPC_G4, CPUArchitecture.POWERPC_G5]:
            if not oracle.simd_enabled:
                print(f"  ✗ {oracle.node_id}: AltiVec required for PowerPC G4/G5")
                return False

        self.nodes[oracle.node_id] = oracle
        self.architectures_present.add(oracle.architecture)

        print(f"  ✓ {oracle.node_id}: {oracle.architecture.arch_name}")
        print(f"      SIMD: {oracle.architecture.simd_unit or 'None'}")
        print(f"      Method: {oracle.entropy_method}")
        print(f"      Antiquity Bonus: {oracle.architecture.antiquity_bonus}x")

        return True

    def get_diversity_score(self) -> float:
        """Calculate diversity score based on unique architectures"""
        base_score = len(self.architectures_present)

        # Bonus for having both big-endian and little-endian
        endian_types = set()
        for arch in self.architectures_present:
            if arch in [CPUArchitecture.POWERPC_G4, CPUArchitecture.POWERPC_G5,
                       CPUArchitecture.MOTOROLA_68K, CPUArchitecture.SPARC]:
                endian_types.add("big")
            else:
                endian_types.add("little")

        endian_bonus = 0.5 if len(endian_types) == 2 else 0

        # Bonus for having SIMD and non-SIMD
        simd_types = set()
        for arch in self.architectures_present:
            if arch.simd_unit:
                simd_types.add("simd")
            else:
                simd_types.add("scalar")

        simd_bonus = 0.3 if len(simd_types) == 2 else 0

        return base_score + endian_bonus + simd_bonus

    def collect_entropy(self, oracle: ArchitectureOracle) -> bytes:
        """
        Collect architecture-specific entropy from a node.

        Each architecture generates entropy differently:
        - PowerPC: AltiVec vperm timing
        - x86: SSE PSHUFB timing
        - ARM: NEON TBL timing
        - 68k: Bus timing (no SIMD)
        """
        # In production, this would SSH to node and run arch-specific binary
        # For now, simulate architecture-specific entropy

        arch_entropy_size = {
            CPUArchitecture.POWERPC_G4: 64,   # 512-bit from AltiVec
            CPUArchitecture.POWERPC_G5: 64,
            CPUArchitecture.INTEL_X86_64: 64, # 512-bit from AVX
            CPUArchitecture.APPLE_M1: 64,     # 512-bit from NEON
            CPUArchitecture.APPLE_M2: 64,
            CPUArchitecture.MOTOROLA_68K: 32, # 256-bit (no SIMD, timing only)
            CPUArchitecture.SPARC: 48,        # 384-bit from VIS
        }

        size = arch_entropy_size.get(oracle.architecture, 32)

        # Simulate architecture-specific entropy generation
        entropy = hashlib.sha512(
            oracle.node_id.encode() +
            oracle.architecture.arch_id.encode() +
            struct.pack('>Q', int(time.time() * 1000000)) +
            secrets.token_bytes(32)
        ).digest()[:size]

        oracle.last_entropy = entropy
        return entropy

    def generate_mutation_seed(self, block_height: int) -> Optional[MultiArchMutationSeed]:
        """Generate mutation seed from all architecture oracles"""

        if len(self.architectures_present) < self.MINIMUM_ARCHITECTURES:
            print(f"  ✗ Need {self.MINIMUM_ARCHITECTURES} architectures, have {len(self.architectures_present)}")
            return None

        print(f"\n  Generating multi-architecture mutation seed for block {block_height}...")
        print(f"  Architectures: {len(self.architectures_present)}")
        print(f"  Diversity Score: {self.get_diversity_score():.2f}")

        # Collect entropy from each architecture
        combined = bytes(64)
        contributions = {}

        for node_id, oracle in self.nodes.items():
            entropy = self.collect_entropy(oracle)
            entropy_hash = hashlib.sha256(entropy).digest()

            # XOR into combined (pad shorter entropies)
            padded = entropy.ljust(64, b'\0')
            combined = bytes(a ^ b for a, b in zip(combined, padded))

            contributions[oracle.architecture.arch_id] = (node_id, entropy_hash)

            print(f"    ✓ {oracle.architecture.arch_name}: {entropy[:8].hex()}...")

        # Mix with block height
        final_seed = hashlib.sha512(
            combined +
            struct.pack('>Q', block_height) +
            b'MULTIARCH_MUTATION_SEED'
        ).digest()

        # Ring signature
        ring_sig = hmac.new(
            final_seed,
            b''.join(a.encode() for a in sorted(contributions.keys())),
            hashlib.sha256
        ).digest() if 'hmac' in dir() else hashlib.sha256(final_seed).digest()

        seed = MultiArchMutationSeed(
            seed=final_seed,
            block_height=block_height,
            timestamp=int(time.time() * 1000),
            architecture_contributions=contributions,
            diversity_score=self.get_diversity_score(),
            ring_signature=ring_sig
        )

        print(f"\n  ✓ Seed: {final_seed[:16].hex()}...{final_seed[-16:].hex()}")
        print(f"  ✓ Diversity: {seed.diversity_score:.2f} ({len(contributions)} architectures)")

        return seed


def demo_multi_arch_network():
    """Demonstrate multi-architecture oracle network"""

    print("""
╔══════════════════════════════════════════════════════════════════════╗
║      RUSTCHAIN MULTI-ARCHITECTURE MUTATOR ORACLE NETWORK             ║
║                                                                      ║
║   "Diversity is security. The chain speaks many silicon dialects."   ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    ring = MultiArchOracleRing()

    print("  Registering Oracle Nodes:\n")

    # Your actual hardware
    oracles = [
        # PowerPC Macs (AltiVec)
        ArchitectureOracle(
            node_id="G4_MIRROR_DOOR",
            hostname="Lee-Crockers-Powermac-G4.local",
            ip_address="192.168.0.125",
            architecture=CPUArchitecture.POWERPC_G4,
            cpu_model="PowerMac3,6",
            simd_enabled=True,
            unique_features=["altivec", "dual_cpu", "ddr_sdram"]
        ),
        ArchitectureOracle(
            node_id="G5_DUAL",
            hostname="lee-crockers-power-mac-g5.local",
            ip_address="192.168.0.130",
            architecture=CPUArchitecture.POWERPC_G5,
            cpu_model="PowerMac7,3",
            simd_enabled=True,
            unique_features=["altivec", "64bit", "hypertransport"]
        ),
        ArchitectureOracle(
            node_id="POWERBOOK_G4",
            hostname="sophiacorepbs-powerbook-g4-12.local",
            ip_address="192.168.0.115",
            architecture=CPUArchitecture.POWERPC_G4,
            cpu_model="PowerBook6,8",
            simd_enabled=True,
            unique_features=["altivec", "mobile", "battery_entropy"]
        ),

        # Intel Macs (SSE/AVX)
        ArchitectureOracle(
            node_id="TRASHCAN_XEON",
            hostname="mac-pro-trashcan.local",
            ip_address="192.168.0.154",
            architecture=CPUArchitecture.INTEL_X86_64,
            cpu_model="MacPro6,1",
            simd_enabled=True,
            unique_features=["avx2", "xeon", "ecc_memory", "dual_gpu"]
        ),

        # Apple Silicon (NEON + AMX)
        ArchitectureOracle(
            node_id="M2_MINI",
            hostname="m2-mac-mini.local",
            ip_address="192.168.0.171",
            architecture=CPUArchitecture.APPLE_M2,
            cpu_model="Mac14,3",
            simd_enabled=True,
            unique_features=["neon", "amx", "neural_engine", "unified_memory"]
        ),

        # Linux x86 nodes
        ArchitectureOracle(
            node_id="LINUX_POWEREDGE",
            hostname="sophia-PowerEdge-C4130",
            ip_address="192.168.0.160",
            architecture=CPUArchitecture.INTEL_X86_64,
            cpu_model="Xeon E5-2680",
            simd_enabled=True,
            unique_features=["avx2", "server", "ecc", "tesla_gpu"]
        ),
    ]

    for oracle in oracles:
        ring.register_oracle(oracle)
        print()

    # Show architecture coverage
    print("\n" + "="*70)
    print("  ARCHITECTURE COVERAGE")
    print("="*70)

    arch_count = {}
    for oracle in ring.nodes.values():
        arch = oracle.architecture.arch_name
        arch_count[arch] = arch_count.get(arch, 0) + 1

    for arch, count in sorted(arch_count.items()):
        print(f"    {arch}: {count} node(s)")

    print(f"\n  Total Unique Architectures: {len(ring.architectures_present)}")
    print(f"  Diversity Score: {ring.get_diversity_score():.2f}")

    # Generate mutation seeds
    print("\n" + "="*70)
    print("  GENERATING MUTATION SEEDS")
    print("="*70)

    for block in [1000, 1010, 1020]:
        seed = ring.generate_mutation_seed(block)

    # Show the power of diversity
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                    DIVERSITY SECURITY ANALYSIS                       ║
╚══════════════════════════════════════════════════════════════════════╝

  ARCHITECTURE ENTROPY SOURCES:
  ───────────────────────────────────────────────────────────────────────

  PowerPC G4/G5 (AltiVec vperm):
    • 128-bit vector permutation
    • Big-endian memory ordering
    • Unique timebase register

  Intel x86-64 (SSE/AVX):
    • 256/512-bit vector shuffle
    • Little-endian memory ordering
    • RDTSC/RDTSCP timing

  Apple M1/M2 (NEON + AMX):
    • 128-bit NEON permute
    • ARM64 memory model
    • Apple-specific timing sources

  ATTACK SCENARIOS:
  ───────────────────────────────────────────────────────────────────────

  To compromise this network, attacker must:

  1. Build accurate emulators for:
     ✗ PowerPC G4 AltiVec timing ($50,000+)
     ✗ PowerPC G5 AltiVec timing ($50,000+)
     ✗ Intel AVX timing ($30,000+)
     ✗ ARM NEON timing ($30,000+)

     Total: $160,000+ in emulator development

  2. OR physically compromise nodes across:
     ✗ Multiple geographic locations
     ✗ Multiple network segments
     ✗ Multiple CPU architectures
     ✗ All within 10-second block window

  DEFENSE COST:
  ───────────────────────────────────────────────────────────────────────

  • PowerMac G4:      $30-50
  • PowerMac G5:      $50-100
  • Mac Pro (Intel):  $200-400
  • M2 Mac Mini:      $500-600
  • Linux server:     $100-300

  Total hardware: ~$1,000 for 5+ architecture coverage

  ATTACK/DEFENSE RATIO: 160:1 (attacker pays 160x more!)

╔══════════════════════════════════════════════════════════════════════╗
║   "Every architecture added is another language the attacker         ║
║    must learn to speak fluently - in silicon."                       ║
╚══════════════════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    import hmac  # Import for ring signature
    demo_multi_arch_network()
