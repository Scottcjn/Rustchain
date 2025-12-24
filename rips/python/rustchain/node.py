"""
RustChain Node Implementation
=============================

Full node implementation combining all RIPs.

APIs:
- GET /api/stats - Blockchain statistics
- GET /api/node/antiquity - Node AS and eligibility
- POST /api/node/claim - Submit block claim with PoA metadata
- POST /api/mine - Submit mining proof
- POST /api/governance/create - Create proposal
- POST /api/governance/vote - Cast vote
- GET /api/governance/proposals - List proposals
"""

import hashlib
import json
import time
import sqlite3
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from decimal import Decimal
from threading import Lock, Thread
from pathlib import Path

from .core_types import (
    Block,
    BlockMiner,
    Transaction,
    TransactionType,
    WalletAddress,
    HardwareInfo,
    TokenAmount,
    TOTAL_SUPPLY,
    BLOCK_TIME_SECONDS,
    CHAIN_ID,
    PREMINE_AMOUNT,
    FOUNDER_WALLETS,
)
from .proof_of_antiquity import (
    ProofOfAntiquity,
    calculate_antiquity_score,
    AS_MAX,
    AS_MIN,
)
from .deep_entropy import DeepEntropyVerifier, EntropyProof
from .governance import GovernanceEngine, ProposalType, SophiaDecision


# =============================================================================
# Node Configuration
# =============================================================================

@dataclass
class NodeConfig:
    """Node configuration"""
    data_dir: str = "./rustchain_data"
    api_host: str = "0.0.0.0"
    api_port: int = 8085
    mtls_port: int = 4443
    enable_mining: bool = True
    enable_governance: bool = True


# =============================================================================
# RustChain Node
# =============================================================================

class RustChainNode:
    """
    Full RustChain node implementing Proof of Antiquity.

    This node:
    - Validates hardware via deep entropy
    - Calculates Antiquity Scores
    - Processes blocks via weighted lottery
    - Manages governance proposals
    - Tracks wallets and balances
    """

    def __init__(self, config: Optional[NodeConfig] = None):
        self.config = config or NodeConfig()
        self.lock = Lock()

        # Initialize components
        self.poa = ProofOfAntiquity()
        self.entropy_verifier = DeepEntropyVerifier()
        self.governance = GovernanceEngine(TOTAL_SUPPLY)

        # Blockchain state
        self.blocks: List[Block] = []
        self.wallets: Dict[str, TokenAmount] = {}
        self.pending_transactions: List[Transaction] = []

        # Network state
        self.total_minted = TokenAmount.from_rtc(float(PREMINE_AMOUNT))
        self.mining_pool = TokenAmount.from_rtc(
            float(TOTAL_SUPPLY - PREMINE_AMOUNT)
        )

        # Initialize genesis
        self._initialize_genesis()

        # Background block processor
        self.running = False

    def _initialize_genesis(self):
        """Initialize genesis block and founder wallets"""
        # Create genesis block
        genesis = Block(
            height=0,
            timestamp=int(time.time()),
            previous_hash="0" * 64,
            miners=[],
            total_reward=TokenAmount(0),
        )
        genesis.hash = "019c177b44a41f78da23caa99314adbc44889be2dcdd5021930f9d991e7e34cf"
        self.blocks.append(genesis)

        # Initialize founder wallets (RIP-0004: 4 x 125,829.12 RTC)
        founder_amount = TokenAmount.from_rtc(125829.12)
        for wallet_addr in FOUNDER_WALLETS:
            self.wallets[wallet_addr] = founder_amount

        print(f"🔥 RustChain Genesis initialized")
        print(f"   Chain ID: {CHAIN_ID}")
        print(f"   Total Supply: {TOTAL_SUPPLY:,} RTC")
        print(f"   Mining Pool: {self.mining_pool.to_rtc():,.2f} RTC")
        print(f"   Founder Wallets: {len(FOUNDER_WALLETS)}")

    def start(self):
        """Start the node"""
        self.running = True
        print(f"🚀 RustChain node starting...")
        print(f"   API: http://{self.config.api_host}:{self.config.api_port}")
        print(f"   mTLS: port {self.config.mtls_port}")

        # Start block processor thread
        self.block_thread = Thread(target=self._block_processor, daemon=True)
        self.block_thread.start()

    def stop(self):
        """Stop the node"""
        self.running = False
        print("🛑 RustChain node stopped")

    def _block_processor(self):
        """Background block processor"""
        while self.running:
            time.sleep(10)  # Check every 10 seconds

            with self.lock:
                status = self.poa.get_status()
                if status["time_remaining_seconds"] <= 0:
                    self._process_block()

    def _process_block(self):
        """Process pending proofs and create new block"""
        previous_hash = self.blocks[-1].hash if self.blocks else "0" * 64
        block = self.poa.process_block(previous_hash)

        if block:
            self.blocks.append(block)

            # Update wallet balances
            for miner in block.miners:
                wallet_addr = miner.wallet.address
                if wallet_addr not in self.wallets:
                    self.wallets[wallet_addr] = TokenAmount(0)
                self.wallets[wallet_addr] += miner.reward

            # Update totals
            self.total_minted += block.total_reward
            self.mining_pool -= block.total_reward

            print(f"⛏️  Block #{block.height} processed")

    # =========================================================================
    # API Methods
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """GET /api/stats - Get blockchain statistics"""
        with self.lock:
            return {
                "chain_id": CHAIN_ID,
                "blocks": len(self.blocks),
                "total_minted": float(self.total_minted.to_rtc()),
                "mining_pool": float(self.mining_pool.to_rtc()),
                "wallets": len(self.wallets),
                "pending_proofs": self.poa.get_status()["pending_proofs"],
                "current_block_age": self.poa.get_status()["block_age_seconds"],
                "next_block_in": self.poa.get_status()["time_remaining_seconds"],
                "latest_block": self.blocks[-1].to_dict() if self.blocks else None,
            }

    def get_node_antiquity(
        self, wallet: WalletAddress, hardware: HardwareInfo
    ) -> Dict[str, Any]:
        """GET /api/node/antiquity - Get node AS and eligibility"""
        as_score = calculate_antiquity_score(
            hardware.release_year,
            hardware.uptime_days
        )

        eligible = as_score >= AS_MIN

        return {
            "wallet": wallet.address,
            "hardware": hardware.to_dict(),
            "antiquity_score": as_score,
            "as_max": AS_MAX,
            "eligible": eligible,
            "eligibility_reason": (
                "Meets minimum AS threshold"
                if eligible
                else f"AS {as_score:.2f} below minimum {AS_MIN}"
            ),
        }

    def submit_mining_proof(
        self,
        wallet: WalletAddress,
        hardware: HardwareInfo,
        entropy_proof: Optional[EntropyProof] = None,
    ) -> Dict[str, Any]:
        """POST /api/mine - Submit mining proof"""
        with self.lock:
            # Verify entropy if provided
            anti_emulation_hash = "0" * 64
            if entropy_proof:
                result = self.entropy_verifier.verify(
                    entropy_proof,
                    self._detect_hardware_profile(hardware)
                )
                if not result.valid:
                    return {
                        "success": False,
                        "error": f"Entropy verification failed: {result.issues}",
                        "emulation_probability": result.emulation_probability,
                    }
                anti_emulation_hash = entropy_proof.signature_hash

            # Submit to PoA
            try:
                return self.poa.submit_proof(
                    wallet=wallet,
                    hardware=hardware,
                    anti_emulation_hash=anti_emulation_hash,
                )
            except Exception as e:
                return {"success": False, "error": str(e)}

    def _detect_hardware_profile(self, hardware: HardwareInfo) -> str:
        """Detect hardware profile from HardwareInfo"""
        model = hardware.cpu_model.lower()
        if "486" in model:
            return "486DX2"
        elif "pentium ii" in model or "pentium 2" in model:
            return "PentiumII"
        elif "pentium" in model:
            return "Pentium"
        elif "g4" in model or "powerpc g4" in model:
            return "G4"
        elif "g5" in model or "powerpc g5" in model:
            return "G5"
        elif "alpha" in model:
            return "Alpha"
        return "Unknown"

    def get_wallet(self, address: str) -> Dict[str, Any]:
        """GET /api/wallet/:address - Get wallet details"""
        with self.lock:
            balance = self.wallets.get(address, TokenAmount(0))
            is_founder = address in FOUNDER_WALLETS

            return {
                "address": address,
                "balance": float(balance.to_rtc()),
                "is_founder": is_founder,
            }

    def get_block(self, height: int) -> Optional[Dict[str, Any]]:
        """GET /api/block/:height - Get block by height"""
        with self.lock:
            if 0 <= height < len(self.blocks):
                return self.blocks[height].to_dict()
            return None

    def create_proposal(
        self,
        title: str,
        description: str,
        proposal_type: str,
        proposer: WalletAddress,
        contract_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /api/governance/create - Create proposal"""
        ptype = ProposalType[proposal_type.upper()]
        proposal = self.governance.create_proposal(
            title=title,
            description=description,
            proposal_type=ptype,
            proposer=proposer,
            contract_hash=contract_hash,
        )
        return proposal.to_dict()

    def sophia_analyze(
        self,
        proposal_id: str,
        decision: str,
        rationale: str,
    ) -> Dict[str, Any]:
        """POST /api/governance/sophia/analyze - Sophia evaluation"""
        sophia_decision = SophiaDecision[decision.upper()]
        evaluation = self.governance.sophia_evaluate(
            proposal_id=proposal_id,
            decision=sophia_decision,
            rationale=rationale,
        )
        proposal = self.governance.get_proposal(proposal_id)
        return proposal.to_dict() if proposal else {}

    def vote_proposal(
        self,
        proposal_id: str,
        voter: WalletAddress,
        support: bool,
    ) -> Dict[str, Any]:
        """POST /api/governance/vote - Cast vote"""
        with self.lock:
            balance = self.wallets.get(voter.address, TokenAmount(0))
            vote = self.governance.vote(
                proposal_id=proposal_id,
                voter=voter,
                support=support,
                token_balance=balance.to_rtc(),
            )
            proposal = self.governance.get_proposal(proposal_id)
            return {
                "success": True,
                "vote_weight": str(vote.weight),
                "proposal": proposal.to_dict() if proposal else {},
            }

    def get_proposals(self) -> List[Dict[str, Any]]:
        """GET /api/governance/proposals - List proposals"""
        return [p.to_dict() for p in self.governance.get_all_proposals()]


# =============================================================================
# Flask API Server
# =============================================================================

def create_api_server(node: RustChainNode):
    """Create Flask API server for the node"""
    try:
        from flask import Flask, jsonify, request
        from flask_cors import CORS
    except ImportError:
        print("Flask not installed. Run: pip install flask flask-cors")
        return None

    app = Flask(__name__)
    CORS(app)

    @app.route("/api/stats")
    def stats():
        return jsonify(node.get_stats())

    @app.route("/api/wallet/<address>")
    def wallet(address):
        return jsonify(node.get_wallet(address))

    @app.route("/api/block/<int:height>")
    def block(height):
        result = node.get_block(height)
        if result:
            return jsonify(result)
        return jsonify({"error": "Block not found"}), 404

    @app.route("/api/mine", methods=["POST"])
    def mine():
        data = request.json
        wallet = WalletAddress(data["wallet"])
        hardware = HardwareInfo(
            cpu_model=data["hardware"],
            release_year=data.get("release_year", 2000),
            uptime_days=data.get("uptime_days", 0),
        )
        result = node.submit_mining_proof(wallet, hardware)
        return jsonify(result)

    @app.route("/api/node/antiquity", methods=["POST"])
    def antiquity():
        data = request.json
        wallet = WalletAddress(data["wallet"])
        hardware = HardwareInfo(
            cpu_model=data["hardware"],
            release_year=data.get("release_year", 2000),
            uptime_days=data.get("uptime_days", 0),
        )
        return jsonify(node.get_node_antiquity(wallet, hardware))

    @app.route("/api/governance/proposals")
    def proposals():
        return jsonify(node.get_proposals())

    @app.route("/api/governance/create", methods=["POST"])
    def create_proposal():
        data = request.json
        result = node.create_proposal(
            title=data["title"],
            description=data["description"],
            proposal_type=data["type"],
            proposer=WalletAddress(data["proposer"]),
            contract_hash=data.get("contract_hash"),
        )
        return jsonify(result)

    @app.route("/api/governance/vote", methods=["POST"])
    def vote():
        data = request.json
        result = node.vote_proposal(
            proposal_id=data["proposal_id"],
            voter=WalletAddress(data["voter"]),
            support=data["support"],
        )
        return jsonify(result)

    return app


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("RUSTCHAIN NODE - PROOF OF ANTIQUITY")
    print("=" * 60)
    print()
    print("Philosophy: Every vintage computer has historical potential")
    print()

    # Create and start node
    config = NodeConfig()
    node = RustChainNode(config)
    node.start()

    # Create API server
    app = create_api_server(node)
    if app:
        print()
        print("Starting API server...")
        app.run(
            host=config.api_host,
            port=config.api_port,
            debug=False,
            threaded=True,
        )
