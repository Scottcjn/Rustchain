"""
RustChain Governance (RIP-0002, RIP-0005, RIP-0006)
===================================================

Hybrid human + Sophia AI governance system.

Features:
- Proposal creation and voting
- Sophia AI evaluation (Endorse/Veto/Analyze)
- Token-weighted and reputation-weighted voting
- Smart contract binding layer
- Delegation framework
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Callable
from decimal import Decimal

from .core_types import WalletAddress, TokenAmount


# =============================================================================
# Proposal Status & Types
# =============================================================================

class ProposalStatus(Enum):
    """Proposal lifecycle status"""
    DRAFT = auto()
    SUBMITTED = auto()
    SOPHIA_REVIEW = auto()
    VOTING = auto()
    PASSED = auto()
    REJECTED = auto()
    VETOED = auto()
    EXECUTED = auto()
    EXPIRED = auto()


class ProposalType(Enum):
    """Types of proposals"""
    PARAMETER_CHANGE = auto()
    MONETARY_POLICY = auto()
    PROTOCOL_UPGRADE = auto()
    VALIDATOR_CHANGE = auto()
    SMART_CONTRACT = auto()
    COMMUNITY = auto()


class SophiaDecision(Enum):
    """Sophia AI evaluation decisions"""
    PENDING = auto()
    ENDORSE = auto()      # Boosts support probability
    VETO = auto()         # Locks proposal
    ANALYZE = auto()      # Neutral, logs public rationale


# =============================================================================
# Governance Constants
# =============================================================================

VOTING_PERIOD_DAYS: int = 7
QUORUM_PERCENTAGE: float = 0.33  # 33% participation minimum
EXECUTION_DELAY_BLOCKS: int = 3
REPUTATION_DECAY_WEEKLY: float = 0.05  # 5% weekly decay


# =============================================================================
# Proposal Data Classes
# =============================================================================

@dataclass
class Vote:
    """A single vote on a proposal"""
    voter: WalletAddress
    support: bool
    weight: Decimal
    timestamp: int
    delegation_from: Optional[WalletAddress] = None


@dataclass
class SophiaEvaluation:
    """Sophia AI's evaluation of a proposal"""
    decision: SophiaDecision
    rationale: str
    feasibility_score: float
    risk_level: str  # "low", "medium", "high"
    aligned_precedent: List[str]
    timestamp: int


@dataclass
class Proposal:
    """A governance proposal"""
    id: str
    title: str
    description: str
    proposal_type: ProposalType
    proposer: WalletAddress
    created_at: int
    status: ProposalStatus = ProposalStatus.DRAFT

    # Contract binding (RIP-0005)
    contract_hash: Optional[str] = None
    requires_multi_sig: bool = False
    timelock_blocks: int = EXECUTION_DELAY_BLOCKS
    auto_expire: bool = True

    # Voting data
    votes: List[Vote] = field(default_factory=list)
    voting_starts_at: Optional[int] = None
    voting_ends_at: Optional[int] = None

    # Sophia evaluation (RIP-0002)
    sophia_evaluation: Optional[SophiaEvaluation] = None

    # Execution
    executed_at: Optional[int] = None
    execution_tx_hash: Optional[str] = None

    @property
    def yes_votes(self) -> Decimal:
        return sum(v.weight for v in self.votes if v.support)

    @property
    def no_votes(self) -> Decimal:
        return sum(v.weight for v in self.votes if not v.support)

    @property
    def total_votes(self) -> Decimal:
        return sum(v.weight for v in self.votes)

    @property
    def approval_percentage(self) -> float:
        total = self.total_votes
        if total == 0:
            return 0.0
        return float(self.yes_votes / total)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "type": self.proposal_type.name,
            "proposer": self.proposer.address,
            "status": self.status.name,
            "created_at": self.created_at,
            "contract_hash": self.contract_hash,
            "yes_votes": str(self.yes_votes),
            "no_votes": str(self.no_votes),
            "total_votes": str(self.total_votes),
            "approval_percentage": self.approval_percentage,
            "sophia_decision": (
                self.sophia_evaluation.decision.name
                if self.sophia_evaluation else "PENDING"
            ),
        }


# =============================================================================
# Reputation System (RIP-0006)
# =============================================================================

@dataclass
class NodeReputation:
    """Reputation score for a node/wallet"""
    wallet: WalletAddress
    score: float = 50.0  # Start neutral
    participation_count: int = 0
    correct_predictions: int = 0
    uptime_contribution: float = 0.0
    sophia_alignment: float = 0.0  # Correlation with Sophia decisions
    last_activity: int = 0

    def decay(self, weeks_inactive: int):
        """Apply decay for inactivity"""
        decay_factor = (1 - REPUTATION_DECAY_WEEKLY) ** weeks_inactive
        self.score *= decay_factor

    def update_alignment(self, voted_with_sophia: bool):
        """Update Sophia alignment score"""
        weight = 0.1
        if voted_with_sophia:
            self.sophia_alignment = min(1.0, self.sophia_alignment + weight)
        else:
            self.sophia_alignment = max(0.0, self.sophia_alignment - weight)


@dataclass
class Delegation:
    """Voting power delegation"""
    from_wallet: WalletAddress
    to_wallet: WalletAddress
    weight: Decimal  # Percentage of voting power delegated
    created_at: int
    expires_at: Optional[int] = None

    def is_active(self, current_time: int) -> bool:
        if self.expires_at and current_time > self.expires_at:
            return False
        return True


# =============================================================================
# Governance Engine
# =============================================================================

class GovernanceEngine:
    """
    Main governance engine implementing RIP-0002, RIP-0005, RIP-0006.

    Lifecycle:
    1. Proposal created via create_proposal()
    2. Sophia evaluates via sophia_evaluate()
    3. If not vetoed, voting begins
    4. After voting period, proposal passes/fails
    5. Passed proposals execute after delay
    """

    def __init__(self, total_supply: int):
        self.proposals: Dict[str, Proposal] = {}
        self.reputations: Dict[str, NodeReputation] = {}
        self.delegations: Dict[str, List[Delegation]] = {}
        self.total_supply = total_supply
        self.proposal_counter = 0

    def create_proposal(
        self,
        title: str,
        description: str,
        proposal_type: ProposalType,
        proposer: WalletAddress,
        contract_hash: Optional[str] = None,
    ) -> Proposal:
        """
        Create a new governance proposal.

        Args:
            title: Proposal title
            description: Detailed description
            proposal_type: Type of proposal
            proposer: Wallet creating the proposal
            contract_hash: Optional smart contract reference

        Returns:
            Created proposal
        """
        self.proposal_counter += 1
        proposal_id = f"RCP-{self.proposal_counter:04d}"

        proposal = Proposal(
            id=proposal_id,
            title=title,
            description=description,
            proposal_type=proposal_type,
            proposer=proposer,
            created_at=int(time.time()),
            contract_hash=contract_hash,
            status=ProposalStatus.SUBMITTED,
        )

        self.proposals[proposal_id] = proposal

        # Update proposer reputation
        self._update_reputation(proposer, activity_type="propose")

        return proposal

    def sophia_evaluate(
        self,
        proposal_id: str,
        decision: SophiaDecision,
        rationale: str,
        feasibility_score: float = 0.5,
        risk_level: str = "medium",
    ) -> SophiaEvaluation:
        """
        Record Sophia AI's evaluation of a proposal (RIP-0002).

        Args:
            proposal_id: Proposal to evaluate
            decision: ENDORSE, VETO, or ANALYZE
            rationale: Public explanation
            feasibility_score: 0.0-1.0
            risk_level: "low", "medium", "high"

        Returns:
            SophiaEvaluation object
        """
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        evaluation = SophiaEvaluation(
            decision=decision,
            rationale=rationale,
            feasibility_score=feasibility_score,
            risk_level=risk_level,
            aligned_precedent=[],
            timestamp=int(time.time()),
        )

        proposal.sophia_evaluation = evaluation

        if decision == SophiaDecision.VETO:
            proposal.status = ProposalStatus.VETOED
            print(f"🚫 Sophia VETOED proposal {proposal_id}: {rationale}")
        elif decision == SophiaDecision.ENDORSE:
            proposal.status = ProposalStatus.VOTING
            proposal.voting_starts_at = int(time.time())
            proposal.voting_ends_at = proposal.voting_starts_at + (
                VOTING_PERIOD_DAYS * 86400
            )
            print(f"✅ Sophia ENDORSED proposal {proposal_id}")
        else:  # ANALYZE
            proposal.status = ProposalStatus.VOTING
            proposal.voting_starts_at = int(time.time())
            proposal.voting_ends_at = proposal.voting_starts_at + (
                VOTING_PERIOD_DAYS * 86400
            )
            print(f"📊 Sophia ANALYZED proposal {proposal_id}: {rationale}")

        return evaluation

    def vote(
        self,
        proposal_id: str,
        voter: WalletAddress,
        support: bool,
        token_balance: Decimal,
    ) -> Vote:
        """
        Cast a vote on a proposal.

        Args:
            proposal_id: Proposal to vote on
            voter: Voting wallet
            support: True for yes, False for no
            token_balance: Voter's token balance (for weighting)

        Returns:
            Vote object
        """
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        if proposal.status != ProposalStatus.VOTING:
            raise ValueError(f"Proposal not in voting phase: {proposal.status}")

        current_time = int(time.time())
        if proposal.voting_ends_at and current_time > proposal.voting_ends_at:
            raise ValueError("Voting period has ended")

        # Check for existing vote
        existing = [v for v in proposal.votes if v.voter == voter]
        if existing:
            raise ValueError("Already voted on this proposal")

        # Calculate voting weight (token + reputation weighted)
        reputation = self.reputations.get(voter.address)
        rep_bonus = (reputation.score / 100.0) if reputation else 0.5
        weight = token_balance * Decimal(str(1 + rep_bonus * 0.2))

        # Include delegated votes
        delegated_weight = self._get_delegated_weight(voter, current_time)
        total_weight = weight + delegated_weight

        vote = Vote(
            voter=voter,
            support=support,
            weight=total_weight,
            timestamp=current_time,
        )

        proposal.votes.append(vote)

        # Update reputation
        self._update_reputation(voter, activity_type="vote")

        return vote

    def finalize_proposal(self, proposal_id: str) -> ProposalStatus:
        """
        Finalize a proposal after voting period ends.

        Args:
            proposal_id: Proposal to finalize

        Returns:
            Final status (PASSED, REJECTED, or current status)
        """
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        if proposal.status != ProposalStatus.VOTING:
            return proposal.status

        current_time = int(time.time())
        if proposal.voting_ends_at and current_time < proposal.voting_ends_at:
            return proposal.status  # Still voting

        # Check quorum
        participation = float(proposal.total_votes) / self.total_supply
        if participation < QUORUM_PERCENTAGE:
            proposal.status = ProposalStatus.REJECTED
            print(f"❌ Proposal {proposal_id} rejected: quorum not met "
                  f"({participation:.1%} < {QUORUM_PERCENTAGE:.0%})")
            return proposal.status

        # Check approval
        if proposal.approval_percentage > 0.5:
            proposal.status = ProposalStatus.PASSED
            print(f"✅ Proposal {proposal_id} PASSED with "
                  f"{proposal.approval_percentage:.1%} approval")

            # Update reputation based on Sophia alignment
            self._update_sophia_alignment(proposal)
        else:
            proposal.status = ProposalStatus.REJECTED
            print(f"❌ Proposal {proposal_id} rejected: "
                  f"{proposal.approval_percentage:.1%} approval")

        return proposal.status

    def execute_proposal(self, proposal_id: str) -> bool:
        """
        Execute a passed proposal (RIP-0005).

        Args:
            proposal_id: Proposal to execute

        Returns:
            True if executed, False otherwise
        """
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        if proposal.status != ProposalStatus.PASSED:
            raise ValueError(f"Cannot execute: status is {proposal.status}")

        # Vetoed proposals cannot execute
        if (proposal.sophia_evaluation and
            proposal.sophia_evaluation.decision == SophiaDecision.VETO):
            raise ValueError("Vetoed proposals cannot be executed")

        # Execute contract if specified
        if proposal.contract_hash:
            # Verify contract alignment before execution
            print(f"🔗 Executing contract {proposal.contract_hash}")

        proposal.status = ProposalStatus.EXECUTED
        proposal.executed_at = int(time.time())
        proposal.execution_tx_hash = hashlib.sha256(
            f"{proposal_id}:{proposal.executed_at}".encode()
        ).hexdigest()

        print(f"⚡ Proposal {proposal_id} executed at block height [N]")
        return True

    def delegate_voting_power(
        self,
        from_wallet: WalletAddress,
        to_wallet: WalletAddress,
        weight: Decimal,
        duration_days: Optional[int] = None,
    ) -> Delegation:
        """
        Delegate voting power to another wallet (RIP-0006).

        Args:
            from_wallet: Delegating wallet
            to_wallet: Receiving wallet
            weight: Percentage of voting power (0-1)
            duration_days: Optional delegation duration

        Returns:
            Delegation object
        """
        if weight < 0 or weight > 1:
            raise ValueError("Delegation weight must be between 0 and 1")

        current_time = int(time.time())
        expires_at = None
        if duration_days:
            expires_at = current_time + (duration_days * 86400)

        delegation = Delegation(
            from_wallet=from_wallet,
            to_wallet=to_wallet,
            weight=weight,
            created_at=current_time,
            expires_at=expires_at,
        )

        key = to_wallet.address
        if key not in self.delegations:
            self.delegations[key] = []
        self.delegations[key].append(delegation)

        return delegation

    def _get_delegated_weight(
        self, wallet: WalletAddress, current_time: int
    ) -> Decimal:
        """Get total delegated voting weight for a wallet"""
        delegations = self.delegations.get(wallet.address, [])
        total = Decimal("0")
        for d in delegations:
            if d.is_active(current_time):
                total += d.weight
        return total

    def _update_reputation(self, wallet: WalletAddress, activity_type: str):
        """Update wallet reputation based on activity"""
        key = wallet.address
        if key not in self.reputations:
            self.reputations[key] = NodeReputation(
                wallet=wallet,
                last_activity=int(time.time()),
            )

        rep = self.reputations[key]
        rep.participation_count += 1
        rep.last_activity = int(time.time())

        # Small reputation boost for participation
        if activity_type == "vote":
            rep.score = min(100, rep.score + 0.5)
        elif activity_type == "propose":
            rep.score = min(100, rep.score + 1.0)

    def _update_sophia_alignment(self, proposal: Proposal):
        """Update voter reputations based on Sophia alignment"""
        if not proposal.sophia_evaluation:
            return

        sophia_decision = proposal.sophia_evaluation.decision
        if sophia_decision == SophiaDecision.ANALYZE:
            return  # Neutral, no alignment update

        # Sophia endorsed = yes is aligned, Sophia vetoed = no is aligned
        sophia_supported = sophia_decision == SophiaDecision.ENDORSE

        for vote in proposal.votes:
            voted_with_sophia = vote.support == sophia_supported
            rep = self.reputations.get(vote.voter.address)
            if rep:
                rep.update_alignment(voted_with_sophia)

    def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        """Get a proposal by ID"""
        return self.proposals.get(proposal_id)

    def get_active_proposals(self) -> List[Proposal]:
        """Get all proposals currently in voting"""
        return [
            p for p in self.proposals.values()
            if p.status == ProposalStatus.VOTING
        ]

    def get_all_proposals(self) -> List[Proposal]:
        """Get all proposals"""
        return list(self.proposals.values())
