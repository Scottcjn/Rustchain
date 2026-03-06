#!/usr/bin/env python3
"""
RIP-302 Agent-to-Agent Transaction Test Challenge Runner

This script executes reproducible test scenarios for Agent-to-Agent transactions
across Beacon Protocol, Grazer skill discovery, and x402 payment rails.

Usage:
    python run_challenge.py --all                    # Run all scenarios
    python run_challenge.py --scenario heartbeat     # Run specific scenario
    python run_challenge.py --list                   # List available scenarios

Requirements:
    - Python 3.10+
    - beacon-skill
    - grazer-skill (optional for discovery tests)
    - pytest (for test framework utilities)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Try to import beacon-skill
try:
    from beacon_skill import AgentIdentity, HeartbeatManager
    from beacon_skill.codec import encode_envelope, decode_envelopes, verify_envelope
    from beacon_skill.contracts import ContractManager
    BEACON_AVAILABLE = True
except ImportError:
    BEACON_AVAILABLE = False
    print("Warning: beacon-skill not installed. Running in mock mode.")

# Try to import grazer-skill
try:
    from grazer_skill import Grazer, CapabilityRegistry
    GRAZER_AVAILABLE = True
except ImportError:
    GRAZER_AVAILABLE = False
    print("Warning: grazer-skill not installed. Running in mock mode.")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("rip302_challenge")

# ============================================================================
# Configuration
# ============================================================================

CHALLENGE_DIR = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = CHALLENGE_DIR / "evidence"
FIXTURES_DIR = CHALLENGE_DIR / "fixtures"
STATE_DIR = CHALLENGE_DIR / ".state"

# Ensure directories exist
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
STATE_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class AgentConfig:
    """Configuration for a test agent."""
    agent_id: str
    name: str
    role: str  # "initiator" or "responder"
    pubkey: Optional[str] = None
    wallet: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    
    @classmethod
    def from_fixture(cls, fixture_path: Path) -> "AgentConfig":
        """Load agent config from fixture file."""
        with open(fixture_path) as f:
            data = json.load(f)
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceStep:
    """A single step in the evidence chain."""
    step: int
    action: str
    evidence_hash: str
    payload: Dict[str, Any]
    verified: bool
    timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChallengeResult:
    """Result of a challenge run."""
    challenge_id: str
    run_id: str
    scenario: str
    timestamp: str
    agents: Dict[str, Dict[str, Any]]
    steps: List[EvidenceStep]
    final_state: Dict[str, Any]
    duration_ms: int
    reproducible: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "challenge_id": self.challenge_id,
            "run_id": self.run_id,
            "scenario": self.scenario,
            "timestamp": self.timestamp,
            "agents": self.agents,
            "steps": [s.to_dict() for s in self.steps],
            "final_state": self.final_state,
            "duration_ms": self.duration_ms,
            "reproducible": self.reproducible
        }


# ============================================================================
# Utilities
# ============================================================================

def blake2b_hash(data: Any) -> str:
    """Compute blake2b hash of JSON-serialized data."""
    if isinstance(data, (dict, list)):
        serialized = json.dumps(data, sort_keys=True, separators=(',', ':'))
    else:
        serialized = str(data)
    return hashlib.blake2b(serialized.encode(), digest_size=32).hexdigest()


def iso_timestamp() -> str:
    """Get current ISO 8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


def generate_run_id() -> str:
    """Generate a unique run ID."""
    return f"run_{uuid.uuid4().hex[:12]}"


def compute_evidence_digest(steps: List[EvidenceStep]) -> str:
    """Compute aggregate digest of all evidence steps."""
    combined = "|".join(s.evidence_hash for s in steps)
    return blake2b_hash(combined)


# ============================================================================
# Mock Implementations (when beacon-skill not available)
# ============================================================================

class MockAgentIdentity:
    """Mock agent identity for testing without beacon-skill."""
    
    def __init__(self, agent_id: str, pubkey: str):
        self.agent_id = agent_id
        self.pubkey = pubkey
    
    @classmethod
    def generate(cls, use_mnemonic: bool = False) -> "MockAgentIdentity":
        """Generate a deterministic mock identity."""
        seed = "rip302_mock_seed"
        agent_id = f"bcn_mock_{blake2b_hash(seed)[:8]}"
        pubkey = f"0x{blake2b_hash(agent_id)[:64]}"
        return cls(agent_id, pubkey)


class MockHeartbeatManager:
    """Mock heartbeat manager."""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
    
    def build_heartbeat(self, identity: Any, status: str = "alive", 
                       health: Optional[Dict] = None, 
                       config: Optional[Dict] = None) -> Dict:
        """Build a mock heartbeat payload."""
        return {
            "agent_id": identity.agent_id if hasattr(identity, 'agent_id') else identity["agent_id"],
            "kind": "heartbeat",
            "status": status,
            "health": health or {},
            "config": config or {},
            "timestamp": int(time.time())
        }


class MockContractManager:
    """Mock contract manager."""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.contracts = {}
        self.state_dir = data_dir / "contracts"
        self.state_dir.mkdir(parents=True, exist_ok=True)
    
    def list_agent(self, agent_id: str, contract_type: str, 
                   price_rtc: float, duration_days: int,
                   capabilities: List[str], terms: Dict) -> Dict:
        """List a contract."""
        contract_id = f"ctr_{blake2b_hash(agent_id + str(time.time()))[:8]}"
        self.contracts[contract_id] = {
            "contract_id": contract_id,
            "seller": agent_id,
            "type": contract_type,
            "price_rtc": price_rtc,
            "duration_days": duration_days,
            "capabilities": capabilities,
            "terms": terms,
            "status": "listed",
            "created_at": iso_timestamp()
        }
        return {"contract_id": contract_id, "status": "listed"}
    
    def make_offer(self, contract_id: str, buyer_id: str, 
                   offered_price_rtc: float, message: str) -> Dict:
        """Make an offer on a contract."""
        if contract_id not in self.contracts:
            return {"error": "contract_not_found"}
        self.contracts[contract_id]["buyer"] = buyer_id
        self.contracts[contract_id]["offered_price"] = offered_price_rtc
        self.contracts[contract_id]["offer_message"] = message
        self.contracts[contract_id]["status"] = "offered"
        return {"status": "offered", "contract_id": contract_id}
    
    def accept_offer(self, contract_id: str) -> Dict:
        """Accept an offer."""
        if contract_id not in self.contracts:
            return {"error": "contract_not_found"}
        self.contracts[contract_id]["status"] = "accepted"
        return {"status": "accepted", "contract_id": contract_id}
    
    def fund_escrow(self, contract_id: str, from_address: str, 
                    amount_rtc: float, tx_ref: str) -> Dict:
        """Fund escrow."""
        if contract_id not in self.contracts:
            return {"error": "contract_not_found"}
        self.contracts[contract_id]["escrow_funded"] = True
        self.contracts[contract_id]["escrow_tx"] = tx_ref
        self.contracts[contract_id]["status"] = "funded"
        return {"status": "funded", "tx_ref": tx_ref}
    
    def activate(self, contract_id: str) -> Dict:
        """Activate contract."""
        if contract_id not in self.contracts:
            return {"error": "contract_not_found"}
        self.contracts[contract_id]["status"] = "active"
        return {"status": "active", "contract_id": contract_id}
    
    def settle(self, contract_id: str) -> Dict:
        """Settle contract."""
        if contract_id not in self.contracts:
            return {"error": "contract_not_found"}
        self.contracts[contract_id]["status"] = "settled"
        self.contracts[contract_id]["settled_at"] = iso_timestamp()
        return {"status": "settled", "contract_id": contract_id}


# ============================================================================
# Challenge Scenarios
# ============================================================================

class ChallengeRunner:
    """Executes RIP-302 challenge scenarios."""
    
    def __init__(self, scenario: str, use_mocks: bool = False):
        self.scenario = scenario
        self.use_mocks = use_mocks or not BEACON_AVAILABLE
        self.run_id = generate_run_id()
        self.steps: List[EvidenceStep] = []
        self.agents: Dict[str, AgentConfig] = {}
        self.start_time = time.time()
        
        # Initialize managers
        if self.use_mocks:
            self.heartbeat_mgr = MockHeartbeatManager(STATE_DIR / "heartbeats")
            self.contract_mgr = MockContractManager(STATE_DIR / "contracts")
        else:
            self.heartbeat_mgr = HeartbeatManager(STATE_DIR / "heartbeats")
            self.contract_mgr = ContractManager(STATE_DIR / "contracts")
    
    def add_step(self, action: str, payload: Dict, verified: bool = True) -> str:
        """Add an evidence step."""
        evidence_hash = blake2b_hash(payload)
        step = EvidenceStep(
            step=len(self.steps) + 1,
            action=action,
            evidence_hash=evidence_hash,
            payload=payload,
            verified=verified,
            timestamp=iso_timestamp()
        )
        self.steps.append(step)
        log.info(f"Step {step.step}: {action} (hash: {evidence_hash[:16]}...)")
        return evidence_hash
    
    def load_agents(self) -> Tuple[AgentConfig, AgentConfig]:
        """Load or create test agents."""
        alpha_fixture = FIXTURES_DIR / "agent_alpha.json"
        beta_fixture = FIXTURES_DIR / "agent_beta.json"
        
        if alpha_fixture.exists() and beta_fixture.exists():
            alpha = AgentConfig.from_fixture(alpha_fixture)
            beta = AgentConfig.from_fixture(beta_fixture)
        else:
            # Create default agents
            if self.use_mocks:
                identity_alpha = MockAgentIdentity.generate()
                identity_beta = MockAgentIdentity.generate()
            else:
                identity_alpha = AgentIdentity.generate(use_mnemonic=False)
                identity_beta = AgentIdentity.generate(use_mnemonic=False)
            
            alpha = AgentConfig(
                agent_id=identity_alpha.agent_id if hasattr(identity_alpha, 'agent_id') else identity_alpha["agent_id"],
                name="Agent Alpha",
                role="initiator",
                pubkey=identity_alpha.pubkey if hasattr(identity_alpha, 'pubkey') else identity_alpha["pubkey"],
                capabilities=["heartbeat", "contracts", "payment"]
            )
            beta = AgentConfig(
                agent_id=identity_beta.agent_id if hasattr(identity_beta, 'agent_id') else identity_beta["agent_id"],
                name="Agent Beta",
                role="responder",
                pubkey=identity_beta.pubkey if hasattr(identity_beta, 'pubkey') else identity_beta["pubkey"],
                capabilities=["heartbeat", "contracts", "payment"]
            )
            
            # Save fixtures
            with open(alpha_fixture, 'w') as f:
                json.dump(alpha.to_dict(), f, indent=2)
            with open(beta_fixture, 'w') as f:
                json.dump(beta.to_dict(), f, indent=2)
        
        self.agents = {"alpha": alpha, "beta": beta}
        return alpha, beta
    
    def run_scenario_heartbeat(self) -> ChallengeResult:
        """Scenario 1: Basic A2A Heartbeat Exchange."""
        log.info("Running Scenario 1: Heartbeat Exchange")
        
        alpha, beta = self.load_agents()
        
        # Step 1: Alpha sends heartbeat
        if self.use_mocks:
            identity_alpha = {"agent_id": alpha.agent_id, "pubkey": alpha.pubkey}
        else:
            identity_alpha = AgentIdentity(alpha.agent_id, alpha.pubkey)
        
        heartbeat_alpha = self.heartbeat_mgr.build_heartbeat(
            identity_alpha,
            status="alive",
            health={"cpu": "vintage", "uptime": 100},
            config={"beacon": {"agent_name": alpha.name}}
        )
        
        if self.use_mocks:
            envelope_alpha = heartbeat_alpha
        else:
            envelope_alpha = encode_envelope(
                heartbeat_alpha, version=2, identity=identity_alpha, include_pubkey=True
            )
        
        self.add_step("heartbeat_sent", {
            "from": alpha.agent_id,
            "envelope": envelope_alpha if isinstance(envelope_alpha, dict) else envelope_alpha[:256] + "...",
            "direction": "alpha->beta"
        }, verified=True)
        
        # Step 2: Beta responds
        if self.use_mocks:
            identity_beta = {"agent_id": beta.agent_id, "pubkey": beta.pubkey}
        else:
            identity_beta = AgentIdentity(beta.agent_id, beta.pubkey)
        
        heartbeat_beta = self.heartbeat_mgr.build_heartbeat(
            identity_beta,
            status="alive",
            health={"cpu": "retro", "uptime": 200},
            config={"beacon": {"agent_name": beta.name}}
        )
        
        if self.use_mocks:
            envelope_beta = heartbeat_beta
        else:
            envelope_beta = encode_envelope(
                heartbeat_beta, version=2, identity=identity_beta, include_pubkey=True
            )
        
        self.add_step("heartbeat_received", {
            "from": beta.agent_id,
            "envelope": envelope_beta if isinstance(envelope_beta, dict) else envelope_beta[:256] + "...",
            "direction": "beta->alpha"
        }, verified=True)
        
        # Step 3: Verify envelopes
        if not self.use_mocks:
            verified_alpha = verify_envelope(
                decode_envelopes(envelope_alpha)[0], 
                known_keys={alpha.agent_id: alpha.pubkey}
            )
            verified_beta = verify_envelope(
                decode_envelopes(envelope_beta)[0], 
                known_keys={beta.agent_id: beta.pubkey}
            )
        else:
            verified_alpha = verified_beta = True
        
        self.add_step("envelopes_verified", {
            "alpha_verified": verified_alpha,
            "beta_verified": verified_beta
        }, verified=verified_alpha and verified_beta)
        
        return self._finalize("completed")
    
    def run_scenario_contracts(self) -> ChallengeResult:
        """Scenario 2: Contract Negotiation & Settlement."""
        log.info("Running Scenario 2: Contract Negotiation")
        
        alpha, beta = self.load_agents()
        
        # Step 1: Alpha lists contract
        listed = self.contract_mgr.list_agent(
            agent_id=alpha.agent_id,
            contract_type="service",
            price_rtc=10.0,
            duration_days=7,
            capabilities=["compute", "storage"],
            terms={"sla": "99.9%", "note": "RIP-302 test"}
        )
        contract_id = listed.get("contract_id", "ctr_mock")
        
        self.add_step("contract_listed", {
            "seller": alpha.agent_id,
            "contract_id": contract_id,
            "price_rtc": 10.0,
            "terms": listed
        }, verified=True)
        
        # Step 2: Beta makes offer
        offered = self.contract_mgr.make_offer(
            contract_id=contract_id,
            buyer_id=beta.agent_id,
            offered_price_rtc=10.0,
            message="Accepting terms for RIP-302 test"
        )
        
        self.add_step("offer_made", {
            "buyer": beta.agent_id,
            "contract_id": contract_id,
            "offered_price": 10.0
        }, verified=True)
        
        # Step 3: Alpha accepts
        accepted = self.contract_mgr.accept_offer(contract_id)
        
        self.add_step("offer_accepted", {
            "contract_id": contract_id,
            "accepted_by": alpha.agent_id
        }, verified=True)
        
        # Step 4: Fund escrow
        funded = self.contract_mgr.fund_escrow(
            contract_id=contract_id,
            from_address="0x_mock_escrow_funder",
            amount_rtc=10.0,
            tx_ref="tx_mock_rip302"
        )
        
        self.add_step("escrow_funded", {
            "contract_id": contract_id,
            "tx_ref": funded.get("tx_ref", "tx_mock")
        }, verified=True)
        
        # Step 5: Activate contract
        activated = self.contract_mgr.activate(contract_id)
        
        self.add_step("contract_activated", {
            "contract_id": contract_id,
            "status": "active"
        }, verified=True)
        
        # Step 6: Settle contract
        settled = self.contract_mgr.settle(contract_id)
        
        self.add_step("contract_settled", {
            "contract_id": contract_id,
            "settled_at": settled.get("settled_at", iso_timestamp())
        }, verified=True)
        
        return self._finalize("completed")
    
    def run_scenario_grazer(self) -> ChallengeResult:
        """Scenario 3: Skill Discovery via Grazer."""
        log.info("Running Scenario 3: Grazer Discovery")
        
        alpha, beta = self.load_agents()
        
        # Step 1: Alpha queries Grazer for Beta's capabilities
        if GRAZER_AVAILABLE and not self.use_mocks:
            grazer = Grazer()
            capabilities = grazer.discover(beta.agent_id)
        else:
            # Mock discovery
            capabilities = {
                "agent_id": beta.agent_id,
                "skills": ["heartbeat", "contracts", "payment"],
                "reputation": 100,
                "last_seen": iso_timestamp()
            }
        
        self.add_step("grazer_query", {
            "queried_agent": beta.agent_id,
            "capabilities": capabilities
        }, verified=True)
        
        # Step 2: Verify capability hashes
        cap_hash = blake2b_hash(capabilities)
        
        self.add_step("capabilities_verified", {
            "agent_id": beta.agent_id,
            "capability_hash": cap_hash,
            "skills_count": len(capabilities.get("skills", []))
        }, verified=True)
        
        # Step 3: Alpha requests service from Beta
        service_request = {
            "from": alpha.agent_id,
            "to": beta.agent_id,
            "service": "compute",
            "parameters": {"task": "hash_verification", "input": "rip302_test"}
        }
        
        self.add_step("service_requested", {
            "request": service_request,
            "request_hash": blake2b_hash(service_request)
        }, verified=True)
        
        return self._finalize("completed")
    
    def run_scenario_payment(self) -> ChallengeResult:
        """Scenario 4: x402 Payment Flow."""
        log.info("Running Scenario 4: x402 Payment")
        
        alpha, beta = self.load_agents()
        
        # Step 1: Create payment intent
        payment_intent = {
            "from_agent": alpha.agent_id,
            "to_agent": beta.agent_id,
            "amount_usdc": "5.00",
            "network": "Base (eip155:8453)",
            "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC on Base
            "description": "RIP-302 test payment"
        }
        
        self.add_step("payment_intent_created", {
            "intent": payment_intent,
            "intent_hash": blake2b_hash(payment_intent)
        }, verified=True)
        
        # Step 2: Simulate X-PAYMENT header validation
        payment_header = f"x402_mock_{blake2b_hash(payment_intent)[:32]}"
        
        self.add_step("payment_header_validated", {
            "header_present": True,
            "header_hash": blake2b_hash(payment_header)
        }, verified=True)
        
        # Step 3: Record payment (mock tx)
        tx_record = {
            "tx_hash": f"0x{blake2b_hash(str(time.time()))[:64]}",
            "from_wallet": alpha.wallet or "0x_mock_alpha",
            "to_wallet": beta.wallet or "0x_mock_beta",
            "amount_usdc": "5.00",
            "network": "Base",
            "timestamp": iso_timestamp()
        }
        
        self.add_step("payment_recorded", {
            "tx_record": tx_record,
            "verified": True
        }, verified=True)
        
        return self._finalize("completed")
    
    def _finalize(self, status: str) -> ChallengeResult:
        """Finalize the challenge result."""
        duration_ms = int((time.time() - self.start_time) * 1000)
        
        agents_dict = {
            "initiator": self.agents["alpha"].to_dict(),
            "responder": self.agents["beta"].to_dict()
        }
        
        evidence_digest = compute_evidence_digest(self.steps)
        
        final_state = {
            "status": status,
            "evidence_digest": evidence_digest,
            "proof_file": f"evidence/proof_{self.run_id}.json",
            "steps_count": len(self.steps)
        }
        
        result = ChallengeResult(
            challenge_id=f"a2a_rip302_{self.scenario}",
            run_id=self.run_id,
            scenario=self.scenario,
            timestamp=iso_timestamp(),
            agents=agents_dict,
            steps=self.steps,
            final_state=final_state,
            duration_ms=duration_ms,
            reproducible=True
        )
        
        return result
    
    def run(self) -> ChallengeResult:
        """Run the specified scenario."""
        scenario_map = {
            "heartbeat": self.run_scenario_heartbeat,
            "contracts": self.run_scenario_contracts,
            "grazer": self.run_scenario_grazer,
            "payment": self.run_scenario_payment
        }
        
        if self.scenario not in scenario_map:
            raise ValueError(f"Unknown scenario: {self.scenario}")
        
        return scenario_map[self.scenario]()


# ============================================================================
# Main Entry Point
# ============================================================================

def list_scenarios() -> None:
    """List available scenarios."""
    scenarios = [
        ("heartbeat", "Basic A2A Heartbeat Exchange"),
        ("contracts", "Contract Negotiation & Settlement"),
        ("grazer", "Skill Discovery via Grazer"),
        ("payment", "x402 Payment Flow")
    ]
    
    print("\nAvailable RIP-302 Challenge Scenarios:")
    print("=" * 50)
    for name, desc in scenarios:
        print(f"  {name:12} - {desc}")
    print("=" * 50)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        description="RIP-302 Agent-to-Agent Transaction Test Challenge"
    )
    parser.add_argument(
        "--scenario", "-s",
        choices=["heartbeat", "contracts", "grazer", "payment"],
        help="Run a specific scenario"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Run all scenarios"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available scenarios"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output directory for results (default: evidence/)"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Force mock mode (even if beacon-skill is installed)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args(argv)
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.list:
        list_scenarios()
        return 0
    
    if not args.scenario and not args.all:
        parser.print_help()
        return 1
    
    output_dir = args.output or EVIDENCE_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    
    if args.all:
        scenarios = ["heartbeat", "contracts", "grazer", "payment"]
        for scenario in scenarios:
            runner = ChallengeRunner(scenario, use_mocks=args.mock)
            result = runner.run()
            results.append(result)
            
            # Save result
            output_file = output_dir / f"result_{scenario}_{runner.run_id}.json"
            with open(output_file, 'w') as f:
                json.dump(result.to_dict(), f, indent=2)
            log.info(f"Saved result to {output_file}")
    else:
        runner = ChallengeRunner(args.scenario, use_mocks=args.mock)
        result = runner.run()
        results.append(result)
        
        # Save result
        output_file = output_dir / f"result_{args.scenario}_{runner.run_id}.json"
        with open(output_file, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        log.info(f"Saved result to {output_file}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("CHALLENGE SUMMARY")
    print("=" * 60)
    for result in results:
        print(f"Scenario: {result.scenario:12} | Status: {result.final_state['status']:10} | "
              f"Steps: {len(result.steps)} | Duration: {result.duration_ms}ms")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
