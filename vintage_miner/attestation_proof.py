#!/usr/bin/env python3
"""
Attestation Proof Generator for RustChain Vintage Hardware
==========================================================

Generates cryptographic proofs for vintage hardware attestation.
Part of Bounty #2314 - Ghost in the Machine.

Usage:
    python3 attestation_proof.py --miner-id my-pentium-ii --profile pentium_ii
    python3 attestation_proof.py --verify proof.json
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import struct
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

# Try to import hardware profiles (optional - works without it)
try:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from hardware_profiles import get_profile, get_multiplier, get_era, get_bounty
    HAS_PROFILES = True
except ImportError:
    HAS_PROFILES = False


# =============================================================================
# CRYPTOGRAPHIC PRIMITIVES (Reference Implementation)
# =============================================================================

def sha256(data: bytes) -> bytes:
    """SHA-256 hash"""
    return hashlib.sha256(data).digest()


def sha512(data: bytes) -> bytes:
    """SHA-512 hash"""
    return hashlib.sha512(data).digest()


def hmac_sha512(key: bytes, data: bytes) -> bytes:
    """HMAC-SHA512"""
    return hmac.new(key, data, hashlib.sha512).digest()


def generate_challenge_response(challenge: bytes, private_key_seed: bytes) -> bytes:
    """
    Generate a challenge response using HMAC-SHA512
    
    In production, this would use actual Ed25519 signing.
    This reference implementation uses HMAC for demonstration.
    """
    return hmac_sha512(private_key_seed, challenge)


def verify_challenge_response(
    challenge: bytes, 
    response: bytes, 
    public_key_seed: bytes
) -> bool:
    """
    Verify a challenge response
    
    In production, this verifies Ed25519 signatures.
    """
    expected = generate_challenge_response(challenge, public_key_seed)
    return hmac.compare_digest(response, expected)


# =============================================================================
# HARDWARE FINGERPRINTING
# =============================================================================

class HardwareFingerprint:
    """
    Generates unique fingerprints for vintage hardware based on:
    - CPU characteristics (simulated via profiles)
    - Timing signatures
    - Device-specific entropy
    """
    
    # CPUID-like instruction results for different architectures
    CPUID_SIMULATION = {
        "intel_386": {
            "vendor": b"GenuineIntel",
            "version": 0x00000300,
            "feature_flags": 0x00000000,
            "serial": b"386-0001",
        },
        "intel_486": {
            "vendor": b"GenuineIntel",
            "version": 0x00000400,
            "feature_flags": 0x00000001,  # FPU
            "serial": b"486-0001",
        },
        "pentium": {
            "vendor": b"GenuineIntel",
            "version": 0x00000500,
            "feature_flags": 0x00800001,  # FPU + MMX
            "serial": b"PENTIUM-001",
        },
        "pentium_ii": {
            "vendor": b"GenuineIntel",
            "version": 0x00000600,
            "feature_flags": 0x00800003,  # FPU + MMX + CX8
            "serial": b"PENTIUMII-001",
        },
        "amd_k6": {
            "vendor": b"AuthenticAMD",
            "version": 0x00000580,
            "feature_flags": 0x00800002,
            "serial": b"AMD-K6-001",
        },
        "motorola_68000": {
            "vendor": b"Motorola68K",
            "version": 0x00000001,
            "feature_flags": 0x00000000,
            "serial": b"MC68000-001",
        },
        "mos_6502": {
            "vendor": b"MOSTechnology",
            "version": 0x00000001,
            "feature_flags": 0x00000000,
            "serial": b"6502-001",
        },
    }
    
    def __init__(self, miner_id: str, profile_name: str, device_entropy: Optional[bytes] = None):
        self.miner_id = miner_id
        self.profile_name = profile_name
        self.device_entropy = device_entropy or self._generate_device_entropy()
        
    def _generate_device_entropy(self) -> bytes:
        """Generate device-specific entropy"""
        # In production, this would collect entropy from real hardware
        # Sources: timing jitter, device serial numbers, MAC addresses, etc.
        entropy_base = sha512(f"{self.miner_id}:vintage:rustchain".encode())
        return entropy_base
    
    def get_cpuid_simulation(self) -> Dict[str, bytes]:
        """Get simulated CPUID results for the profile"""
        # Try exact match first, then fall back to architecture family
        if self.profile_name in self.CPUID_SIMULATION:
            return self.CPUID_SIMULATION[self.profile_name]
        
        # Fall back based on architecture family
        if "intel" in self.profile_name:
            return self.CPUID_SIMULATION["pentium_ii"]
        elif "amd" in self.profile_name:
            return self.CPUID_SIMULATION["amd_k6"]
        elif "motorola" in self.profile_name or "68000" in self.profile_name:
            return self.CPUID_SIMULATION["motorola_68000"]
        elif "mos_6502" in self.profile_name or "6502" in self.profile_name:
            return self.CPUID_SIMULATION["mos_6502"]
        else:
            return self.CPUID_SIMULATION["pentium"]
    
    def generate_timing_signature(self, num_samples: int = 100) -> Dict[str, float]:
        """
        Generate timing signature by measuring execution time variance
        
        Vintage hardware has characteristic timing jitter patterns due to:
        - Slower, less precise oscillators
        - No modern power management
        - Analog circuit characteristics
        """
        # Simulate timing measurements
        # In production, this would use actual CPU timing instructions
        import random
        
        # Profile-specific timing characteristics
        timing_params = self._get_timing_params()
        min_jitter, max_jitter = timing_params
        
        samples = []
        for _ in range(num_samples):
            base_jitter = random.uniform(min_jitter, max_jitter)
            noise = random.gauss(0, (max_jitter - min_jitter) * 0.15)
            samples.append(max(0.001, base_jitter + noise))
        
        mean = sum(samples) / len(samples)
        variance = sum((x - mean) ** 2 for x in samples) / len(samples)
        stddev = variance ** 0.5
        
        # Calculate stability score (relative consistency)
        stability = 1.0 - (stddev / mean) if mean > 0 else 0.0
        
        return {
            "mean_ms": round(mean, 4),
            "stddev_ms": round(stddev, 4),
            "min_ms": round(min(samples), 4),
            "max_ms": round(max(samples), 4),
            "stability_score": round(stability, 4),
            "sample_count": num_samples,
        }
    
    def _get_timing_params(self) -> Tuple[float, float]:
        """Get profile-specific timing parameters"""
        if not HAS_PROFILES:
            return (1.0, 5.0)  # Default
        
        try:
            profile = get_profile(self.profile_name)
            return profile.timing_variance
        except (ValueError, AttributeError):
            return (1.0, 5.0)
    
    def compute_fingerprint(self) -> str:
        """
        Compute the full hardware fingerprint
        
        Combines:
        - CPUID simulation
        - Timing signature
        - Device entropy
        - Miner ID
        """
        cpuid = self.get_cpuid_simulation()
        timing = self.generate_timing_signature()
        
        # Build fingerprint data
        fp_data = {
            "miner_id": self.miner_id,
            "profile": self.profile_name,
            "cpuid_vendor": cpuid["vendor"].decode("utf-8", errors="replace"),
            "cpuid_version": hex(cpuid["version"]),
            "cpuid_feature_flags": hex(cpuid["feature_flags"]),
            "cpuid_serial": cpuid["serial"].decode("utf-8", errors="replace"),
            "timing_mean_ms": timing["mean_ms"],
            "timing_stddev_ms": timing["stddev_ms"],
            "timing_stability": timing["stability_score"],
            "device_entropy": self.device_entropy.hex(),
        }
        
        # Serialize and hash
        fp_json = json.dumps(fp_data, sort_keys=True)
        fp_hash = sha256(fp_json.encode("utf-8"))
        
        return fp_hash.hex()


# =============================================================================
# ATTESTATION PROOF
# =============================================================================

@dataclass
class TimingProof:
    """Timing-based proof of vintage hardware authenticity"""
    jitter_mean_ms: float
    jitter_stddev_ms: float
    stability_score: float
    sample_count: int
    measurement_duration_ms: int


@dataclass 
class AttestationProof:
    """
    Complete attestation proof for vintage hardware mining
    
    Contains all data needed to verify a miner's hardware age and authenticity.
    """
    version: str = "1.0"
    miner_id: str = ""
    device_arch: str = ""
    profile_name: str = ""
    
    # Hardware identification
    fingerprint_hash: str = ""
    cpuid_vendor: str = ""
    cpuid_version: str = ""
    cpuid_feature_flags: str = ""
    cpuid_serial: str = ""
    
    # Timing proof
    timing_proof: Optional[TimingProof] = None
    
    # Multiplier and bounty
    era: str = ""
    base_multiplier: float = 0.0
    bounty_rtc: int = 0
    
    # Timestamps and signatures
    created_at_unix: int = 0
    created_at_iso: str = ""
    challenge: str = ""
    response: str = ""
    signature: str = ""
    
    # Slot and node info
    slot: int = 0
    ttl_hours: int = 24
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        result = asdict(self)
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AttestationProof":
        """Create from dictionary"""
        if data.get("timing_proof"):
            data["timing_proof"] = TimingProof(**data["timing_proof"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class AttestationProofGenerator:
    """
    Generates and verifies attestation proofs for vintage hardware
    
    Usage:
        generator = AttestationProofGenerator(miner_id="my-miner", profile="pentium_ii")
        proof = generator.generate_proof()
        generator.verify(proof)
    """
    
    CURRENT_SLOT = 12345  # Would come from blockchain in production
    SLOT_TIME_SECONDS = 400  # ~400ms per slot in production
    
    def __init__(
        self,
        miner_id: str,
        profile: str,
        private_key_seed: Optional[bytes] = None,
        wallet: str = ""
    ):
        self.miner_id = miner_id
        self.profile = profile
        self.wallet = wallet
        
        # Generate or use provided private key seed
        # In production, this would be a real Ed25519 private key
        self.private_key_seed = private_key_seed or self._generate_key_seed()
        self.public_key_seed = self.private_key_seed  # In production, derived
        
        # Generate fingerprint
        self.fingerprint = HardwareFingerprint(miner_id, profile)
        
        # Load profile data
        if HAS_PROFILES:
            try:
                self.profile_data = get_profile(profile)
                self.multiplier = self.profile_data.base_multiplier
                self.era = get_era(profile)
                self.bounty = get_bounty(profile)
            except (ValueError, AttributeError):
                self._set_defaults()
        else:
            self._set_defaults()
    
    def _set_defaults(self):
        """Set default values when profiles aren't available"""
        self.profile_data = None
        self.multiplier = 2.0
        self.era = "1995-1999"
        self.bounty = 100
    
    def _generate_key_seed(self) -> bytes:
        """Generate a deterministic key seed from miner ID"""
        seed = hashlib.pbkdf2_hmac(
            'sha256',
            self.miner_id.encode('utf-8'),
            b'rustchain-vintage-mining-v1',
            1000,
            dklen=32
        )
        return seed
    
    def _generate_challenge(self) -> bytes:
        """Generate a random challenge for signing"""
        # In production, this would come from the node
        challenge_data = f"{self.miner_id}:{int(time.time())}:{os.urandom(16).hex()}"
        return sha256(challenge_data.encode())
    
    def _generate_signature(self, data: bytes) -> str:
        """Generate signature over data"""
        sig = hmac_sha512(self.private_key_seed, data)
        return f"ed25519:{sig.hex()}"
    
    def _verify_signature(self, data: bytes, signature: str) -> bool:
        """Verify signature"""
        if not signature.startswith("ed25519:"):
            return False
        
        expected = hmac_sha512(self.public_key_seed, data)
        actual = bytes.fromhex(signature[8:])
        
        return hmac.compare_digest(expected, actual)
    
    def generate_proof(self, slot: Optional[int] = None) -> AttestationProof:
        """
        Generate a complete attestation proof
        
        Args:
            slot: Blockchain slot number (optional, auto-generated if not provided)
            
        Returns:
            AttestationProof object
        """
        now = int(time.time())
        
        # Generate hardware fingerprint
        fingerprint_hash = self.fingerprint.compute_fingerprint()
        cpuid = self.fingerprint.get_cpuid_simulation()
        timing = self.fingerprint.generate_timing_signature()
        
        # Create timing proof
        timing_proof = TimingProof(
            jitter_mean_ms=timing["mean_ms"],
            jitter_stddev_ms=timing["stddev_ms"],
            stability_score=timing["stability_score"],
            sample_count=timing["sample_count"],
            measurement_duration_ms=int(timing["mean_ms"] * timing["sample_count"])
        )
        
        # Generate challenge-response
        challenge = self._generate_challenge()
        response = generate_challenge_response(challenge, self.private_key_seed)
        
        # Create proof data for signing
        proof_data = (
            f"{self.miner_id}:"
            f"{fingerprint_hash}:"
            f"{timing_proof.jitter_mean_ms}:"
            f"{timing_proof.stability_score}:"
            f"{now}"
        ).encode()
        
        # Sign the proof
        signature = self._generate_signature(proof_data)
        
        # Build attestation proof
        proof = AttestationProof(
            version="1.0",
            miner_id=self.miner_id,
            device_arch=self.profile,
            profile_name=self.profile_data.name if self.profile_data else self.profile,
            
            # Hardware identification
            fingerprint_hash=fingerprint_hash,
            cpuid_vendor=cpuid["vendor"].decode("utf-8", errors="replace"),
            cpuid_version=hex(cpuid["version"]),
            cpuid_feature_flags=hex(cpuid["feature_flags"]),
            cpuid_serial=cpuid["serial"].decode("utf-8", errors="replace"),
            
            # Timing proof
            timing_proof=timing_proof,
            
            # Multiplier and bounty
            era=self.era,
            base_multiplier=self.multiplier,
            bounty_rtc=self.bounty,
            
            # Timestamps
            created_at_unix=now,
            created_at_iso=datetime.utcfromtimestamp(now).isoformat() + "Z",
            
            # Challenge-response
            challenge=challenge.hex(),
            response=response.hex(),
            signature=signature,
            
            # Slot info
            slot=slot or self.CURRENT_SLOT,
            ttl_hours=24,
        )
        
        return proof
    
    def verify_proof(self, proof: AttestationProof) -> Tuple[bool, List[str]]:
        """
        Verify an attestation proof
        
        Returns:
            (is_valid, error_messages)
        """
        errors = []
        
        # Check version
        if proof.version != "1.0":
            errors.append(f"Unknown proof version: {proof.version}")
        
        # Check miner ID matches
        if proof.miner_id != self.miner_id:
            errors.append("Miner ID mismatch")
        
        # Check profile matches
        if proof.device_arch != self.profile:
            errors.append("Profile mismatch")
        
        # Check timing proof is present and valid
        if not proof.timing_proof:
            errors.append("Missing timing proof")
        else:
            tp = proof.timing_proof
            
            # Check jitter is in reasonable range for vintage hardware
            if tp.jitter_mean_ms <= 0:
                errors.append("Invalid jitter mean (must be > 0)")
            
            if tp.stability_score <= 0 or tp.stability_score > 1:
                errors.append("Stability score out of range (0-1)")
            
            # Check sample count
            if tp.sample_count < 10:
                errors.append("Insufficient timing samples")
        
        # Verify signature
        proof_data = (
            f"{proof.miner_id}:"
            f"{proof.fingerprint_hash}:"
            f"{proof.timing_proof.jitter_mean_ms if proof.timing_proof else 0}:"
            f"{proof.timing_proof.stability_score if proof.timing_proof else 0}:"
            f"{proof.created_at_unix}"
        ).encode()
        
        if not self._verify_signature(proof_data, proof.signature):
            errors.append("Signature verification failed")
        
        # Check TTL
        now = int(time.time())
        age_hours = (now - proof.created_at_unix) / 3600
        if age_hours > proof.ttl_hours:
            errors.append(f"Proof expired (age: {age_hours:.1f}h, TTL: {proof.ttl_hours}h)")
        
        return len(errors) == 0, errors
    
    def export_proof(self, proof: AttestationProof, filepath: str):
        """Export proof to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(proof.to_dict(), f, indent=2)
        print(f"Proof exported to: {filepath}")
    
    def import_proof(self, filepath: str) -> AttestationProof:
        """Import proof from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return AttestationProof.from_dict(data)


# =============================================================================
# MAIN CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Attestation Proof Generator for RustChain Vintage Hardware Mining"
    )
    
    parser.add_argument(
        "--miner-id", "-m",
        help="Unique miner identifier"
    )
    
    parser.add_argument(
        "--profile", "-p",
        choices=[
            "intel_386", "intel_486", "pentium", "pentium_mmx", "pentium_pro", "pentium_ii",
            "amd_k5", "amd_k6", "cyrix_6x86", "cyrix_mii",
            "motorola_68000", "mos_6502",
            "powerpc_601", "powerpc_603", "powerpc_604", "powerpc_750",
            "dec_vax", "sparc_v8", "dec_alpha",
            "nes_6502", "snes_65c816", "genesis_68000", "ps1_mips", "dreamcast_sh4",
        ],
        help="Vintage CPU profile"
    )
    
    parser.add_argument(
        "--wallet", "-w",
        default="",
        help="RTC wallet address"
    )
    
    parser.add_argument(
        "--slot", "-s",
        type=int,
        default=None,
        help="Blockchain slot number"
    )
    
    parser.add_argument(
        "--verify", "-v",
        help="Verify an existing proof file"
    )
    
    parser.add_argument(
        "--export", "-e",
        help="Export proof to file"
    )
    
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output as JSON"
    )
    
    args = parser.parse_args()
    
    # Verify mode
    if args.verify:
        generator = AttestationProofGenerator(
            miner_id="unknown",
            profile="pentium_ii"
        )
        
        try:
            proof = generator.import_proof(args.verify)
            print(f"Loaded proof for miner: {proof.miner_id}")
            print(f"Device: {proof.device_arch}")
            print(f"Era: {proof.era}")
            print(f"Multiplier: {proof.base_multiplier}x")
            print(f"Bounty: {proof.bounty_rtc} RTC")
            print(f"Created: {proof.created_at_iso}")
            print(f"Signature: {proof.signature[:64]}...")
            
            # Verify
            is_valid, errors = generator.verify_proof(proof)
            if is_valid:
                print("\n✅ Proof is VALID")
            else:
                print("\n❌ Proof is INVALID:")
                for error in errors:
                    print(f"  - {error}")
        
        except Exception as e:
            print(f"Error loading proof: {e}")
        
        return 0
    
    # Generate mode
    if not args.miner_id or not args.profile:
        parser.error("--miner-id and --profile are required for generation")
    
    generator = AttestationProofGenerator(
        miner_id=args.miner_id,
        profile=args.profile,
        wallet=args.wallet
    )
    
    print("=" * 70)
    print("VINTAGE HARDWARE ATTESTATION PROOF GENERATOR")
    print("=" * 70)
    print(f"Miner ID:    {generator.miner_id}")
    print(f"Profile:     {generator.profile}")
    print(f"Era:         {generator.era}")
    print(f"Multiplier:  {generator.multiplier}x")
    print(f"Bounty:      {generator.bounty} RTC")
    print("=" * 70)
    
    proof = generator.generate_proof(slot=args.slot)
    
    print(f"\nGenerated Attestation Proof:")
    print(f"  Fingerprint Hash: {proof.fingerprint_hash[:32]}...")
    print(f"  CPUID Vendor:     {proof.cpuid_vendor}")
    print(f"  CPUID Version:    {proof.cpuid_version}")
    print(f"  Timing Mean:      {proof.timing_proof.jitter_mean_ms} ms")
    print(f"  Timing StdDev:    {proof.timing_proof.jitter_stddev_ms} ms")
    print(f"  Stability Score:  {proof.timing_proof.stability_score}")
    print(f"  Signature:        {proof.signature[:64]}...")
    print(f"  Created:          {proof.created_at_iso}")
    print(f"  Slot:             {proof.slot}")
    
    # Verify the proof
    is_valid, errors = generator.verify_proof(proof)
    if is_valid:
        print(f"\n✅ Proof self-verification: PASSED")
    else:
        print(f"\n❌ Proof self-verification: FAILED")
        for error in errors:
            print(f"  - {error}")
    
    # Export if requested
    if args.export:
        generator.export_proof(proof, args.export)
    
    # JSON output
    if args.json:
        print("\n--- JSON OUTPUT ---")
        print(json.dumps(proof.to_dict(), indent=2))
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
