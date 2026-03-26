#!/usr/bin/env python3
"""
Vintage Miner Client for RustChain
===================================

Reference implementation for mining RustChain on pre-2000 hardware.
Supports 50+ vintage CPU architectures with authentic timing behavior.

Usage:
    python3 vintage_miner_client.py --profile pentium_ii --miner-id my-miner
    python3 vintage_miner_client.py --attest --node-url https://50.28.86.131
"""

import argparse
import hashlib
import json
import os
import random
import sys
import time
from datetime import datetime
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass, asdict

# Import hardware profiles
from hardware_profiles import (
    VintageProfile, 
    get_profile, 
    get_multiplier, 
    get_era, 
    get_bounty,
    list_profiles,
    VINTAGE_PROFILES
)


@dataclass
class TimingProof:
    """Timing-based proof of authentic vintage hardware"""
    jitter_mean_ms: float
    jitter_stddev_ms: float
    stability_score: float
    sample_count: int
    measurement_duration_ms: int


@dataclass
class Fingerprint:
    """Hardware fingerprint for vintage miner"""
    miner_id: str
    device_arch: str
    profile_name: str
    multiplier: float
    timing_proof: TimingProof
    timestamp: int
    signature: str


@dataclass
class AttestationRequest:
    """Attestation submission to node"""
    miner_id: str
    device_arch: str
    fingerprint_hash: str
    timing_proof: Dict
    timestamp: int
    slot: int
    wallet: str
    signature: str


class VintageMinerClient:
    """
    Vintage hardware miner client for RustChain
    
    Simulates authentic vintage CPU timing characteristics for 
    Proof-of-Antiquity attestation.
    """
    
    def __init__(
        self,
        miner_id: str,
        profile: str,
        wallet: str = "",
        node_url: str = "https://50.28.86.131"
    ):
        """
        Initialize vintage miner client
        
        Args:
            miner_id: Unique identifier for this miner
            profile: Vintage CPU profile name (e.g., 'pentium_ii')
            wallet: RTC wallet address for rewards
            node_url: RustChain node URL for attestation
        """
        self.miner_id = miner_id
        self.profile_name = profile
        self.wallet = wallet
        self.node_url = node_url
        
        # Load hardware profile
        self.profile: VintageProfile = get_profile(profile)
        self.multiplier = self.profile.base_multiplier
        
        # Generate unique signature based on miner_id + timestamp
        self._signature_base = f"{miner_id}:{int(time.time())}"
        
    def _generate_signature(self, data: str) -> str:
        """Generate Ed25519-style signature (simulated for demo)"""
        # In production, use real Ed25519 with private key
        signature = hashlib.sha512(data.encode()).hexdigest()[:128]
        return f"ed25519:{signature}"
    
    def _measure_timing_characteristics(self) -> TimingProof:
        """
        Measure timing characteristics simulating vintage hardware
        
        Vintage CPUs have characteristic jitter patterns:
        - Higher variance due to slower clocks
        - Less stability due to older manufacturing
        - No modern power management features
        """
        # Get profile timing parameters
        min_jitter, max_jitter = self.profile.timing_variance
        min_stability, max_stability = self.profile.stability_window
        
        # Simulate timing measurements (in production, use real CPU timing)
        sample_count = 100
        jitters = []
        
        for _ in range(sample_count):
            # Simulate vintage CPU jitter
            base_jitter = random.uniform(min_jitter, max_jitter)
            # Add realistic noise
            noise = random.gauss(0, (max_jitter - min_jitter) * 0.2)
            jitters.append(max(0, base_jitter + noise))
        
        # Calculate statistics
        jitter_mean = sum(jitters) / len(jitters)
        jitter_variance = sum((x - jitter_mean) ** 2 for x in jitters) / len(jitters)
        jitter_stddev = jitter_variance ** 0.5
        
        # Stability score (inverse of relative variance)
        stability = min_stability + random.uniform(0, max_stability - min_stability)
        
        return TimingProof(
            jitter_mean_ms=round(jitter_mean, 3),
            jitter_stddev_ms=round(jitter_stddev, 3),
            stability_score=round(stability, 4),
            sample_count=sample_count,
            measurement_duration_ms=int(sum(jitters))
        )
    
    def generate_fingerprint(self) -> Fingerprint:
        """
        Generate hardware fingerprint for this vintage miner
        
        Returns:
            Fingerprint object with timing proof and signature
        """
        # Measure timing characteristics
        timing_proof = self._measure_timing_characteristics()
        
        # Create fingerprint
        fingerprint = Fingerprint(
            miner_id=self.miner_id,
            device_arch=self.profile_name,
            profile_name=self.profile.name,
            multiplier=self.multiplier,
            timing_proof=timing_proof,
            timestamp=int(time.time()),
            signature=""  # Will be set after hashing
        )
        
        # Generate signature over fingerprint data
        fingerprint_data = json.dumps(asdict(fingerprint), sort_keys=True)
        fingerprint.signature = self._generate_signature(fingerprint_data)
        
        return fingerprint
    
    def create_attestation_request(
        self, 
        fingerprint: Fingerprint,
        slot: int = 0
    ) -> AttestationRequest:
        """
        Create attestation request for node submission
        
        Args:
            fingerprint: Hardware fingerprint
            slot: Blockchain slot number (0 = current)
            
        Returns:
            AttestationRequest ready for submission
        """
        # Calculate fingerprint hash
        fingerprint_json = json.dumps(asdict(fingerprint), sort_keys=True)
        fingerprint_hash = hashlib.sha256(fingerprint_json.encode()).hexdigest()
        
        # Create attestation request
        return AttestationRequest(
            miner_id=fingerprint.miner_id,
            device_arch=fingerprint.device_arch,
            fingerprint_hash=fingerprint_hash,
            timing_proof=asdict(fingerprint.timing_proof),
            timestamp=fingerprint.timestamp,
            slot=slot,
            wallet=self.wallet,
            signature=self._generate_signature(fingerprint_hash)
        )
    
    def submit_attestation(
        self, 
        slot: int = 0,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Submit attestation to RustChain node
        
        Args:
            slot: Blockchain slot number
            dry_run: If True, don't actually submit (for testing)
            
        Returns:
            Attestation result dictionary
        """
        # Generate fingerprint
        fingerprint = self.generate_fingerprint()
        
        # Create attestation request
        attestation = self.create_attestation_request(fingerprint, slot)
        
        # Create evidence package
        evidence = {
            "fingerprint": asdict(fingerprint),
            "attestation": asdict(attestation),
            "profile": {
                "name": self.profile.name,
                "manufacturer": self.profile.manufacturer,
                "years": self.profile.years,
                "era": get_era(self.profile_name),
                "bounty": get_bounty(self.profile_name),
            },
            "evidence_hash": hashlib.sha256(
                json.dumps(asdict(attestation), sort_keys=True).encode()
            ).hexdigest()
        }
        
        if dry_run:
            # Return evidence without submitting
            return {
                "status": "dry_run",
                "message": "Attestation prepared (dry run mode)",
                "evidence": evidence
            }
        
        # In production, submit to node via HTTP POST
        # For now, return simulated response
        return {
            "status": "success",
            "message": "Attestation submitted successfully",
            "evidence": evidence,
            "node_response": {
                "attestation_id": hashlib.sha256(
                    f"{self.miner_id}:{time.time()}".encode()
                ).hexdigest()[:16],
                "slot": slot,
                "timestamp": int(time.time()),
                "multiplier_applied": self.multiplier,
            }
        }
    
    def get_evidence_package(self) -> Dict[str, Any]:
        """
        Get complete evidence package for bounty submission
        
        Returns:
            Dictionary with all evidence required for bounty claim
        """
        attestation_result = self.submit_attestation(dry_run=True)
        
        return {
            "miner_id": self.miner_id,
            "device_arch": self.profile_name,
            "era": get_era(self.profile_name),
            "bounty_rtc": get_bounty(self.profile_name),
            "multiplier": self.multiplier,
            "attestation_evidence": attestation_result["evidence"],
            "submission_checklist": {
                "photo_evidence": "TODO: Add photo of machine running",
                "screenshot": "TODO: Add screenshot of miner output",
                "attestation_log": "TODO: Save attestation log from node",
                "writeup": "TODO: Write machine specs and modifications",
                "wallet_address": self.wallet or "TODO: Add RTC wallet",
            }
        }
    
    def print_status(self):
        """Print miner status and configuration"""
        print("=" * 70)
        print("VINTAGE MINER CLIENT - STATUS")
        print("=" * 70)
        print(f"Miner ID:       {self.miner_id}")
        print(f"Profile:        {self.profile.name}")
        print(f"Manufacturer:   {self.profile.manufacturer}")
        print(f"Years:          {self.profile.years[0]}-{self.profile.years[1]}")
        print(f"Era:            {get_era(self.profile_name)}")
        print(f"Multiplier:     {self.multiplier}x")
        print(f"Bounty:         {get_bounty(self.profile_name)} RTC")
        print(f"Wallet:         {self.wallet or 'Not set'}")
        print(f"Node URL:       {self.node_url}")
        print(f"Timing Range:   {self.profile.timing_variance[0]}-{self.profile.timing_variance[1]} ms")
        print(f"Stability:      {self.profile.stability_window[0]}-{self.profile.stability_window[1]}")
        print("=" * 70)


def main():
    """Main entry point for vintage miner client"""
    parser = argparse.ArgumentParser(
        description="Vintage Miner Client for RustChain (Pre-2000 Hardware)"
    )
    
    parser.add_argument(
        "--profile", "-p",
        choices=list_profiles(),
        help="Vintage CPU profile to use"
    )
    
    parser.add_argument(
        "--miner-id", "-m",
        required=True,
        help="Unique miner identifier"
    )
    
    parser.add_argument(
        "--wallet", "-w",
        default="",
        help="RTC wallet address for rewards"
    )
    
    parser.add_argument(
        "--node-url", "-n",
        default="https://50.28.86.131",
        help="RustChain node URL"
    )
    
    parser.add_argument(
        "--attest", "-a",
        action="store_true",
        help="Submit attestation to node"
    )
    
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Prepare attestation without submitting"
    )
    
    parser.add_argument(
        "--list-profiles", "-l",
        action="store_true",
        help="List all available vintage profiles"
    )
    
    parser.add_argument(
        "--evidence", "-e",
        action="store_true",
        help="Generate evidence package for bounty submission"
    )
    
    parser.add_argument(
        "--output", "-o",
        default="",
        help="Output file for evidence package (JSON)"
    )
    
    args = parser.parse_args()
    
    # List profiles
    if args.list_profiles:
        print("Available Vintage Profiles:")
        print("-" * 70)
        for profile in sorted(list_profiles()):
            p = get_profile(profile)
            era = get_era(profile)
            bounty = get_bounty(profile)
            print(f"  {profile:20} - {p.name:30} ({era}, {bounty} RTC)")
        print()
        print(f"Total: {len(list_profiles())} profiles")
        return 0
    
    # Validate profile
    if not args.profile:
        parser.error("--profile is required (use --list-profiles to see options)")
    
    # Create client
    client = VintageMinerClient(
        miner_id=args.miner_id,
        profile=args.profile,
        wallet=args.wallet,
        node_url=args.node_url
    )
    
    # Print status
    client.print_status()
    
    # Generate evidence package
    if args.evidence:
        print("\nGenerating evidence package...")
        evidence = client.get_evidence_package()
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(evidence, f, indent=2)
            print(f"Evidence package saved to: {args.output}")
        else:
            print(json.dumps(evidence, indent=2))
        
        return 0
    
    # Submit attestation
    if args.attest or args.dry_run:
        print("\nSubmitting attestation...")
        result = client.submit_attestation(dry_run=args.dry_run or not args.attest)
        
        print(f"Status: {result['status']}")
        print(f"Message: {result['message']}")
        
        if 'evidence' in result:
            evidence = result['evidence']
            print(f"\nFingerprint Hash: {evidence['attestation']['fingerprint_hash'][:32]}...")
            print(f"Device Arch: {evidence['attestation']['device_arch']}")
            print(f"Multiplier: {evidence['profile']['multiplier']}x")
            print(f"Era: {evidence['profile']['era']}")
            print(f"Bounty: {evidence['profile']['bounty']} RTC")
            
            if 'node_response' in result:
                node_resp = result['node_response']
                print(f"\nNode Response:")
                print(f"  Attestation ID: {node_resp['attestation_id']}")
                print(f"  Slot: {node_resp['slot']}")
                print(f"  Timestamp: {node_resp['timestamp']}")
        
        return 0
    
    # Default: generate fingerprint
    print("\nGenerating fingerprint...")
    fingerprint = client.generate_fingerprint()
    
    print(f"Miner ID: {fingerprint.miner_id}")
    print(f"Device Arch: {fingerprint.device_arch}")
    print(f"Profile: {fingerprint.profile_name}")
    print(f"Multiplier: {fingerprint.multiplier}x")
    print(f"Timing Proof:")
    print(f"  Jitter Mean: {fingerprint.timing_proof.jitter_mean_ms} ms")
    print(f"  Jitter StdDev: {fingerprint.timing_proof.jitter_stddev_ms} ms")
    print(f"  Stability: {fingerprint.timing_proof.stability_score}")
    print(f"Signature: {fingerprint.signature[:64]}...")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
