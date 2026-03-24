"""
RustChain Governance Proposals (RIP-0002, RIP-0005, RIP-0006)
=============================================================

Proposal lifecycle and voting system with Sophia AI integration.

Lifecycle:
1. Draft -> Submitted
2. Sophia Review (Endorse/Veto/Analyze)
3. Voting Period (7 days)
4. Passed/Rejected/Vetoed
5. Execution (if passed)
"""

import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum, auto
from decimal import Decimal

from ..config.chain_params import (
    VOTING_PERIOD_DAYS,
    QUORUM_PERCENTAGE,
    EXECUTION_DELAY_BLOCKS,
    REPUTATION_DECAY_WEEKLY,
    TOTAL_SUPPLY,
)


# =============================================================================
# Enums
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
    """Types of governance proposals"""
    PARAMETER_CHANGE = auto()
    MONETARY_POLICY = auto()
    PROTOCOL_UPGRADE = auto()
    VALIDATOR_CHANGE = auto()
    SMART_CONTRACT = auto()
    COMMUNITY = auto()


class SophiaDecision(Enum):
    """Sophia AI evaluation decisions"""
    PENDING = auto()
    ENDORSE = auto()  # Boosts support probability
    VETO = auto()      # Locks the proposal
    ANALYZE = auto()   # Neutral, logs public rationale


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class Vote:
    """A single vote on a proposal"""
    voter: str
    support: bool
    weight: int
    timestamp: int
    delegation_from: Optional[str] = None


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
    proposer: str
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

    # Sophia evaluation
    sophia_evaluation: Optional[SophiaEvaluation] = None

    # Execution
    executed_at: Optional[int] = None
    execution_tx_hash: Optional[str] = None

    @property
    def yes_votes(self) -> int:
        return sum(v.weight for v in self.votes if v.support)

    @property
    def no_votes(self) -> int:
        return sum(v.weight for v in self.votes if not v.support)

    @property
    def total_votes(self) -> int:
        return sum(v.weight for v in self.votes)

    @property
    def approval_percentage(self) -> float:
        total = self.total_votes
        if total == 0:
            return 0.0
        return self.yes_votes / total

    def has_voted(self, voter: str) -> bool:
        return any(v.voter == voter for v in self.votes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "type": self.proposal_type.name,
            "proposer": self.proposer,
            "status": self.status.name,
            "created_at": self.created_at,
            "contract_hash": self.contract_hash,
            "yes_votes": self.yes_votes,
            "no_votes": self.no_votes,
            "total_votes": self.total_votes,
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
    wallet: str
    score: float = 50.0  # Start neutral (0-100)
    participation_count: int = 0
    correct_predictions: int = 0
    uptime_contribution: float = 0.0
    sophia_alignment: float = 0.0
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
    from_wallet: str
    to_wallet: str
    weight: float  # Percentage (0.0 - 1.0)
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

    def __init__(self, total_supply: int = TOTAL_SUPPLY):
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
        proposer: str,
        contract_hash: Optional[str] = None,
    ) -> Proposal:
        """Create a new governance proposal."""
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
        self._update_reputation(proposer, "propose")

        return proposal

    def sophia_evaluate(
        self,
        proposal_id: str,
        decision: SophiaDecision,
        rationale: str,
        feasibility_score: float = 0.5,
        risk_level: str = "medium",
    ) -> SophiaEvaluation:
        """Record Sophia AI's evaluation (RIP-0002)."""
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
        now = int(time.time())

        if decision == SophiaDecision.VETO:
            proposal.status = ProposalStatus.VETOED
            print(f"SOPHIA VETO: {proposal_id} - {rationale}")
        elif decision == SophiaDecision.ENDORSE:
            proposal.status = ProposalStatus.VOTING
            proposal.voting_starts_at = now
            proposal.voting_ends_at = now + (VOTING_PERIOD_DAYS * 86400)
            print(f"SOPHIA ENDORSE: {proposal_id}")
        else:  # ANALYZE
            proposal.status = ProposalStatus.VOTING
            proposal.voting_starts_at = now
            proposal.voting_ends_at = now + (VOTING_PERIOD_DAYS * 86400)
            print(f"SOPHIA ANALYZE: {proposal_id} - {rationale}")

        return evaluation

    def vote(
        self,
        proposal_id: str,
        voter: str,
        support: bool,
        token_balance: int,
    ) -> Vote:
        """Cast a vote on a proposal."""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        if proposal.status != ProposalStatus.VOTING:
            raise ValueError(f"Proposal not in voting phase: {proposal.status}")

        now = int(time.time())
        if proposal.voting_ends_at and now > proposal.voting_ends_at:
            raise ValueError("Voting period has ended")

        if proposal.has_voted(voter):
            raise ValueError("Already voted on this proposal")

        # Calculate voting weight
        reputation = self.reputations.get(voter)
        rep_bonus = (reputation.score / 100.0) if reputation else 0.5
        base_weight = int(token_balance * (1 + rep_bonus * 0.2))

        # Include delegated votes
        delegated_weight = self._get_delegated_weight(voter, now)
        total_weight = base_weight + delegated_weight

        vote = Vote(
            voter=voter,
            support=support,
            weight=total_weight,
            timestamp=now,
        )

        proposal.votes.append(vote)
        self._update_reputation(voter, "vote")

        return vote

    def finalize_proposal(self, proposal_id: str) -> ProposalStatus:
        """Finalize a proposal after voting period ends."""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        if proposal.status != ProposalStatus.VOTING:
            return proposal.status

        now = int(time.time())
        if proposal.voting_ends_at and now < proposal.voting_ends_at:
            return proposal.status  # Still voting

        # Check quorum
        participation = proposal.total_votes / self.total_supply

        if participation < QUORUM_PERCENTAGE:
            proposal.status = ProposalStatus.REJECTED
            print(f"REJECTED (quorum): {proposal_id} - {participation:.1%} < {QUORUM_PERCENTAGE:.0%}")
            return proposal.status

        # Check approval
        if proposal.approval_percentage > 0.5:
            proposal.status = ProposalStatus.PASSED
            print(f"PASSED: {proposal_id} - {proposal.approval_percentage:.1%} approval")
            self._update_sophia_alignment(proposal)
        else:
            proposal.status = ProposalStatus.REJECTED
            print(f"REJECTED: {proposal_id} - {proposal.approval_percentage:.1%} approval")

        return proposal.status

    def execute_proposal(self, proposal_id: str) -> str:
        """Execute a passed proposal (RIP-0005)."""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        if proposal.status != ProposalStatus.PASSED:
            raise ValueError(f"Cannot execute: status is {proposal.status}")

        # Vetoed proposals cannot execute
        if (proposal.sophia_evaluation and
            proposal.sophia_evaluation.decision == SophiaDecision.VETO):
            raise ValueError("Vetoed proposals cannot be executed")

        now = int(time.time())
        tx_hash = hashlib.sha256(f"{proposal_id}:{now}".encode()).hexdigest()

        proposal.status = ProposalStatus.EXECUTED
        proposal.executed_at = now
        proposal.execution_tx_hash = tx_hash

        print(f"EXECUTED: {proposal_id} - TX: {tx_hash[:16]}...")
        return tx_hash

    def delegate_voting_power(
        self,
        from_wallet: str,
        to_wallet: str,
        weight: float,
        duration_days: Optional[int] = None,
    ) -> Delegation:
        """Delegate voting power to another wallet (RIP-0006)."""
        if weight < 0 or weight > 1:
            raise ValueError("Delegation weight must be between 0 and 1")

        now = int(time.time())
        expires_at = now + (duration_days * 86400) if duration_days else None

        delegation = Delegation(
            from_wallet=from_wallet,
            to_wallet=to_wallet,
            weight=weight,
            created_at=now,
            expires_at=expires_at,
        )

        if to_wallet not in self.delegations:
            self.delegations[to_wallet] = []
        self.delegations[to_wallet].append(delegation)

        return delegation

    def _get_delegated_weight(self, wallet: str, current_time: int) -> int:
        """Get total delegated voting weight for a wallet."""
        delegations = self.delegations.get(wallet, [])
        total = 0
        for d in delegations:
            if d.is_active(current_time):
                total += int(d.weight * 100)  # Scale weight
        return total

    def _update_reputation(self, wallet: str, activity_type: str):
        """Update wallet reputation based on activity."""
        if wallet not in self.reputations:
            self.reputations[wallet] = NodeReputation(
                wallet=wallet,
                last_activity=int(time.time()),
            )

        rep = self.reputations[wallet]
        rep.participation_count += 1
        rep.last_activity = int(time.time())

        if activity_type == "vote":
            rep.score = min(100, rep.score + 0.5)
        elif activity_type == "propose":
            rep.score = min(100, rep.score + 1.0)

    def _update_sophia_alignment(self, proposal: Proposal):
        """Update voter reputations based on Sophia alignment."""
        if not proposal.sophia_evaluation:
            return

        sophia_decision = proposal.sophia_evaluation.decision
        if sophia_decision == SophiaDecision.ANALYZE:
            return

        sophia_supported = sophia_decision == SophiaDecision.ENDORSE

        for vote in proposal.votes:
            voted_with_sophia = vote.support == sophia_supported
            rep = self.reputations.get(vote.voter)
            if rep:
                rep.update_alignment(voted_with_sophia)

    def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        """Get a proposal by ID."""
        return self.proposals.get(proposal_id)

    def get_active_proposals(self) -> List[Proposal]:
        """Get all proposals currently in voting."""
        return [
            p for p in self.proposals.values()
            if p.status == ProposalStatus.VOTING
        ]

    def get_all_proposals(self) -> List[Proposal]:
        """Get all proposals."""
        return list(self.proposals.values())


# =============================================================================
# Sophia AI Interface
# =============================================================================

class SophiaEvaluator:
    """
    Interface for Sophia AI proposal evaluation.

    In production, this connects to Sophia's neural network.
    For development, uses rule-based heuristics.
    """

    def __init__(self, governance: GovernanceEngine):
        self.governance = governance

    def evaluate(self, proposal_id: str) -> SophiaEvaluation:
        """
        Evaluate a proposal using Sophia's judgment.

        Factors considered:
        - Proposal type and risk
        - Historical precedent
        - Community sentiment
        - Technical feasibility
        """
        proposal = self.governance.get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        # Rule-based evaluation (placeholder for neural network)
        risk_scores = {
            ProposalType.PARAMETER_CHANGE: 0.3,
            ProposalType.MONETARY_POLICY: 0.7,
            ProposalType.PROTOCOL_UPGRADE: 0.6,
            ProposalType.VALIDATOR_CHANGE: 0.4,
            ProposalType.SMART_CONTRACT: 0.5,
            ProposalType.COMMUNITY: 0.2,
        }

        risk = risk_scores.get(proposal.proposal_type, 0.5)

        # High risk -> more scrutiny
        if risk > 0.6:
            if "emergency" in proposal.title.lower():
                decision = SophiaDecision.ANALYZE
                rationale = "Emergency proposal requires careful review"
            else:
                decision = SophiaDecision.ANALYZE
                rationale = f"High-risk {proposal.proposal_type.name} proposal"
        elif risk > 0.4:
            decision = SophiaDecision.ANALYZE
            rationale = "Moderate impact - community should decide"
        else:
            decision = SophiaDecision.ENDORSE
            rationale = "Low-risk proposal aligned with community values"

        # Apply evaluation
        return self.governance.sophia_evaluate(
            proposal_id=proposal_id,
            decision=decision,
            rationale=rationale,
            feasibility_score=1.0 - risk,
            risk_level="high" if risk > 0.6 else "medium" if risk > 0.3 else "low",
        )


# =============================================================================
# Tests
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("RUSTCHAIN GOVERNANCE ENGINE TEST")
    print("=" * 60)

    engine = GovernanceEngine()
    sophia = SophiaEvaluator(engine)

    # Create proposal
    proposal = engine.create_proposal(
        title="Increase Block Reward",
        description="Proposal to increase block reward from 1.5 to 2.0 RTC",
        proposal_type=ProposalType.MONETARY_POLICY,
        proposer="RTC1TestProposer",
    )

    print(f"\nCreated: {proposal.id} - {proposal.title}")

    # Sophia evaluates
    evaluation = sophia.evaluate(proposal.id)
    print(f"Sophia: {evaluation.decision.name} - {evaluation.rationale}")

    # Cast votes
    if proposal.status == ProposalStatus.VOTING:
        engine.vote(proposal.id, "RTC1Voter1", True, 1000000)
        engine.vote(proposal.id, "RTC1Voter2", True, 500000)
        engine.vote(proposal.id, "RTC1Voter3", False, 300000)

        print(f"\nVotes: {proposal.yes_votes} yes, {proposal.no_votes} no")
        print(f"Approval: {proposal.approval_percentage:.1%}")
