#!/usr/bin/env python3
"""
RustChain BFT Consensus Module - RIP-0202
Byzantine Fault Tolerant Consensus for Multi-Node Operation

This module implements a simplified PBFT (Practical Byzantine Fault Tolerance)
consensus mechanism adapted for RustChain's Proof of Antiquity (PoA) model.

Key Features:
- 3-phase consensus: PRE-PREPARE, PREPARE, COMMIT
- Tolerates f byzantine nodes where total = 3f + 1
- Epoch-based consensus (one decision per epoch)
- View change for leader failure
- Integrated with PoA hardware attestation

Author: RustChain Team
RIP: 0202
Version: 1.0.0
"""

import hashlib
import hmac
import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, Iterable, List, Optional, Set, Tuple
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [BFT] %(message)s')

# ============================================================================
# CONSTANTS
# ============================================================================

BLOCK_TIME = 600  # 10 minutes per epoch
PREPARE_THRESHOLD = 2/3  # Need 2/3 of nodes to prepare
COMMIT_THRESHOLD = 2/3   # Need 2/3 of nodes to commit
VIEW_CHANGE_TIMEOUT = 90  # Seconds before triggering view change
CONSENSUS_MESSAGE_TTL = 300  # 5 minutes message validity


class ConsensusPhase(Enum):
    IDLE = "idle"
    PRE_PREPARE = "pre_prepare"
    PREPARE = "prepare"
    COMMIT = "commit"
    COMMITTED = "committed"
    VIEW_CHANGE = "view_change"


class MessageType(Enum):
    PRE_PREPARE = "pre_prepare"
    PREPARE = "prepare"
    COMMIT = "commit"
    VIEW_CHANGE = "view_change"
    NEW_VIEW = "new_view"
    CHECKPOINT = "checkpoint"


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class ConsensusMessage:
    """Message structure for BFT consensus"""
    msg_type: str
    view: int           # Current view number
    epoch: int          # RustChain epoch
    digest: str         # Hash of proposal
    node_id: str        # Sender node ID
    signature: str      # HMAC signature
    timestamp: int      # Unix timestamp
    proposal: Optional[Dict] = None  # Actual data (only in PRE-PREPARE)

    def to_dict(self) -> Dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict) -> 'ConsensusMessage':
        return ConsensusMessage(**data)

    def compute_digest(self) -> str:
        """Compute digest of the proposal"""
        if self.proposal:
            return hashlib.sha256(json.dumps(self.proposal, sort_keys=True).encode()).hexdigest()
        return self.digest


@dataclass
class EpochProposal:
    """Proposal for epoch settlement"""
    epoch: int
    miners: List[Dict]          # Miner attestations
    total_reward: float         # 1.5 RTC per epoch
    distribution: Dict[str, float]  # miner_id -> reward
    proposer: str               # Node that created proposal
    merkle_root: str            # Merkle root of miner data

    def compute_digest(self) -> str:
        data = {
            'epoch': self.epoch,
            'miners': self.miners,
            'total_reward': self.total_reward,
            'distribution': self.distribution,
            'proposer': self.proposer,
            'merkle_root': self.merkle_root
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


@dataclass
class ViewChangeMessage:
    """View change request"""
    view: int
    epoch: int
    node_id: str
    prepared_cert: Optional[Dict]  # Proof of prepared state
    signature: str
    timestamp: int = 0  # Unix timestamp (used for HMAC + freshness check)


# ============================================================================
# BFT CONSENSUS ENGINE
# ============================================================================

class BFTConsensus:
    """
    Practical Byzantine Fault Tolerance (PBFT) consensus engine for RustChain.

    Adapted for Proof of Antiquity:
    - No block proposer election (round-robin based on view)
    - Consensus on epoch settlements (miner rewards)
    - Hardware attestation validation before accepting proposals
    """

    def __init__(self, node_id: str, db_path: str, secret_key: str):
        self.node_id = node_id
        self.db_path = db_path
        self.secret_key = secret_key

        # State
        self.current_view = 0
        self.current_epoch = 0
        self.phase = ConsensusPhase.IDLE

        # Message logs
        self.pre_prepare_log: Dict[int, ConsensusMessage] = {}  # epoch -> message
        self.prepare_log: Dict[int, Dict[str, ConsensusMessage]] = {}  # epoch -> {node_id: msg}
        self.commit_log: Dict[int, Dict[str, ConsensusMessage]] = {}  # epoch -> {node_id: msg}
        self.view_change_log: Dict[int, Dict[str, ViewChangeMessage]] = {}  # view -> {node_id: msg}

        # Committed epochs
        self.committed_epochs: Set[int] = set()

        # Peer nodes
        self.peers: Dict[str, str] = {}  # node_id -> url

        # Thread synchronization
        self.lock = threading.RLock()

        # Timer for view change
        self.view_change_timer: Optional[threading.Timer] = None

        # Initialize database
        self._init_db()

    def _init_db(self):
        """Initialize BFT consensus tables"""
        with sqlite3.connect(self.db_path) as conn:
            # Consensus log table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bft_consensus_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    epoch INTEGER NOT NULL,
                    view INTEGER NOT NULL,
                    msg_type TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    proposal_json TEXT,
                    signature TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    UNIQUE(epoch, msg_type, node_id)
                )
            """)

            # Committed epochs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bft_committed_epochs (
                    epoch INTEGER PRIMARY KEY,
                    view INTEGER NOT NULL,
                    digest TEXT NOT NULL,
                    committed_at INTEGER NOT NULL,
                    proposal_json TEXT NOT NULL
                )
            """)

            # View change log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bft_view_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    view INTEGER NOT NULL,
                    node_id TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    UNIQUE(view, node_id)
                )
            """)

            conn.commit()

        logging.info(f"BFT consensus initialized for node {self.node_id}")

        # Restore committed epochs from DB so restarts don't double-credit.
        # Without this, committed_epochs starts empty and _finalize_epoch /
        # _apply_settlement will re-apply settlements for already-committed
        # epochs after a node restart.
        self._restore_committed_state()

    def _restore_committed_state(self):
        """Restore committed epochs and view number from DB on startup.

        Without this, a node restart forgets all committed epochs and the
        consensus engine will re-apply settlements, double-crediting miners.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT epoch, view FROM bft_committed_epochs"
                ).fetchall()
                for epoch, view in rows:
                    self.committed_epochs.add(epoch)
                    if view > self.current_view:
                        self.current_view = view

            if self.committed_epochs:
                logging.info(
                    f"Restored {len(self.committed_epochs)} committed epochs "
                    f"(max epoch={max(self.committed_epochs)}, view={self.current_view})"
                )
        except sqlite3.OperationalError as e:
            # Table may not exist on first run (will be created by _init_db)
            logging.debug(f"Could not restore committed state: {e}")

    def register_peer(self, node_id: str, url: str):
        """Register a peer node"""
        with self.lock:
            self.peers[node_id] = url
            logging.info(f"Registered peer: {node_id} at {url}")

    def get_total_nodes(self) -> int:
        """Get total number of nodes including self"""
        return len(self.peers) + 1

    def get_fault_tolerance(self) -> int:
        """Calculate f (max faulty nodes we can tolerate)"""
        # BFT requires n >= 3f + 1, so we can tolerate f = floor((n-1)/3) faulty nodes.
        # E.g., 4 nodes → f=1: one Byzantine node cannot forge a 2/3 quorum.
        n = self.get_total_nodes()
        return (n - 1) // 3

    def get_quorum_size(self) -> int:
        """Get quorum size for consensus"""
        # Quorum = 2f + 1 = ceil(2n/3). Using integer arithmetic (2n+2)//3 avoids
        # floating point and always rounds up, ensuring we exceed the 2/3 threshold.
        n = self.get_total_nodes()
        return (2 * n + 2) // 3

    def is_leader(self, view: int = None) -> bool:
        """Check if this node is the leader for current view"""
        if view is None:
            view = self.current_view

        # Deterministic round-robin: sorting by node_id ensures all nodes agree on
        # the leader ordering without a separate election or coordinator.
        nodes = sorted([self.node_id] + list(self.peers.keys()))
        leader_idx = view % len(nodes)
        return nodes[leader_idx] == self.node_id

    def get_leader(self, view: int = None) -> str:
        """Get the leader node ID for a view"""
        if view is None:
            view = self.current_view

        nodes = sorted([self.node_id] + list(self.peers.keys()))
        leader_idx = view % len(nodes)
        return nodes[leader_idx]

    def _derive_node_key(self, node_id: str) -> str:
        """Derive a per-node HMAC key from the shared secret.

        Using HMAC(shared_secret, node_id) as the per-node key means:
        1. Each node's signatures are unique and cannot be forged by peers.
        2. A compromised node only leaks its own derived key, not the
           shared secret or other nodes' derived keys.
        3. Existing deployments just need to set the same shared secret
           on all nodes — per-node keys are derived automatically.
        """
        return hmac.new(
            self.secret_key.encode(),
            node_id.encode(),
            hashlib.sha256
        ).hexdigest()

    def _sign_message(self, data: str) -> str:
        """Sign a message with node-specific HMAC key"""
        node_key = self._derive_node_key(self.node_id)
        return hmac.new(
            node_key.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()

    def _verify_signature(self, node_id: str, data: str, signature: str) -> bool:
        """Verify message signature using the sender's derived key.

        Each node has a unique derived key (see _derive_node_key), so
        messages are authenticated per-sender.  A compromised node
        cannot forge messages claiming to be from a different node_id.
        """
        node_key = self._derive_node_key(node_id)
        expected = hmac.new(
            node_key.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected)

    # ========================================================================
    # PHASE 1: PRE-PREPARE (Leader proposes)
    # ========================================================================

    def propose_epoch_settlement(self, epoch: int, miners: List[Dict],
                                  distribution: Dict[str, float]) -> Optional[ConsensusMessage]:
        """
        Leader proposes epoch settlement (PRE-PREPARE phase).
        Only the leader for current view can call this.
        """
        with self.lock:
            if not self.is_leader():
                logging.warning(f"Node {self.node_id} is not leader for view {self.current_view}")
                return None

            if epoch in self.committed_epochs:
                logging.info(f"Epoch {epoch} already committed")
                return None

            # Create proposal
            proposal = EpochProposal(
                epoch=epoch,
                miners=miners,
                total_reward=1.5,  # RTC per epoch
                distribution=distribution,
                proposer=self.node_id,
                merkle_root=self._compute_merkle_root(miners)
            )

            digest = proposal.compute_digest()
            timestamp = int(time.time())

            # Sign the message
            sign_data = f"{MessageType.PRE_PREPARE.value}:{self.current_view}:{epoch}:{digest}:{timestamp}"
            signature = self._sign_message(sign_data)

            # Create PRE-PREPARE message
            msg = ConsensusMessage(
                msg_type=MessageType.PRE_PREPARE.value,
                view=self.current_view,
                epoch=epoch,
                digest=digest,
                node_id=self.node_id,
                signature=signature,
                timestamp=timestamp,
                proposal=asdict(proposal)
            )

            # Log locally
            self.pre_prepare_log[epoch] = msg
            self.phase = ConsensusPhase.PRE_PREPARE
            self._save_message_to_db(msg)

            # Start view change timer
            self._start_view_change_timer()

            # Broadcast to peers
            self._broadcast_message(msg)

            logging.info(f"[PRE-PREPARE] Leader proposed epoch {epoch} settlement")

            # Leader also prepares
            self._handle_pre_prepare(msg)

            return msg

    def _compute_merkle_root(self, miners: List[Dict]) -> str:
        """Compute merkle root of miner attestations"""
        if not miners:
            return hashlib.sha256(b"empty").hexdigest()

        # Simple merkle: hash all miner data
        hashes = [
            hashlib.sha256(json.dumps(m, sort_keys=True).encode()).hexdigest()
            for m in miners
        ]

        while len(hashes) > 1:
            # Duplicate the last leaf when the count is odd so we always pair evenly.
            # This is the standard Bitcoin-style merkle padding strategy.
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])
            new_hashes = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i + 1]
                new_hashes.append(hashlib.sha256(combined.encode()).hexdigest())
            hashes = new_hashes

        return hashes[0]

    # ========================================================================
    # PHASE 2: PREPARE (Nodes validate and prepare)
    # ========================================================================

    def _handle_pre_prepare(self, msg: ConsensusMessage) -> Optional[ConsensusMessage]:
        """Handle received PRE-PREPARE message"""
        with self.lock:
            epoch = msg.epoch

            # Validate message
            if msg.view != self.current_view:
                logging.warning(f"PRE-PREPARE for wrong view: {msg.view} != {self.current_view}")
                return None

            if epoch in self.committed_epochs:
                logging.info(f"Epoch {epoch} already committed")
                return None

            # Verify it's from the leader
            if msg.node_id != self.get_leader(msg.view):
                logging.warning(f"PRE-PREPARE not from leader: {msg.node_id}")
                return None

            # Verify HMAC signature (matches pattern in handle_prepare/handle_commit)
            sign_data = f"{MessageType.PRE_PREPARE.value}:{msg.view}:{epoch}:{msg.digest}:{msg.timestamp}"
            if not self._verify_signature(msg.node_id, sign_data, msg.signature):
                logging.warning(f"Invalid PRE-PREPARE signature from {msg.node_id}")
                return None

            # Check timestamp freshness
            if abs(time.time() - msg.timestamp) > CONSENSUS_MESSAGE_TTL:
                logging.warning(f"Stale PRE-PREPARE from {msg.node_id} (age={int(time.time()) - msg.timestamp}s)")
                return None

            # Validate proposal (hardware attestation checks)
            if not self._validate_proposal(msg.proposal):
                logging.warning(f"Invalid proposal for epoch {epoch}")
                return None

            # Store PRE-PREPARE
            if epoch not in self.pre_prepare_log:
                self.pre_prepare_log[epoch] = msg
                self._save_message_to_db(msg)

            # Send PREPARE message
            timestamp = int(time.time())
            sign_data = f"{MessageType.PREPARE.value}:{msg.view}:{epoch}:{msg.digest}:{timestamp}"
            signature = self._sign_message(sign_data)

            prepare_msg = ConsensusMessage(
                msg_type=MessageType.PREPARE.value,
                view=msg.view,
                epoch=epoch,
                digest=msg.digest,
                node_id=self.node_id,
                signature=signature,
                timestamp=timestamp
            )

            # Log prepare
            if epoch not in self.prepare_log:
                self.prepare_log[epoch] = {}
            self.prepare_log[epoch][self.node_id] = prepare_msg
            self._save_message_to_db(prepare_msg)

            self.phase = ConsensusPhase.PREPARE

            # Broadcast PREPARE
            self._broadcast_message(prepare_msg)

            logging.info(f"[PREPARE] Node {self.node_id} prepared epoch {epoch}")

            # Check if we have quorum to commit
            self._check_prepare_quorum(epoch)

            return prepare_msg

    def handle_prepare(self, msg: ConsensusMessage):
        """Handle received PREPARE message from peer"""
        with self.lock:
            epoch = msg.epoch

            # Validate
            if msg.view != self.current_view:
                return

            if epoch in self.committed_epochs:
                return

            # Verify signature
            sign_data = f"{MessageType.PREPARE.value}:{msg.view}:{epoch}:{msg.digest}:{msg.timestamp}"
            if not self._verify_signature(msg.node_id, sign_data, msg.signature):
                logging.warning(f"Invalid PREPARE signature from {msg.node_id}")
                return

            # Check timestamp freshness — prevents replay of stale messages
            if abs(time.time() - msg.timestamp) > CONSENSUS_MESSAGE_TTL:
                logging.warning(f"Stale PREPARE from {msg.node_id} (age={int(time.time()) - msg.timestamp}s)")
                return

            # Verify digest matches the PRE-PREPARE for this epoch
            if epoch in self.pre_prepare_log and msg.digest != self.pre_prepare_log[epoch].digest:
                logging.warning(f"PREPARE digest mismatch for epoch {epoch}: expected {self.pre_prepare_log[epoch].digest[:16]}... got {msg.digest[:16]}...")
                return

            # Store prepare
            if epoch not in self.prepare_log:
                self.prepare_log[epoch] = {}

            if msg.node_id not in self.prepare_log[epoch]:
                self.prepare_log[epoch][msg.node_id] = msg
                self._save_message_to_db(msg)
                logging.info(f"[PREPARE] Received from {msg.node_id} for epoch {epoch}")

            # Check quorum
            self._check_prepare_quorum(epoch)

    def _check_prepare_quorum(self, epoch: int):
        """Check if we have quorum of PREPARE messages"""
        if epoch not in self.prepare_log:
            return

        prepare_count = len(self.prepare_log[epoch])
        quorum = self.get_quorum_size()

        logging.info(f"[PREPARE] Epoch {epoch}: {prepare_count}/{quorum} prepares")

        # Verify all prepares share the same digest as the PRE-PREPARE.
        # Individual handle_prepare() calls already filter mismatches, but this
        # provides defense-in-depth against race conditions or code paths that
        # bypass the per-message check.
        if epoch in self.pre_prepare_log:
            expected_digest = self.pre_prepare_log[epoch].digest
            for node_id in list(self.prepare_log[epoch].keys()):
                msg = self.prepare_log[epoch][node_id]
                if msg.digest != expected_digest:
                    logging.warning(
                        f"[PREPARE] Digest mismatch from {node_id} for epoch {epoch}: "
                        f"expected {expected_digest[:16]}... got {msg.digest[:16]}..."
                    )
                    del self.prepare_log[epoch][node_id]
                    prepare_count -= 1

        # Phase guard prevents sending duplicate COMMITs if more PREPAREs arrive
        # after we already advanced — only transition once per epoch.
        if prepare_count >= quorum and self.phase == ConsensusPhase.PREPARE:
            # Transition to COMMIT phase
            self._send_commit(epoch)

    # ========================================================================
    # PHASE 3: COMMIT (Finalize consensus)
    # ========================================================================

    def _send_commit(self, epoch: int):
        """Send COMMIT message after receiving quorum of PREPAREs"""
        with self.lock:
            if epoch not in self.pre_prepare_log:
                return

            pre_prepare = self.pre_prepare_log[epoch]
            timestamp = int(time.time())

            sign_data = f"{MessageType.COMMIT.value}:{pre_prepare.view}:{epoch}:{pre_prepare.digest}:{timestamp}"
            signature = self._sign_message(sign_data)

            commit_msg = ConsensusMessage(
                msg_type=MessageType.COMMIT.value,
                view=pre_prepare.view,
                epoch=epoch,
                digest=pre_prepare.digest,
                node_id=self.node_id,
                signature=signature,
                timestamp=timestamp
            )

            # Log commit
            if epoch not in self.commit_log:
                self.commit_log[epoch] = {}
            self.commit_log[epoch][self.node_id] = commit_msg
            self._save_message_to_db(commit_msg)

            self.phase = ConsensusPhase.COMMIT

            # Broadcast COMMIT
            self._broadcast_message(commit_msg)

            logging.info(f"[COMMIT] Node {self.node_id} committed epoch {epoch}")

            # Check commit quorum
            self._check_commit_quorum(epoch)

    def handle_commit(self, msg: ConsensusMessage):
        """Handle received COMMIT message"""
        with self.lock:
            epoch = msg.epoch

            if epoch in self.committed_epochs:
                return

            # Validate view matches current view
            if msg.view != self.current_view:
                return

            # Verify signature
            sign_data = f"{MessageType.COMMIT.value}:{msg.view}:{epoch}:{msg.digest}:{msg.timestamp}"
            if not self._verify_signature(msg.node_id, sign_data, msg.signature):
                logging.warning(f"Invalid COMMIT signature from {msg.node_id}")
                return

            # Check timestamp freshness — prevents replay of stale messages
            if abs(time.time() - msg.timestamp) > CONSENSUS_MESSAGE_TTL:
                logging.warning(f"Stale COMMIT from {msg.node_id} (age={int(time.time()) - msg.timestamp}s)")
                return

            # Verify digest matches the PRE-PREPARE for this epoch
            if epoch in self.pre_prepare_log and msg.digest != self.pre_prepare_log[epoch].digest:
                logging.warning(f"COMMIT digest mismatch for epoch {epoch}: expected {self.pre_prepare_log[epoch].digest[:16]}... got {msg.digest[:16]}...")
                return

            # Store commit
            if epoch not in self.commit_log:
                self.commit_log[epoch] = {}

            if msg.node_id not in self.commit_log[epoch]:
                self.commit_log[epoch][msg.node_id] = msg
                self._save_message_to_db(msg)
                logging.info(f"[COMMIT] Received from {msg.node_id} for epoch {epoch}")

            # Check quorum
            self._check_commit_quorum(epoch)

    def _check_commit_quorum(self, epoch: int):
        """Check if we have quorum of COMMIT messages"""
        if epoch not in self.commit_log:
            return

        commit_count = len(self.commit_log[epoch])
        quorum = self.get_quorum_size()

        logging.info(f"[COMMIT] Epoch {epoch}: {commit_count}/{quorum} commits")

        if commit_count >= quorum and epoch not in self.committed_epochs:
            # CONSENSUS REACHED!
            self._finalize_epoch(epoch)

    def _finalize_epoch(self, epoch: int):
        """Finalize epoch after consensus reached"""
        with self.lock:
            if epoch in self.committed_epochs:
                return

            self.committed_epochs.add(epoch)
            self.phase = ConsensusPhase.COMMITTED

            # Cancel view change timer
            self._cancel_view_change_timer()

            # Get the proposal
            pre_prepare = self.pre_prepare_log.get(epoch)
            if not pre_prepare or not pre_prepare.proposal:
                logging.error(f"No proposal found for committed epoch {epoch}")
                return

            # Save to committed epochs table
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO bft_committed_epochs
                    (epoch, view, digest, committed_at, proposal_json)
                    VALUES (?, ?, ?, ?, ?)
                """, (epoch, self.current_view, pre_prepare.digest,
                      int(time.time()), json.dumps(pre_prepare.proposal)))
                conn.commit()

            logging.info(f"CONSENSUS REACHED for epoch {epoch}")
            logging.info(f"  Digest: {pre_prepare.digest[:16]}...")
            logging.info(f"  Proposer: {pre_prepare.proposal.get('proposer')}")

            # Apply the settlement (distribute rewards)
            self._apply_settlement(pre_prepare.proposal)

    def _apply_settlement(self, proposal: Dict):
        """Apply the consensus settlement to database (idempotent).

        Uses epoch-scoped ledger entries to ensure each epoch's rewards are
        credited exactly once, even if _apply_settlement is called multiple
        times for the same epoch (e.g. after a restart before
        committed_epochs is fully restored).
        """
        epoch = proposal.get('epoch')
        distribution = proposal.get('distribution', {})

        with sqlite3.connect(self.db_path) as conn:
            # ── Idempotency guard ────────────────────────────────────
            # If any ledger entry already exists for this epoch, the
            # settlement was already applied.  Bail out.
            existing = conn.execute(
                "SELECT 1 FROM ledger WHERE memo = ? LIMIT 1",
                (f"epoch_{epoch}_bft",)
            ).fetchone()
            if existing:
                logging.warning(
                    f"Settlement for epoch {epoch} already applied — skipping "
                    f"to prevent reward doubling"
                )
                return

            for miner_id, reward in distribution.items():
                # Store as integer micro-RTC (1 RTC = 1,000,000 uRTC) to avoid
                # floating-point drift accumulating across many ledger entries.
                reward_urtc = int(reward * 1_000_000)

                conn.execute("""
                    INSERT INTO balances (miner_id, amount_i64)
                    VALUES (?, ?)
                    ON CONFLICT(miner_id) DO UPDATE SET
                    amount_i64 = amount_i64 + excluded.amount_i64
                """, (miner_id, reward_urtc))

                # Log in ledger
                conn.execute("""
                    INSERT INTO ledger (miner_id, delta_i64, tx_type, memo, ts)
                    VALUES (?, ?, 'reward', ?, ?)
                """, (miner_id, reward_urtc, f"epoch_{epoch}_bft", int(time.time())))

            conn.commit()

        logging.info(f"Applied settlement for epoch {epoch}: {len(distribution)} miners rewarded")

    # ========================================================================
    # VIEW CHANGE (Leader failure handling)
    # ========================================================================

    def _start_view_change_timer(self):
        """Start timer for view change if consensus not reached"""
        self._cancel_view_change_timer()

        self.view_change_timer = threading.Timer(VIEW_CHANGE_TIMEOUT, self._trigger_view_change)
        self.view_change_timer.daemon = True
        self.view_change_timer.start()

    def _cancel_view_change_timer(self):
        """Cancel view change timer"""
        if self.view_change_timer:
            self.view_change_timer.cancel()
            self.view_change_timer = None

    def _trigger_view_change(self):
        """Trigger view change due to timeout"""
        with self.lock:
            logging.warning(f"[VIEW-CHANGE] Timeout! Requesting view {self.current_view + 1}")
            self.phase = ConsensusPhase.VIEW_CHANGE

            new_view = self.current_view + 1
            timestamp = int(time.time())

            sign_data = f"{MessageType.VIEW_CHANGE.value}:{new_view}:{self.current_epoch}:{timestamp}"
            signature = self._sign_message(sign_data)

            vc_msg = ViewChangeMessage(
                view=new_view,
                epoch=self.current_epoch,
                node_id=self.node_id,
                prepared_cert=None,  # Could include prepared certificate
                signature=signature,
                timestamp=timestamp
            )

            # Log view change
            if new_view not in self.view_change_log:
                self.view_change_log[new_view] = {}
            self.view_change_log[new_view][self.node_id] = vc_msg

            # Broadcast view change
            self._broadcast_view_change(vc_msg)

            # Check if we have quorum for view change
            self._check_view_change_quorum(new_view)

    def handle_view_change(self, msg_data: Dict):
        """Handle received VIEW-CHANGE message"""
        with self.lock:
            new_view = msg_data.get('view')
            node_id = msg_data.get('node_id')
            signature = msg_data.get('signature', '')
            timestamp = msg_data.get('timestamp', 0)
            epoch = msg_data.get('epoch', 0)

            # -- Validation: reject garbage / missing fields -----------------
            if not all([new_view, node_id, signature, timestamp]):
                logging.warning("[VIEW-CHANGE] Rejected: missing required fields")
                return

            # Must be requesting a *higher* view than current
            if new_view <= self.current_view:
                logging.warning(
                    f"[VIEW-CHANGE] Rejected stale view {new_view} "
                    f"(<= current {self.current_view})"
                )
                return

            # -- Verify HMAC signature (same format as _trigger_view_change) --
            sign_data = (
                f"{MessageType.VIEW_CHANGE.value}:{new_view}:{epoch}:{timestamp}"
            )
            if not self._verify_signature(node_id, sign_data, signature):
                logging.warning(
                    f"[VIEW-CHANGE] Invalid signature from {node_id}"
                )
                return

            # -- Timestamp freshness -----------------------------------------
            if abs(time.time() - timestamp) > CONSENSUS_MESSAGE_TTL:
                logging.warning(
                    f"[VIEW-CHANGE] Stale message from {node_id} "
                    f"(age={int(time.time()) - timestamp}s)"
                )
                return

            # -- Passed all checks, store ------------------------------------
            if new_view not in self.view_change_log:
                self.view_change_log[new_view] = {}

            if node_id not in self.view_change_log[new_view]:
                self.view_change_log[new_view][node_id] = ViewChangeMessage(**msg_data)
                logging.info(f"[VIEW-CHANGE] Received from {node_id} for view {new_view}")

            self._check_view_change_quorum(new_view)

    def _check_view_change_quorum(self, new_view: int):
        """Check if we have quorum for view change"""
        if new_view not in self.view_change_log:
            return

        vc_count = len(self.view_change_log[new_view])
        quorum = self.get_quorum_size()

        logging.info(f"[VIEW-CHANGE] View {new_view}: {vc_count}/{quorum} votes")

        if vc_count >= quorum:
            self._perform_view_change(new_view)

    def _perform_view_change(self, new_view: int):
        """Perform view change"""
        with self.lock:
            if new_view <= self.current_view:
                return

            self.current_view = new_view
            self.phase = ConsensusPhase.IDLE

            logging.info(f"[NEW-VIEW] Changed to view {new_view}, leader: {self.get_leader()}")

            # If we're the new leader, propose
            if self.is_leader():
                logging.info(f"[NEW-VIEW] We are the new leader!")
                # New leader should re-propose pending epochs

    # ========================================================================
    # VALIDATION
    # ========================================================================

    def _validate_proposal(self, proposal: Dict) -> bool:
        """Validate an epoch settlement proposal"""
        if not proposal:
            return False

        epoch = proposal.get('epoch')
        miners = proposal.get('miners', [])
        distribution = proposal.get('distribution', {})

        # Check epoch is valid
        if epoch is None or epoch < 0:
            return False

        # Use absolute tolerance rather than ==, since floating-point arithmetic
        # on reward fractions can produce values like 1.4999999999 or 1.5000000001.
        total = sum(distribution.values())
        if abs(total - 1.5) > 0.001:
            logging.warning(f"Invalid total reward: {total} != 1.5")
            return False

        # Check all miners in distribution are in miner list
        miner_ids = {m.get('miner_id') for m in miners}
        for miner_id in distribution:
            if miner_id not in miner_ids:
                logging.warning(f"Miner {miner_id} in distribution but not in miners list")
                return False

        # Verify merkle_root matches the submitted miners list.
        # Without this check a Byzantine leader can recycle a valid merkle_root
        # from a previous epoch while submitting a different (falsified) miners
        # list, and honest nodes would still send PREPARE for the forged proposal.
        expected_merkle = self._compute_merkle_root(miners)
        if proposal.get('merkle_root') != expected_merkle:
            logging.warning(
                f"Proposal merkle_root mismatch for epoch {epoch}: "
                f"got {proposal.get('merkle_root', '')[:16]}... "
                f"expected {expected_merkle[:16]}..."
            )
            return False

        return True

    # ========================================================================
    # NETWORK
    # ========================================================================

    def _broadcast_message(self, msg: ConsensusMessage):
        """Broadcast message to all peers"""
        for node_id, url in self.peers.items():
            try:
                endpoint = f"{url}/bft/message"
                response = requests.post(
                    endpoint,
                    json=msg.to_dict(),
                    timeout=5,
                    headers={'X-Node-ID': self.node_id}
                )
                if response.ok:
                    logging.debug(f"Broadcast {msg.msg_type} to {node_id}")
            except Exception as e:
                logging.error(f"Failed to broadcast to {node_id}: {e}")

    def _broadcast_view_change(self, msg: ViewChangeMessage):
        """Broadcast view change message"""
        msg_data = asdict(msg)
        for node_id, url in self.peers.items():
            try:
                endpoint = f"{url}/bft/view_change"
                response = requests.post(endpoint, json=msg_data, timeout=5)
                if response.ok:
                    logging.debug(f"Broadcast VIEW-CHANGE to {node_id}")
            except Exception as e:
                logging.error(f"Failed to broadcast VIEW-CHANGE to {node_id}: {e}")

    def _save_message_to_db(self, msg: ConsensusMessage):
        """Save consensus message to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO bft_consensus_log
                    (epoch, view, msg_type, node_id, digest, proposal_json, signature, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    msg.epoch, msg.view, msg.msg_type, msg.node_id,
                    msg.digest, json.dumps(msg.proposal) if msg.proposal else None,
                    msg.signature, msg.timestamp
                ))
                conn.commit()
        except Exception as e:
            logging.error(f"Failed to save message: {e}")

    def receive_message(self, msg_data: Dict):
        """Handle incoming consensus message"""
        msg_type = msg_data.get('msg_type')

        if msg_type == MessageType.PRE_PREPARE.value:
            msg = ConsensusMessage.from_dict(msg_data)
            self._handle_pre_prepare(msg)
        elif msg_type == MessageType.PREPARE.value:
            msg = ConsensusMessage.from_dict(msg_data)
            self.handle_prepare(msg)
        elif msg_type == MessageType.COMMIT.value:
            msg = ConsensusMessage.from_dict(msg_data)
            self.handle_commit(msg)

    # ========================================================================
    # STATUS
    # ========================================================================

    def get_status(self) -> Dict:
        """Get consensus status"""
        with self.lock:
            return {
                'node_id': self.node_id,
                'current_view': self.current_view,
                'current_epoch': self.current_epoch,
                'phase': self.phase.value,
                'leader': self.get_leader(),
                'is_leader': self.is_leader(),
                'total_nodes': self.get_total_nodes(),
                'fault_tolerance': self.get_fault_tolerance(),
                'quorum_size': self.get_quorum_size(),
                'committed_epochs': len(self.committed_epochs),
                'peers': list(self.peers.keys())
            }


# ============================================================================
# FLASK ROUTES FOR BFT
# ============================================================================

def create_bft_routes(app, bft: BFTConsensus):
    """Add BFT consensus routes to Flask app"""
    from flask import request, jsonify

    def _json_object():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return None, ({'error': 'JSON object required'}, 400)
        return data, None

    def _missing_fields(data: Dict, required: Iterable[str]) -> List[str]:
        return [field for field in required if field not in data]

    @app.route('/bft/status', methods=['GET'])
    def bft_status():
        """Get BFT consensus status"""
        return jsonify(bft.get_status())

    @app.route('/bft/message', methods=['POST'])
    def bft_receive_message():
        """Receive consensus message from peer"""
        try:
            msg_data, error = _json_object()
            if error:
                return jsonify(error[0]), error[1]

            msg_type = msg_data.get('msg_type')
            valid_types = {
                MessageType.PRE_PREPARE.value,
                MessageType.PREPARE.value,
                MessageType.COMMIT.value,
            }
            if msg_type not in valid_types:
                return jsonify({'error': 'invalid msg_type'}), 400

            bft.receive_message(msg_data)
            return jsonify({'status': 'ok'})
        except Exception as e:
            logging.error(f"BFT message error: {e}")
            return jsonify({'error': str(e)}), 400

    @app.route('/bft/view_change', methods=['POST'])
    def bft_view_change():
        """Receive view change message"""
        try:
            msg_data, error = _json_object()
            if error:
                return jsonify(error[0]), error[1]

            missing = _missing_fields(
                msg_data,
                ('view', 'epoch', 'node_id', 'signature', 'timestamp'),
            )
            if missing:
                return jsonify({'error': f"missing required fields: {', '.join(missing)}"}), 400

            bft.handle_view_change(msg_data)
            return jsonify({'status': 'ok'})
        except Exception as e:
            logging.error(f"BFT view change error: {e}")
            return jsonify({'error': str(e)}), 400

    @app.route('/bft/propose', methods=['POST'])
    def bft_propose():
        """Manually trigger epoch proposal (admin)"""
        try:
            data = request.get_json()
            epoch = data.get('epoch')
            miners = data.get('miners', [])
            distribution = data.get('distribution', {})

            msg = bft.propose_epoch_settlement(epoch, miners, distribution)
            if msg:
                return jsonify({'status': 'proposed', 'digest': msg.digest})
            else:
                return jsonify({'error': 'not_leader_or_already_committed'}), 400
        except Exception as e:
            logging.error(f"BFT propose error: {e}")
            return jsonify({'error': str(e)}), 500


# ============================================================================
# MAIN (Testing)
# ============================================================================

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("RustChain BFT Consensus Module - RIP-0202")
    print("=" * 60)

    # Test with mock data
    node_id = sys.argv[1] if len(sys.argv) > 1 else "node-131"
    db_path = "/tmp/bft_test.db"
    secret_key = "rustchain_bft_testnet_key_2025"

    bft = BFTConsensus(node_id, db_path, secret_key)

    # Register peer
    bft.register_peer("node-153", "http://50.28.86.153:8099")

    print(f"\nNode: {node_id}")
    print(f"Is Leader: {bft.is_leader()}")
    print(f"Current View: {bft.current_view}")
    print(f"Total Nodes: {bft.get_total_nodes()}")
    print(f"Quorum Size: {bft.get_quorum_size()}")
    print(f"Fault Tolerance: {bft.get_fault_tolerance()}")

    if bft.is_leader():
        print("\nProposing epoch settlement...")

        # Mock miner data
        miners = [
            {'miner_id': 'g4-powerbook-115', 'device_arch': 'G4', 'weight': 2.5},
            {'miner_id': 'sophia-nas-c4130', 'device_arch': 'modern', 'weight': 1.0},
        ]

        total_weight = sum(m['weight'] for m in miners)
        distribution = {
            m['miner_id']: 1.5 * (m['weight'] / total_weight)
            for m in miners
        }

        msg = bft.propose_epoch_settlement(epoch=425, miners=miners, distribution=distribution)
        if msg:
            print(f"Proposed! Digest: {msg.digest[:32]}...")

    print("\n" + "=" * 60)
    print("Status:", json.dumps(bft.get_status(), indent=2))
