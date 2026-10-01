#!/usr/bin/env python3
"""
RustChain Mutating Challenge System -- EXPERIMENTAL DESIGN SKETCH
=================================================================

STATUS: experimental, NOT wired in. Nothing under ``node/`` or ``miners/``
imports this module, and it takes no part in consensus, attestation or reward
calculation. ``tests/test_mutating_challenge_unwired.py`` asserts that, so that
wiring it in has to be a deliberate, reviewed change. Do not treat this file as
a security control: as written it is a model of the *shape* of a protocol, not
an implementation of one.

The idea being sketched:
- Challenge parameters are re-derived each round from the block hash and the
  target, so a responder cannot reuse a fixed, pre-recorded answer.
- Validators challenge each other in round-robin (block N: A challenges B,
  B challenges C, C challenges A; block N+1: roles rotate).
- A quorum of validators would have to agree on a target's hardware validity.

What this code does NOT do (known gaps):
- Nothing is authenticated. The ``signature`` fields on ``MutatingChallenge``
  and ``MutatingResponse`` are never produced or verified.
- The proof hash is not bound to hardware. ``compute_proof`` is only ever
  called with empty entropy, and the validator recomputes it from fields the
  responder supplied, so it is a self-consistency check that anyone can
  satisfy. It proves nothing about the responder's machine.
- Timing, jitter and thermal values are self-reported numbers compared against
  ranges; they are not measured by the validator.
- Challenges do not expire and are not single-use; a challenge stays answerable
  until ``end_round`` clears it.
- A hardware profile that lacks the requested serial type is not rejected (only
  a wholly missing profile is).
- No quorum is computed. ``CONSENSUS_THRESHOLD`` is declared but unused, and
  the "slashing" list is a local counter with no effect on anything.
- Mutation seeds derive from a block hash, which is public once the block
  exists and can be influenced by whoever produces the block. That makes
  pre-computation inconvenient, not impossible.

Required before this may be used for consensus or rewards:
1. Signed challenges, verified against the challenger's registered key.
2. ``responder == challenge.target`` (enforced below) AND a signature over the
   full response, verified against the target's registered key.
3. Fail closed on a missing hardware profile (enforced below) and on a missing
   serial for the requested serial type.
4. Single-use challenges with an expiry.
5. A proof rooted in a registered hardware key, not in client-supplied entropy.
"""

import hashlib
import secrets
import struct
import time
import json
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from enum import Enum, auto

class MutationType(Enum):
    """Types of challenge mutations"""
    CACHE_STRIDE = auto()      # Change cache access stride
    MEMORY_PATTERN = auto()    # Change memory access pattern
    TIMING_WINDOW = auto()     # Adjust expected timing window
    PIPELINE_DEPTH = auto()    # Change instruction pipeline test depth
    THERMAL_RANGE = auto()     # Adjust thermal sensor expectations
    JITTER_THRESHOLD = auto()  # Change jitter detection threshold
    HASH_ROUNDS = auto()       # Change cryptographic hash iterations
    SERIAL_CHECK = auto()      # Which serial to validate (OF, GPU, HD)

@dataclass
class MutationParams:
    """Parameters that mutate each challenge round"""
    cache_stride: int = 64           # Bytes between cache accesses
    cache_iterations: int = 256      # Number of cache probes
    memory_pattern_seed: int = 0     # Seed for random memory access
    memory_size_kb: int = 1024       # Size of memory test region
    timing_min_ticks: int = 100      # Minimum expected response ticks
    timing_max_ticks: int = 500000   # Maximum expected response ticks
    pipeline_test_depth: int = 1000  # Instruction pipeline iterations
    thermal_min_c: int = 15          # Minimum expected temperature
    thermal_max_c: int = 85          # Maximum expected temperature
    jitter_min_percent: int = 5      # Minimum jitter (emulator detection)
    jitter_max_percent: int = 500    # Maximum jitter
    hash_rounds: int = 1000          # SHA256 iterations for proof
    serial_type: str = "openfirmware" # Which serial to check

    def to_bytes(self) -> bytes:
        """Serialize for hashing"""
        return struct.pack(
            '>IIIIIIIIII',
            self.cache_stride,
            self.cache_iterations,
            self.memory_pattern_seed,
            self.memory_size_kb,
            self.timing_min_ticks,
            self.timing_max_ticks,
            self.pipeline_test_depth,
            self.jitter_min_percent,
            self.jitter_max_percent,
            self.hash_rounds
        ) + self.serial_type.encode()

    def hash(self) -> str:
        """Get deterministic hash of parameters"""
        return hashlib.sha256(self.to_bytes()).hexdigest()[:16]

class ChallengeMutator:
    """
    Mutates challenge parameters based on blockchain state.

    Experimental sketch; see the module docstring for status and known gaps.

    Mutation is deterministic given its inputs:
    - Seed derived from the genesis seed, block hash, target and epoch
    - Parameters change in ways intended to stress different hardware aspects
    - The parameters are not known before the block hash is, but the block
      producer can influence that hash, so treat this as raising the cost of
      pre-computation rather than preventing it
    """

    # Mutation ranges (min, max) for each parameter
    MUTATION_RANGES = {
        'cache_stride': (32, 512),        # 32-512 byte strides
        'cache_iterations': (128, 1024),  # Number of probes
        'memory_size_kb': (256, 8192),    # 256KB to 8MB test region
        'pipeline_test_depth': (500, 5000),
        'hash_rounds': (500, 5000),
        'jitter_min_percent': (3, 10),    # 0.3% to 1.0% minimum
    }

    SERIAL_TYPES = ['openfirmware', 'gpu', 'storage', 'platform']

    def __init__(self, genesis_seed: bytes = None):
        """Initialize with genesis seed"""
        self.genesis_seed = genesis_seed or secrets.token_bytes(32)
        self.current_epoch = 0
        self.mutation_history: List[MutationParams] = []

    def derive_seed(self, block_hash: bytes, validator_pubkey: str) -> bytes:
        """
        Derive mutation seed from block hash and validator.

        Properties:
        - Different validators get different mutations
        - Mutations are not known until the block hash is (the block producer
          can influence it; this is not a source of unbiasable randomness)
        - Mutations are deterministic (re-derivable by any node holding the
          same genesis seed)
        """
        return hashlib.sha256(
            self.genesis_seed +
            block_hash +
            validator_pubkey.encode() +
            struct.pack('>Q', self.current_epoch)
        ).digest()

    def mutate(self, block_hash: bytes, validator_pubkey: str) -> MutationParams:
        """
        Generate mutated parameters for this block/validator pair.

        The mutation is deterministic - any node can verify it.
        """
        seed = self.derive_seed(block_hash, validator_pubkey)

        # Use seed bytes to deterministically select parameters
        params = MutationParams()

        # Each parameter gets different seed bytes
        params.cache_stride = self._select_range(
            seed[0:4], self.MUTATION_RANGES['cache_stride']
        )
        params.cache_iterations = self._select_range(
            seed[4:8], self.MUTATION_RANGES['cache_iterations']
        )
        params.memory_pattern_seed = int.from_bytes(seed[8:12], 'big')
        params.memory_size_kb = self._select_range(
            seed[12:16], self.MUTATION_RANGES['memory_size_kb']
        )
        params.pipeline_test_depth = self._select_range(
            seed[16:20], self.MUTATION_RANGES['pipeline_test_depth']
        )
        params.hash_rounds = self._select_range(
            seed[20:24], self.MUTATION_RANGES['hash_rounds']
        )
        params.jitter_min_percent = self._select_range(
            seed[24:28], self.MUTATION_RANGES['jitter_min_percent']
        )

        # Select which serial to check this round
        serial_idx = seed[28] % len(self.SERIAL_TYPES)
        params.serial_type = self.SERIAL_TYPES[serial_idx]

        # Timing windows scale with test complexity
        complexity = (params.cache_iterations * params.pipeline_test_depth) // 1000
        params.timing_min_ticks = 100 + complexity
        params.timing_max_ticks = 500000 + complexity * 10

        self.mutation_history.append(params)
        return params

    def _select_range(self, seed_bytes: bytes, range_tuple: Tuple[int, int]) -> int:
        """Select value in range using seed bytes"""
        min_val, max_val = range_tuple
        seed_int = int.from_bytes(seed_bytes, 'big')
        return min_val + (seed_int % (max_val - min_val + 1))

    def advance_epoch(self):
        """Move to next epoch (e.g., every 100 blocks)"""
        self.current_epoch += 1


@dataclass
class RoundRobinState:
    """Tracks round-robin challenge state"""
    validators: List[str]                    # List of validator pubkeys
    current_round: int = 0                   # Current round number
    challenges_this_round: Dict[str, str] = field(default_factory=dict)  # challenger -> target
    results_this_round: Dict[str, bool] = field(default_factory=dict)    # target -> passed

    def get_challenge_pairs(self) -> List[Tuple[str, str]]:
        """
        Get challenger->target pairs for this round.

        Round-robin ensures everyone challenges everyone over time.
        Each validator challenges the next one in the rotated list.
        """
        n = len(self.validators)
        if n < 2:
            return []

        # Rotate list by round number
        rotated = self.validators[self.current_round % n:] + \
                  self.validators[:self.current_round % n]

        # Each validator challenges the next one
        pairs = []
        for i in range(n):
            challenger = rotated[i]
            target = rotated[(i + 1) % n]
            pairs.append((challenger, target))

        return pairs

    def advance_round(self):
        """Move to next round"""
        self.current_round += 1
        self.challenges_this_round.clear()
        self.results_this_round.clear()


@dataclass
class MutatingChallenge:
    """
    A challenge with mutated parameters.

    Experimental sketch. ``signature`` is a placeholder: nothing signs a
    challenge and nothing verifies one, so a challenge is not authenticated
    as coming from ``challenger``. Challenges also carry no expiry.
    """
    challenge_id: str
    block_height: int
    block_hash: bytes
    challenger: str
    target: str
    mutation_params: MutationParams
    timestamp_ms: int
    signature: bytes = b''

    def to_dict(self) -> dict:
        return {
            'challenge_id': self.challenge_id,
            'block_height': self.block_height,
            'block_hash': self.block_hash.hex(),
            'challenger': self.challenger,
            'target': self.target,
            'mutation_hash': self.mutation_params.hash(),
            'cache_stride': self.mutation_params.cache_stride,
            'cache_iterations': self.mutation_params.cache_iterations,
            'memory_pattern_seed': self.mutation_params.memory_pattern_seed,
            'memory_size_kb': self.mutation_params.memory_size_kb,
            'pipeline_depth': self.mutation_params.pipeline_test_depth,
            'hash_rounds': self.mutation_params.hash_rounds,
            'serial_type': self.mutation_params.serial_type,
            'timestamp_ms': self.timestamp_ms
        }


@dataclass
class MutatingResponse:
    """
    Response to a mutating challenge.

    Experimental sketch. ``signature`` is a placeholder that is never
    verified, so ``responder`` is an unauthenticated claim, and every
    measurement field is self-reported.
    """
    challenge_id: str
    responder: str

    # Hardware measurements using mutated parameters
    cache_timing_ticks: int
    memory_timing_ticks: int
    pipeline_timing_ticks: int
    jitter_variance: int
    thermal_celsius: int
    serial_value: str  # Value of requested serial type

    # Proof of work with mutated hash rounds
    proof_hash: bytes

    timestamp_ms: int
    signature: bytes = b''

    def compute_proof(self, challenge: MutatingChallenge, hardware_entropy: bytes) -> bytes:
        """
        Compute proof hash using mutated parameters.

        NOTE: this is not a hardware proof. The intent was to mix in entropy
        from the responding machine, but every caller (including
        ``validate_response``) passes ``b''``, and a validator has no way to
        know a client-supplied entropy value anyway. The result is a
        deterministic function of the challenge ID and the response's own
        fields, so it only shows the response is internally consistent. A real
        design needs a proof rooted in a registered hardware key.
        """
        data = (
            challenge.challenge_id.encode() +
            hardware_entropy +
            struct.pack('>Q', self.cache_timing_ticks) +
            struct.pack('>Q', self.memory_timing_ticks) +
            struct.pack('>Q', self.pipeline_timing_ticks) +
            struct.pack('>I', self.jitter_variance) +
            struct.pack('>i', self.thermal_celsius) +
            self.serial_value.encode()
        )

        # Iterated hashing with mutated round count
        result = data
        for _ in range(challenge.mutation_params.hash_rounds):
            result = hashlib.sha256(result).digest()

        return result


class MutatingChallengeNetwork:
    """
    In-memory model of a mutating challenge round with round-robin pairing.

    EXPERIMENTAL DESIGN SKETCH: not wired into the node, consensus or
    rewards. See the module docstring for the known gaps and for what must
    exist before this may be relied on.

    What is modelled:
    1. Every ``BLOCKS_PER_ROUND`` blocks triggers a new challenge round
    2. Challenge parameters mutate based on block hash
    3. Validators are paired challenger -> target in round-robin

    Intended but NOT implemented:
    4. A 2/3 quorum to mark a validator as valid (``CONSENSUS_THRESHOLD`` is
       unused; each response is judged once, locally)
    5. Reward loss or slashing (``get_slashed_validators`` only reads a local
       failure counter; nothing acts on it)
    """

    CONSENSUS_THRESHOLD = 0.67  # 2/3 must agree
    BLOCKS_PER_ROUND = 10       # Challenge every 10 blocks
    MAX_FAILURES = 3            # Failures before slashing

    def __init__(self, validators: List[str], genesis_seed: bytes = None):
        self.mutator = ChallengeMutator(genesis_seed)
        self.round_robin = RoundRobinState(validators=validators)
        self.validator_failures: Dict[str, int] = {v: 0 for v in validators}
        self.validator_hardware: Dict[str, dict] = {}  # Registered hardware profiles
        self.pending_challenges: Dict[str, MutatingChallenge] = {}

    def register_hardware(self, validator: str, hardware_profile: dict):
        """Register a validator's hardware profile"""
        self.validator_hardware[validator] = hardware_profile

    def on_new_block(self, block_height: int, block_hash: bytes) -> List[MutatingChallenge]:
        """
        Called when a new block is mined.
        Returns challenges to be issued this block.
        """
        # Only challenge every N blocks
        if block_height % self.BLOCKS_PER_ROUND != 0:
            return []

        challenges = []
        pairs = self.round_robin.get_challenge_pairs()

        for challenger, target in pairs:
            # Generate mutated parameters for this challenger/target/block
            mutation = self.mutator.mutate(block_hash, target)

            challenge = MutatingChallenge(
                challenge_id=f"{block_height}-{challenger[:8]}-{target[:8]}",
                block_height=block_height,
                block_hash=block_hash,
                challenger=challenger,
                target=target,
                mutation_params=mutation,
                timestamp_ms=int(time.time() * 1000)
            )

            self.pending_challenges[challenge.challenge_id] = challenge
            self.round_robin.challenges_this_round[challenger] = target
            challenges.append(challenge)

        return challenges

    def validate_response(
        self,
        response: MutatingResponse
    ) -> Tuple[bool, float, List[str]]:
        """
        Validate a response against its challenge.

        Returns: (valid, confidence_score, failure_reasons)

        Fails closed, before any measurement is looked at, when:
        - the challenge ID is unknown;
        - ``response.responder`` is not the challenge's target;
        - no hardware profile is registered for the target.

        These early rejections return ``(False, 0.0, [reason])`` and do not
        touch round results or failure counters: nothing here is
        authenticated, so a response that never reached evaluation must not
        count as evidence against the target.

        This is still NOT sufficient for production use. Signatures are not
        verified (so the responder check compares an unauthenticated claim),
        challenges are neither single-use nor expiring, and the proof hash is
        not bound to hardware. See the module docstring.
        """
        challenge = self.pending_challenges.get(response.challenge_id)
        if not challenge:
            return False, 0.0, ["Unknown challenge ID"]

        # Fail closed: only the challenged target may answer its challenge.
        if response.responder != challenge.target:
            return False, 0.0, ["Responder does not match challenge target"]

        # Fail closed: without a registered profile there is nothing to check
        # the serial against, so the response cannot be accepted.
        expected_hardware = self.validator_hardware.get(challenge.target)
        if not expected_hardware:
            return False, 0.0, ["No hardware profile registered for target"]

        params = challenge.mutation_params
        failures = []
        confidence = 100.0

        # 1. Check jitter (using mutated threshold)
        min_jitter = params.jitter_min_percent
        if response.jitter_variance < min_jitter:
            failures.append(
                f"Jitter too consistent ({response.jitter_variance/10:.1f}% < {min_jitter/10:.1f}%) "
                f"- emulator detected"
            )
            confidence -= 40.0

        # 2. Check timing windows (using mutated ranges)
        if response.cache_timing_ticks < params.timing_min_ticks:
            failures.append(f"Cache timing too fast - possible speedhack")
            confidence -= 25.0

        # 3. Check thermal
        if response.thermal_celsius < params.thermal_min_c or \
           response.thermal_celsius > params.thermal_max_c:
            if response.thermal_celsius < 0:
                failures.append("No thermal sensor - possible VM")
            else:
                failures.append(f"Thermal out of range ({response.thermal_celsius}C)")
            confidence -= 15.0

        # 4. Check serial (mutated serial type)
        expected_serial = self._get_serial(expected_hardware, params.serial_type)

        if expected_serial and response.serial_value != expected_serial:
            failures.append(
                f"Serial mismatch for {params.serial_type}: "
                f"got '{response.serial_value}', expected '{expected_serial}'"
            )
            confidence -= 30.0
        elif not response.serial_value or response.serial_value == "UNKNOWN":
            failures.append(f"Missing {params.serial_type} serial")
            confidence -= 20.0

        # 5. Verify proof hash (must have correct round count).
        # Consistency check only: recomputed from the response's own fields
        # with empty entropy, so it does not attest to hardware.
        proof_ok = True
        if not response.proof_hash:
            proof_ok = False
            failures.append("Missing proof hash")
            confidence -= 50.0
        else:
            expected_proof = response.compute_proof(challenge, b'')
            if not secrets.compare_digest(response.proof_hash, expected_proof):
                proof_ok = False
                failures.append("Proof hash mismatch")
                confidence -= 50.0

        valid = confidence >= 50.0 and proof_ok

        # Record result
        self.round_robin.results_this_round[challenge.target] = valid

        # Update failure count
        if not valid:
            self.validator_failures[challenge.target] = \
                self.validator_failures.get(challenge.target, 0) + 1

        return valid, confidence, failures

    def _get_serial(self, hardware: dict, serial_type: str) -> Optional[str]:
        """Get serial value from hardware profile"""
        if serial_type == 'openfirmware':
            return hardware.get('openfirmware', {}).get('serial_number')
        elif serial_type == 'gpu':
            return hardware.get('gpu', {}).get('device_id')
        elif serial_type == 'storage':
            return hardware.get('storage', {}).get('serial')
        elif serial_type == 'platform':
            return hardware.get('cpu', {}).get('model')
        return None

    def get_slashed_validators(self) -> List[str]:
        """Return validators that should be slashed"""
        return [
            v for v, failures in self.validator_failures.items()
            if failures >= self.MAX_FAILURES
        ]

    def end_round(self):
        """End current challenge round and advance"""
        self.round_robin.advance_round()
        self.mutator.advance_epoch()
        self.pending_challenges.clear()


def demo_mutating_challenges():
    """Demonstrate the mutating challenge sketch (illustrative, not a security test)"""

    print("""
╔══════════════════════════════════════════════════════════════════════╗
║      RUSTCHAIN MUTATING CHALLENGE SYSTEM - ROUND ROBIN DEMO          ║
║                                                                      ║
║   "The chain mutates. The emulator cannot adapt."                    ║
╚══════════════════════════════════════════════════════════════════════╝
""")

    print("  NOTE: experimental design sketch. Not wired into the node, consensus")
    print("  or rewards; responses below are simulated and unauthenticated.\n")

    # Setup network with 4 validators
    validators = [
        "G4_MirrorDoor_125",
        "G5_Dual_130",
        "PowerBook_G4_115",
        "MacPro_Trashcan_154"
    ]

    network = MutatingChallengeNetwork(validators)

    # Register hardware profiles
    network.register_hardware("G4_MirrorDoor_125", {
        "cpu": {"model": "PowerMac3,6"},
        "openfirmware": {"serial_number": "G84243AZQ6P"},
        "gpu": {"device_id": "0x4966"},
        "storage": {"serial": "WD-WMAJ91385123"}
    })
    network.register_hardware("G5_Dual_130", {
        "cpu": {"model": "PowerMac7,3"},
        "openfirmware": {"serial_number": "G8435B2RQPR"},
        "gpu": {"device_id": "0x4152"},
        "storage": {"serial": "5QF5R18X"}
    })
    network.register_hardware("PowerBook_G4_115", {
        "cpu": {"model": "PowerBook6,8"},
        "openfirmware": {"serial_number": "4H509179RJ6"},
        "gpu": {"device_id": "0x0329"},
        "storage": {"serial": "MPB350X5G11H0C"}
    })
    network.register_hardware("MacPro_Trashcan_154", {
        "cpu": {"model": "MacPro6,1"},
        "openfirmware": {"serial_number": "TRASHCAN001"},
        "gpu": {"device_id": "0x6798"},
        "storage": {"serial": "S3T8NX0K"}
    })

    print("  Validators registered:")
    for v in validators:
        print(f"    • {v}")

    # Simulate 3 blocks
    for block_num in [10, 20, 30]:
        block_hash = hashlib.sha256(f"block_{block_num}".encode()).digest()

        print(f"\n{'='*70}")
        print(f"  BLOCK {block_num} - Hash: {block_hash.hex()[:16]}...")
        print(f"{'='*70}")

        challenges = network.on_new_block(block_num, block_hash)

        for challenge in challenges:
            print(f"\n  Challenge: {challenge.challenger[:15]} → {challenge.target[:15]}")
            print(f"    Mutation Hash: {challenge.mutation_params.hash()}")
            print(f"    Cache Stride: {challenge.mutation_params.cache_stride} bytes")
            print(f"    Cache Iterations: {challenge.mutation_params.cache_iterations}")
            print(f"    Memory Size: {challenge.mutation_params.memory_size_kb} KB")
            print(f"    Pipeline Depth: {challenge.mutation_params.pipeline_test_depth}")
            print(f"    Hash Rounds: {challenge.mutation_params.hash_rounds}")
            print(f"    Serial Check: {challenge.mutation_params.serial_type}")

            # Simulate response from real hardware
            response = MutatingResponse(
                challenge_id=challenge.challenge_id,
                responder=challenge.target,
                cache_timing_ticks=1500 + (block_num * 10),
                memory_timing_ticks=45000 + (block_num * 100),
                pipeline_timing_ticks=8000 + (block_num * 50),
                jitter_variance=150 + (block_num % 50),  # Natural variance
                thermal_celsius=35 + (block_num % 20),
                serial_value=network._get_serial(
                    network.validator_hardware[challenge.target],
                    challenge.mutation_params.serial_type
                ) or "UNKNOWN",
                proof_hash=b'',
                timestamp_ms=int(time.time() * 1000)
            )
            response.proof_hash = response.compute_proof(challenge, b'')

            valid, confidence, failures = network.validate_response(response)

            print(f"\n    Response from {challenge.target[:15]}:")
            print(f"      Jitter: {response.jitter_variance/10:.1f}%")
            print(f"      Thermal: {response.thermal_celsius}°C")
            print(f"      Serial ({challenge.mutation_params.serial_type}): {response.serial_value}")
            print(f"      Valid: {'✓ YES' if valid else '✗ NO'} (Confidence: {confidence:.1f}%)")

            if failures:
                for f in failures:
                    print(f"      ⚠ {f}")

        network.end_round()

    print(f"\n{'='*70}")
    print("  MUTATION ANALYSIS")
    print(f"{'='*70}")
    print("""
  Notice how parameters CHANGED each block:
  • Cache stride varied from 32-512 bytes
  • Hash rounds varied from 500-5000
  • Different serial types checked each round

  The design intent is that an emulator would need to:
  1. Know the next block hash in advance
  2. Pre-compute responses for every possible mutation
  3. Reproduce plausible timing for all parameter combinations

  This demo does not establish any of that: measurements here are
  self-reported and nothing is signed or bound to hardware. See the
  module docstring for what must exist before this is relied on.
""")

    print("""
╔══════════════════════════════════════════════════════════════════════╗
║     "The chain mutates. The emulator cannot adapt.                   ║
║      Real hardware persists."                                        ║
╚══════════════════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    demo_mutating_challenges()
