#!/usr/bin/env python3
"""
RustChain Node - Proof of Antiquity Blockchain
==============================================

"Every vintage computer has historical potential"
- Flamekeeper Scott

This is NOT Proof of Work! RustChain rewards:
- Hardware age (older = better)
- Node uptime (longer = better)
- Hardware authenticity (verified via deep entropy)

Usage:
    python -m rustchain-core.main [options]

Options:
    --port PORT       API port (default: 8085)
    --data-dir DIR    Data directory (default: ./rustchain_data)
    --mining          Enable mining
    --validator-id ID Custom validator ID
"""

import argparse
import signal
import sys
import time
import threading
from pathlib import Path

# Local imports
from config.chain_params import (
    CHAIN_ID,
    TOTAL_SUPPLY,
    BLOCK_TIME_SECONDS,
    DEFAULT_PORT,
    PROTOCOL_VERSION,
    FOUNDER_WALLETS,
    PREMINE_AMOUNT,
)
from consensus.poa import ProofOfAntiquity, HardwareProof, compute_antiquity_score
from ledger.utxo_ledger import UtxoSet, Transaction, BalanceTracker
from validator.score import HardwareValidator, HardwareInfo
from validator.entropy import EntropyProfileBuilder, derive_validator_id
from governance.proposals import GovernanceEngine, ProposalType, SophiaDecision
from networking.p2p import NetworkManager, PeerId
from api.rpc import RustChainApi, ApiServer


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

    VERSION = "0.1.0"

    def __init__(
        self,
        data_dir: str = "./rustchain_data",
        api_port: int = DEFAULT_PORT,
        enable_mining: bool = True,
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.chain_id = CHAIN_ID
        self.version = self.VERSION
        self.api_port = api_port
        self.is_mining = enable_mining

        # Generate validator ID from entropy
        print("Collecting entropy fingerprint...")
        self.validator_id = derive_validator_id()
        print(f"Validator ID: {self.validator_id[:32]}...")

        # Initialize components
        self.poa = ProofOfAntiquity()
        self.utxo_set = UtxoSet()
        self.balance_tracker = BalanceTracker(self.utxo_set)
        self.hardware_validator = HardwareValidator()
        self.governance = GovernanceEngine(TOTAL_SUPPLY)

        # Network
        self.network = NetworkManager(
            listen_port=api_port + 1,
            chain_id=CHAIN_ID,
            validator_id=self.validator_id,
        )

        # State
        self._start_time = time.time()
        self._running = False
        self._block_thread = None

        # Initialize genesis
        self._initialize_genesis()

    def _initialize_genesis(self):
        """Initialize genesis block and founder wallets"""
        print()
        print("=" * 60)
        print("RUSTCHAIN - PROOF OF ANTIQUITY")
        print("=" * 60)
        print()
        print('"Every vintage computer has historical potential"')
        print()
        print(f"Chain ID: {CHAIN_ID}")
        print(f"Total Supply: {TOTAL_SUPPLY:,} RTC")
        print(f"Block Time: {BLOCK_TIME_SECONDS // 60} minutes")
        print(f"Founder Wallets: {len(FOUNDER_WALLETS)}")
        print()

        # Initialize founder wallets with premine
        founder_amount = int((PREMINE_AMOUNT / len(FOUNDER_WALLETS)) * 100_000_000)
        for wallet in FOUNDER_WALLETS:
            # Create founder UTXO
            tx = Transaction.mining_reward(
                miner_wallet=wallet,
                reward_amount=founder_amount,
                block_height=0,
                antiquity_score=100.0,
                hardware_model="Genesis",
            )
            self.utxo_set.apply_transaction(tx, block_height=0)
            print(f"  Founder: {wallet[:40]}...")

        print()
        print("Genesis initialized!")

    def start(self):
        """Start the node"""
        self._running = True

        # Start network
        self.network.start()

        # Start block processor
        self._block_thread = threading.Thread(
            target=self._block_processor,
            daemon=True
        )
        self._block_thread.start()

        print()
        print(f"Node started!")
        print(f"  API: http://0.0.0.0:{self.api_port}")
        print(f"  P2P: port {self.api_port + 1}")
        print(f"  Mining: {'enabled' if self.is_mining else 'disabled'}")
        print()

    def stop(self):
        """Stop the node"""
        self._running = False
        self.network.stop()
        print("Node stopped")

    def _block_processor(self):
        """Background block processor"""
        while self._running:
            time.sleep(10)  # Check every 10 seconds

            status = self.poa.get_status()
            if status["time_remaining_seconds"] <= 0:
                self._process_block()

    def _process_block(self):
        """Process pending proofs and create new block"""
        previous_hash = "0" * 64  # TODO: Get from chain

        block = self.poa.produce_block(previous_hash)
        if block:
            # Apply mining rewards
            for miner in block.miners:
                tx = Transaction.mining_reward(
                    miner_wallet=miner.wallet,
                    reward_amount=miner.reward,
                    block_height=block.height,
                    antiquity_score=miner.antiquity_score,
                    hardware_model=miner.hardware_model,
                )
                self.utxo_set.apply_transaction(tx, block.height)

            # Broadcast block
            self.network.broadcast_block(block.__dict__)

            print(f"Block #{block.height} produced! "
                  f"{len(block.miners)} miners, "
                  f"{block.total_reward / 100_000_000:.2f} RTC distributed")

    # =========================================================================
    # API Methods
    # =========================================================================

    def get_block_height(self) -> int:
        return self.poa.current_block_height

    def get_total_minted(self) -> float:
        # TODO: Track properly
        return float(PREMINE_AMOUNT)

    def get_mining_pool(self) -> float:
        return float(TOTAL_SUPPLY - PREMINE_AMOUNT)

    def get_wallet_count(self) -> int:
        return len(self.utxo_set._by_address)

    def get_pending_proofs(self) -> int:
        return len(self.poa.pending_proofs)

    def get_block_age(self) -> int:
        return self.poa.get_status()["block_age_seconds"]

    def get_time_to_next_block(self) -> int:
        return self.poa.get_status()["time_remaining_seconds"]

    def get_uptime(self) -> int:
        return int(time.time() - self._start_time)

    def get_block(self, height: int):
        # TODO: Store blocks
        return None

    def get_block_by_hash(self, block_hash: str):
        # TODO: Store blocks
        return None

    def get_wallet(self, address: str):
        return self.balance_tracker.get_balance(address)

    def get_balance(self, address: str) -> int:
        return self.utxo_set.get_balance(address)

    def submit_mining_proof(
        self,
        wallet: str,
        hardware_model: str,
        release_year: int,
        uptime_days: int,
        entropy_hash: str = "",
    ):
        """Submit a mining proof"""
        # Validate hardware
        hardware = HardwareInfo(
            cpu_model=hardware_model,
            release_year=release_year,
            uptime_days=uptime_days,
        )

        validation = self.hardware_validator.validate_miner(
            wallet=wallet,
            hardware=hardware,
            current_block=self.poa.current_block_height,
        )

        if not validation["eligible"]:
            return {
                "success": False,
                "errors": validation["errors"],
            }

        # Submit to PoA
        proof = HardwareProof(
            cpu_model=hardware_model,
            release_year=release_year,
            uptime_days=uptime_days,
            hardware_hash=hardware.generate_hardware_hash(),
        )

        result = self.poa.submit_proof(
            wallet=wallet,
            hardware=proof,
            anti_emulation_hash=entropy_hash or "0" * 64,
        )

        return result

    def get_mining_status(self):
        return self.poa.get_status()

    def calculate_antiquity_score(self, release_year: int, uptime_days: int):
        score = compute_antiquity_score(release_year, uptime_days)
        return {
            "release_year": release_year,
            "uptime_days": uptime_days,
            "antiquity_score": score,
            "eligible": score >= 1.0,
        }

    def create_proposal(
        self,
        title: str,
        description: str,
        proposal_type: str,
        proposer: str,
        contract_hash: str = None,
    ):
        ptype = ProposalType[proposal_type.upper()]
        proposal = self.governance.create_proposal(
            title=title,
            description=description,
            proposal_type=ptype,
            proposer=proposer,
            contract_hash=contract_hash,
        )
        return proposal.to_dict()

    def vote_proposal(self, proposal_id: str, voter: str, support: bool):
        balance = self.utxo_set.get_balance(voter)
        vote = self.governance.vote(
            proposal_id=proposal_id,
            voter=voter,
            support=support,
            token_balance=balance,
        )
        return {"success": True, "weight": vote.weight}

    def get_proposals(self):
        return [p.to_dict() for p in self.governance.get_all_proposals()]

    def get_proposal(self, proposal_id: str):
        p = self.governance.get_proposal(proposal_id)
        return p.to_dict() if p else None

    def get_peers(self):
        return [
            {
                "address": p.peer_id.to_string(),
                "reputation": p.reputation,
                "best_height": p.best_block_height,
            }
            for p in self.network.peer_manager.get_peers()
        ]

    def get_entropy_profile(self):
        builder = EntropyProfileBuilder()
        profile = builder.collect_full_profile()
        return {
            "validator_id": profile.validator_id,
            "confidence_score": profile.confidence_score,
            "combined_hash": profile.combined_hash,
        }


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="RustChain Node - Proof of Antiquity Blockchain"
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT,
        help=f"API port (default: {DEFAULT_PORT})"
    )
    parser.add_argument(
        "--data-dir", type=str, default="./rustchain_data",
        help="Data directory"
    )
    parser.add_argument(
        "--mining", action="store_true",
        help="Enable mining"
    )
    parser.add_argument(
        "--validator-id", type=str, default=None,
        help="Custom validator ID (auto-generated if not provided)"
    )

    args = parser.parse_args()

    # Create node
    node = RustChainNode(
        data_dir=args.data_dir,
        api_port=args.port,
        enable_mining=args.mining,
    )

    # Create and start API server
    api = RustChainApi(node)
    api_server = ApiServer(api, port=args.port)

    # Handle shutdown
    def shutdown(signum, frame):
        print("\nShutting down...")
        api_server.stop()
        node.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Start
    node.start()
    api_server.start()

    print()
    print("=" * 60)
    print("RUSTCHAIN NODE RUNNING")
    print("=" * 60)
    print()
    print("Remember: This is NOT Proof of Work!")
    print("Older hardware wins, not faster hardware.")
    print()
    print("Press Ctrl+C to stop...")
    print()

    # Keep running
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
