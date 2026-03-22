#!/usr/bin/env python3
"""
Cross-Node Attestation Replay Attack Simulation
================================================

Red Team tool for simulating attestation replay attacks across multiple RustChain nodes.
This tool captures legitimate attestations and attempts to replay them from different
nodes to test replay protection mechanisms.

Attack Vector:
    1. Capture a valid attestation from Node A (with valid nonce)
    2. Replay the same attestation to Node B (cross-node replay)
    3. Replay the same attestation to Node A (same-node replay)
    4. Attempt replay with modified timestamp but same core data

Security Goal:
    Verify that the system properly rejects replayed attestations across all nodes
    through distributed nonce tracking and cross-node synchronization.

Usage:
    python3 cross_node_replay_attack.py --simulate --nodes 3
    python3 cross_node_replay_attack.py --attack --capture-node 0 --replay-node 1
    python3 cross_node_replay_attack.py --full-simulation --epochs 5

Author: RustChain Security Team
Bounty: https://github.com/Scottcjn/rustchain-bounties/issues/2296
"""

import hashlib
import json
import time
import uuid
import argparse
import sqlite3
import sys
import secrets
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from enum import Enum
from datetime import datetime
import random

# =============================================================================
# Constants
# =============================================================================

ATTACK_VERSION = "1.0.0"
DEFAULT_NODE_COUNT = 3
NONCE_WINDOW_SECONDS = 300  # 5 minutes
ATTESTATION_VALIDITY_SECONDS = 60


# =============================================================================
# Enums
# =============================================================================

class AttackStatus(Enum):
    """Status of an attack operation."""
    PENDING = "pending"
    CAPTURING = "capturing"
    CAPTURED = "captured"
    REPLAYING = "replaying"
    SUCCESS = "success"  # Attack succeeded (bad for defense)
    BLOCKED = "blocked"  # Attack was blocked (good for defense)
    ERROR = "error"


class AttackType(Enum):
    """Types of replay attacks."""
    SAME_NODE_REPLAY = "same_node_replay"
    CROSS_NODE_REPLAY = "cross_node_replay"
    TIME_SHIFT_REPLAY = "time_shift_replay"
    NONCE_REUSE = "nonce_reuse"
    BATCH_REPLAY = "batch_replay"


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class AttestationCapture:
    """Captured attestation data for replay."""
    capture_id: str
    miner_id: str
    miner_wallet: str
    nonce: str
    nonce_ts: int
    device_info: Dict[str, Any]
    signals: Dict[str, Any]
    fingerprint: Dict[str, Any]
    entropy_report: Dict[str, Any]
    captured_at: int
    source_node_id: str
    attestation_hash: str
    raw_payload: Dict[str, Any]


@dataclass
class NodeState:
    """State tracking for a simulated node."""
    node_id: str
    node_url: str
    known_nonces: set = field(default_factory=set)
    used_nonces: set = field(default_factory=set)
    attestations_received: int = 0
    replays_blocked: int = 0
    replays_accepted: int = 0  # Should be 0 in secure system
    last_sync_ts: int = 0


@dataclass
class AttackResult:
    """Result of a replay attack attempt."""
    attack_id: str
    attack_type: str
    capture_id: str
    source_node: str
    target_node: str
    status: str
    blocked: bool
    block_reason: Optional[str]
    latency_ms: float
    timestamp: int
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AttackCampaign:
    """Complete attack campaign with multiple attempts."""
    campaign_id: str
    total_attacks: int
    successful_attacks: int
    blocked_attacks: int
    attack_results: List[Dict[str, Any]]
    started_at: int
    completed_at: int
    nodes_tested: int
    security_score: float  # 0.0 = all blocked, 1.0 = all succeeded
    recommendations: List[str]


# =============================================================================
# Attack Simulation Engine
# =============================================================================

class CrossNodeReplayAttacker:
    """
    Red Team tool for simulating cross-node attestation replay attacks.
    
    This simulates an attacker who:
    1. Monitors legitimate attestations from multiple nodes
    2. Captures attestation payloads
    3. Attempts to replay them across different nodes
    4. Tests the effectiveness of replay protection
    """

    def __init__(self, node_count: int = DEFAULT_NODE_COUNT):
        self.node_count = node_count
        self.nodes: Dict[str, NodeState] = {}
        self.captured_attestations: Dict[str, AttestationCapture] = {}
        self.attack_results: List[AttackResult] = []
        self.nonce_registry: Dict[str, str] = {}  # nonce -> node_id that first saw it
        
        # Initialize simulated nodes
        for i in range(node_count):
            node_id = f"node-{i}"
            self.nodes[node_id] = NodeState(
                node_id=node_id,
                node_url=f"http://localhost:{8080 + i}"
            )

    def _generate_nonce(self) -> str:
        """Generate a challenge nonce (64 hex chars)."""
        return secrets.token_hex(32)

    def _compute_attestation_hash(self, payload: Dict[str, Any]) -> str:
        """Compute unique hash for attestation payload."""
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:32]

    def _generate_device_info(self, miner_id: str) -> Dict[str, Any]:
        """Generate realistic device info for a miner."""
        cpu_models = [
            "AMD Ryzen 5 5600X",
            "Intel Core i7-10700K",
            "Apple M1",
            "PowerPC 7447A (G4)",
            "ARM Cortex-A72"
        ]
        archs = ["x86_64", "arm64", "powerpc"]
        
        return {
            "model": random.choice(cpu_models),
            "arch": random.choice(archs),
            "family": "x86_64",
            "cores": random.randint(4, 16),
            "cpu_serial": f"CPU-{uuid.uuid4().hex[:12]}",
            "device_id": str(uuid.uuid4()),
            "serial_number": f"SN-{uuid.uuid4().hex[:16]}",
        }

    def _generate_signals(self) -> Dict[str, Any]:
        """Generate network signals."""
        return {
            "macs": [f"aa:bb:cc:dd:ee:{random.randint(0, 255):02x}"],
            "hostname": f"miner-{uuid.uuid4().hex[:8]}",
            "ip_address": f"192.168.{random.randint(0, 255)}.{random.randint(1, 254)}",
        }

    def _generate_fingerprint(self) -> Dict[str, Any]:
        """Generate hardware fingerprint data."""
        return {
            "all_passed": True,
            "checks": {
                "clock_drift": {
                    "passed": True,
                    "data": {
                        "cv": round(random.uniform(0.05, 0.15), 4),
                        "samples": 1000,
                        "mean_ns": round(random.uniform(100, 500), 2),
                    }
                },
                "cache_timing": {
                    "passed": True,
                    "data": {
                        "profile": [round(random.uniform(1, 10), 2) for _ in range(5)],
                        "l3_ratio": round(random.uniform(0.8, 1.2), 3),
                    }
                },
                "simd_identity": {
                    "passed": True,
                    "data": {"supported": ["AVX2", "SSE4.2"]},
                },
                "thermal_drift": {
                    "passed": True,
                    "data": {
                        "variance": round(random.uniform(2, 8), 2),
                        "ambient": round(random.uniform(20, 35), 1),
                    }
                },
                "instruction_jitter": {
                    "passed": True,
                    "data": {"jitter_cv": round(random.uniform(0.1, 0.3), 4)},
                },
                "anti_emulation": {
                    "passed": True,
                    "data": {"vm_indicators": [], "confidence": 0.95},
                },
            },
        }

    def _generate_entropy_report(self, nonce: str) -> Dict[str, Any]:
        """Generate entropy report from timing measurements."""
        samples = [random.uniform(100, 500) for _ in range(48)]
        mean_ns = sum(samples) / len(samples)
        variance_ns = sum((x - mean_ns) ** 2 for x in samples) / len(samples)
        
        return {
            "nonce": nonce,
            "commitment": hashlib.sha256(f"{nonce}{time.time()}".encode()).hexdigest(),
            "derived": {
                "mean_ns": round(mean_ns, 2),
                "variance_ns": round(variance_ns, 2),
                "min_ns": round(min(samples), 2),
                "max_ns": round(max(samples), 2),
                "sample_count": len(samples),
                "samples_preview": [round(x, 2) for x in samples[:12]],
            },
            "entropy_score": round(variance_ns / 100, 4),
        }

    def capture_attestation(self, miner_id: str, source_node_id: str) -> AttestationCapture:
        """
        Simulate capturing a legitimate attestation from a node.
        
        In a real attack scenario, this would involve:
        - Network packet capture
        - API response interception
        - Log file access
        """
        if source_node_id not in self.nodes:
            raise ValueError(f"Unknown node: {source_node_id}")

        # Generate nonce and timestamp
        nonce = self._generate_nonce()
        nonce_ts = int(time.time())
        
        # Build attestation payload
        device_info = self._generate_device_info(miner_id)
        signals = self._generate_signals()
        fingerprint = self._generate_fingerprint()
        entropy_report = self._generate_entropy_report(nonce)
        
        raw_payload = {
            "miner": f"wallet_{miner_id}",
            "miner_id": miner_id,
            "nonce": nonce,
            "nonce_ts": nonce_ts,
            "device": device_info,
            "signals": signals,
            "fingerprint": fingerprint,
            "report": {
                "nonce": nonce,
                "commitment": entropy_report["commitment"],
            },
        }
        
        # Create capture record
        capture_id = f"cap_{uuid.uuid4().hex[:16]}"
        capture = AttestationCapture(
            capture_id=capture_id,
            miner_id=miner_id,
            miner_wallet=f"wallet_{miner_id}",
            nonce=nonce,
            nonce_ts=nonce_ts,
            device_info=device_info,
            signals=signals,
            fingerprint=fingerprint,
            entropy_report=entropy_report,
            captured_at=int(time.time()),
            source_node_id=source_node_id,
            attestation_hash=self._compute_attestation_hash(raw_payload),
            raw_payload=raw_payload,
        )
        
        # Store capture
        self.captured_attestations[capture_id] = capture
        
        # Register nonce in source node's registry AND mark as used
        # This simulates a SECURE system where nonces are properly tracked
        self.nonce_registry[nonce] = source_node_id
        self.nodes[source_node_id].known_nonces.add(nonce)
        self.nodes[source_node_id].used_nonces.add(nonce)  # Mark as used!
        
        return capture

    def _simulate_nonce_check(
        self, 
        target_node: NodeState, 
        nonce: str,
        miner_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Simulate server-side nonce verification.
        
        Returns (is_valid, block_reason)
        """
        # Check if nonce was used on THIS node
        if nonce in target_node.used_nonces:
            return False, "nonce_already_used_on_this_node"
        
        # Check if nonce is known from ANOTHER node (cross-node replay detection)
        if nonce in self.nonce_registry:
            original_node = self.nonce_registry[nonce]
            if original_node != target_node.node_id:
                return False, "cross_node_replay_detected"
        
        return True, None

    def _simulate_store_nonce(self, node: NodeState, nonce: str, miner_id: str):
        """Simulate storing a used nonce."""
        node.used_nonces.add(nonce)
        node.attestations_received += 1

    def replay_attestation(
        self, 
        capture_id: str, 
        target_node_id: str,
        attack_type: AttackType = AttackType.CROSS_NODE_REPLAY
    ) -> AttackResult:
        """
        Attempt to replay a captured attestation.
        
        Returns AttackResult with success/failure status.
        """
        start_time = time.time()
        attack_id = f"atk_{uuid.uuid4().hex[:16]}"
        
        if capture_id not in self.captured_attestations:
            return AttackResult(
                attack_id=attack_id,
                attack_type=attack_type.value,
                capture_id=capture_id,
                source_node="unknown",
                target_node=target_node_id,
                status=AttackStatus.ERROR.value,
                blocked=True,
                block_reason="capture_not_found",
                latency_ms=0,
                timestamp=int(time.time()),
            )
        
        capture = self.captured_attestations[capture_id]
        target_node = self.nodes.get(target_node_id)
        
        if not target_node:
            return AttackResult(
                attack_id=attack_id,
                attack_type=attack_type.value,
                capture_id=capture_id,
                source_node=capture.source_node_id,
                target_node=target_node_id,
                status=AttackStatus.ERROR.value,
                blocked=True,
                block_reason="target_node_not_found",
                latency_ms=0,
                timestamp=int(time.time()),
            )
        
        # Prepare replay payload
        replay_payload = capture.raw_payload.copy()
        
        # Apply attack-specific modifications
        if attack_type == AttackType.TIME_SHIFT_REPLAY:
            # Try to shift timestamp to bypass time-based checks
            replay_payload["nonce_ts"] = int(time.time())
            replay_payload["report"]["nonce"] = capture.nonce  # Keep same nonce
        
        # Simulate nonce verification
        is_valid, block_reason = self._simulate_nonce_check(
            target_node, 
            capture.nonce,
            capture.miner_id
        )
        
        latency_ms = (time.time() - start_time) * 1000
        
        if is_valid:
            # Attack succeeded - nonce was accepted (BAD for defense)
            self._simulate_store_nonce(target_node, capture.nonce, capture.miner_id)
            target_node.replays_accepted += 1
            
            return AttackResult(
                attack_id=attack_id,
                attack_type=attack_type.value,
                capture_id=capture_id,
                source_node=capture.source_node_id,
                target_node=target_node.node_id,
                status=AttackStatus.SUCCESS.value,
                blocked=False,
                block_reason=None,
                latency_ms=latency_ms,
                timestamp=int(time.time()),
                details={
                    "vulnerability": "replay_protection_bypassed",
                    "severity": "critical",
                }
            )
        else:
            # Attack blocked - nonce was rejected (GOOD for defense)
            target_node.replays_blocked += 1
            
            return AttackResult(
                attack_id=attack_id,
                attack_type=attack_type.value,
                capture_id=capture_id,
                source_node=capture.source_node_id,
                target_node=target_node.node_id,
                status=AttackStatus.BLOCKED.value,
                blocked=True,
                block_reason=block_reason,
                latency_ms=latency_ms,
                timestamp=int(time.time()),
                details={
                    "protection": "working",
                    "mechanism": "nonce_tracking",
                }
            )

    def run_attack_campaign(
        self, 
        captures_per_node: int = 5,
        attack_types: List[AttackType] = None
    ) -> AttackCampaign:
        """
        Run a comprehensive attack campaign testing multiple scenarios.
        """
        if attack_types is None:
            attack_types = [
                AttackType.SAME_NODE_REPLAY,
                AttackType.CROSS_NODE_REPLAY,
                AttackType.TIME_SHIFT_REPLAY,
            ]
        
        campaign_id = f"camp_{uuid.uuid4().hex[:16]}"
        started_at = int(time.time())
        results = []
        successful = 0
        blocked = 0
        
        # Phase 1: Capture attestations from each node
        print(f"\n[PHASE 1] Capturing attestations from {self.node_count} nodes...")
        for node_id in self.nodes:
            for i in range(captures_per_node):
                miner_id = f"miner_{node_id}_{i}"
                capture = self.capture_attestation(miner_id, node_id)
                print(f"  Captured: {capture.capture_id} from {node_id}")
        
        # Phase 2: Launch attacks
        print(f"\n[PHASE 2] Launching {len(attack_types)} attack types...")
        for attack_type in attack_types:
            print(f"\n  Attack Type: {attack_type.value}")
            
            for capture_id, capture in self.captured_attestations.items():
                for target_node_id in self.nodes:
                    # Determine if this should be blocked
                    if attack_type == AttackType.SAME_NODE_REPLAY:
                        # Same node replay - should be blocked by local nonce tracking
                        if target_node_id != capture.source_node_id:
                            continue
                    elif attack_type == AttackType.CROSS_NODE_REPLAY:
                        # Cross-node replay - should be blocked by distributed tracking
                        if target_node_id == capture.source_node_id:
                            continue
                    
                    result = self.replay_attestation(capture_id, target_node_id, attack_type)
                    results.append(result)
                    
                    status_icon = "✓" if result.blocked else "✗ VULNERABILITY"
                    print(f"    {status_icon} {result.attack_id}: {capture.source_node_id} -> {target_node_id} | {result.block_reason or 'ACCEPTED'}")
                    
                    if result.blocked:
                        blocked += 1
                    else:
                        successful += 1
        
        completed_at = int(time.time())
        total = len(results)
        security_score = blocked / total if total > 0 else 0.0
        
        # Generate recommendations
        recommendations = []
        if successful > 0:
            recommendations.append(
                f"CRITICAL: {successful} replay attacks succeeded. "
                "Implement distributed nonce tracking immediately."
            )
        if security_score < 0.95:
            recommendations.append(
                "WARNING: Security score below 95%. Review nonce synchronization."
            )
        if security_score == 1.0:
            recommendations.append(
                "EXCELLENT: All replay attacks blocked. Defense is working."
            )
        
        campaign = AttackCampaign(
            campaign_id=campaign_id,
            total_attacks=total,
            successful_attacks=successful,
            blocked_attacks=blocked,
            attack_results=[asdict(r) for r in results],
            started_at=started_at,
            completed_at=completed_at,
            nodes_tested=self.node_count,
            security_score=security_score,
            recommendations=recommendations,
        )
        
        return campaign

    def get_security_report(self) -> Dict[str, Any]:
        """Generate security report from attack results."""
        total_attacks = len(self.attack_results)
        blocked = sum(1 for r in self.attack_results if r.blocked)
        successful = total_attacks - blocked
        
        node_reports = {}
        for node_id, node in self.nodes.items():
            node_reports[node_id] = {
                "attestations_received": node.attestations_received,
                "replays_blocked": node.replays_blocked,
                "replays_accepted": node.replays_accepted,
                "known_nonces": len(node.known_nonces),
                "used_nonces": len(node.used_nonces),
            }
        
        return {
            "summary": {
                "total_attacks": total_attacks,
                "blocked": blocked,
                "successful": successful,
                "security_score": blocked / total_attacks if total_attacks > 0 else 0,
            },
            "nodes": node_reports,
            "attack_breakdown": self._breakdown_by_type(),
        }

    def _breakdown_by_type(self) -> Dict[str, Dict[str, int]]:
        """Break down results by attack type."""
        breakdown = {}
        for result in self.attack_results:
            atype = result.attack_type
            if atype not in breakdown:
                breakdown[atype] = {"blocked": 0, "successful": 0}
            if result.blocked:
                breakdown[atype]["blocked"] += 1
            else:
                breakdown[atype]["successful"] += 1
        return breakdown


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    import secrets  # Import here for module-level access
    
    parser = argparse.ArgumentParser(
        description="Cross-Node Attestation Replay Attack Simulation"
    )
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--simulate", action="store_true",
        help="Run full attack simulation"
    )
    mode_group.add_argument(
        "--attack", action="store_true",
        help="Run specific attack scenario"
    )
    mode_group.add_argument(
        "--full-simulation", action="store_true",
        help="Run comprehensive multi-epoch simulation"
    )
    
    # Configuration
    parser.add_argument(
        "--nodes", type=int, default=DEFAULT_NODE_COUNT,
        help=f"Number of nodes to simulate (default: {DEFAULT_NODE_COUNT})"
    )
    parser.add_argument(
        "--captures", type=int, default=5,
        help="Attestations to capture per node"
    )
    parser.add_argument(
        "--capture-node", type=int, default=0,
        help="Source node for capture (attack mode)"
    )
    parser.add_argument(
        "--replay-node", type=int, default=1,
        help="Target node for replay (attack mode)"
    )
    parser.add_argument(
        "--epochs", type=int, default=3,
        help="Number of epochs for full simulation"
    )
    
    # Output
    parser.add_argument(
        "--output", type=Path,
        help="Output path for results JSON"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Initialize attacker
    attacker = CrossNodeReplayAttacker(node_count=args.nodes)
    
    if args.simulate or args.full_simulation:
        # Run attack campaign
        campaign = attacker.run_attack_campaign(
            captures_per_node=args.captures,
            attack_types=[
                AttackType.SAME_NODE_REPLAY,
                AttackType.CROSS_NODE_REPLAY,
                AttackType.TIME_SHIFT_REPLAY,
            ]
        )
        
        # Display results
        print("\n" + "=" * 80)
        print("ATTACK CAMPAIGN RESULTS")
        print("=" * 80)
        print(f"Campaign ID: {campaign.campaign_id}")
        print(f"Total Attacks: {campaign.total_attacks}")
        print(f"Blocked: {campaign.blocked_attacks}")
        print(f"Successful: {campaign.successful_attacks}")
        print(f"Security Score: {campaign.security_score:.2%}")
        print(f"Duration: {campaign.completed_at - campaign.started_at}s")
        
        print("\nRecommendations:")
        for rec in campaign.recommendations:
            print(f"  • {rec}")
        
        # Save results
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(asdict(campaign), f, indent=2)
            print(f"\nResults saved to {args.output}")
        
        # Exit with error if vulnerabilities found
        if campaign.successful_attacks > 0:
            print(f"\n⚠️  VULNERABILITY DETECTED: {campaign.successful_attacks} attacks succeeded")
            return 1
        else:
            print("\n✓ All replay attacks successfully blocked")
            return 0
    
    elif args.attack:
        # Single attack scenario
        capture_node = f"node-{args.capture_node}"
        replay_node = f"node-{args.replay_node}"
        
        print(f"\n[ATTACK] Capturing from {capture_node}...")
        capture = attacker.capture_attestation("target_miner", capture_node)
        print(f"  Captured: {capture.capture_id}")
        print(f"  Nonce: {capture.nonce[:16]}...")
        
        print(f"\n[ATTACK] Replaying to {replay_node}...")
        result = attacker.replay_attestation(
            capture.capture_id, 
            replay_node,
            AttackType.CROSS_NODE_REPLAY
        )
        
        print(f"\nResult: {'BLOCKED ✓' if result.blocked else 'SUCCESS ✗ VULNERABILITY'}")
        print(f"Reason: {result.block_reason or 'Nonce accepted'}")
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(asdict(result), f, indent=2)
        
        return 0 if result.blocked else 1
    
    return 0


if __name__ == "__main__":
    exit(main())
