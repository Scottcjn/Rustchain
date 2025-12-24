//! RustChain Governance (RIP-0002, RIP-0005, RIP-0006)
//!
//! Hybrid human + Sophia AI governance system implementing:
//! - Proposal creation and voting
//! - Sophia AI evaluation (Endorse/Veto/Analyze)
//! - Token-weighted and reputation-weighted voting
//! - Smart contract binding layer
//! - Delegation framework

use crate::core_types::{WalletAddress, TokenAmount};
use serde::{Deserialize, Serialize};
use sha2::{Sha256, Digest};
use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};

// =============================================================================
// Constants
// =============================================================================

/// Voting period in seconds (7 days)
pub const VOTING_PERIOD_SECONDS: u64 = 7 * 24 * 60 * 60;

/// Minimum participation for quorum (33%)
pub const QUORUM_PERCENTAGE: f64 = 0.33;

/// Execution delay in blocks after passing
pub const EXECUTION_DELAY_BLOCKS: u64 = 3;

/// Weekly reputation decay rate (5%)
pub const REPUTATION_DECAY_WEEKLY: f64 = 0.05;

// =============================================================================
// Enums
// =============================================================================

/// Proposal lifecycle status
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ProposalStatus {
    /// Initial draft state
    Draft,
    /// Submitted for review
    Submitted,
    /// Under Sophia AI review
    SophiaReview,
    /// Open for voting
    Voting,
    /// Passed by vote
    Passed,
    /// Rejected by vote or quorum failure
    Rejected,
    /// Vetoed by Sophia
    Vetoed,
    /// Successfully executed
    Executed,
    /// Expired without action
    Expired,
}

/// Types of governance proposals
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ProposalType {
    /// Change blockchain parameters
    ParameterChange,
    /// Monetary policy updates
    MonetaryPolicy,
    /// Protocol upgrades
    ProtocolUpgrade,
    /// Validator set changes
    ValidatorChange,
    /// Smart contract deployment/updates
    SmartContract,
    /// Community initiatives
    Community,
}

/// Sophia AI evaluation decision
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SophiaDecision {
    /// Awaiting evaluation
    Pending,
    /// Sophia endorses - boosts support probability
    Endorse,
    /// Sophia veto - locks the proposal
    Veto,
    /// Neutral analysis - logs public rationale
    Analyze,
}

// =============================================================================
// Data Structures
// =============================================================================

/// A single vote on a proposal
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Vote {
    /// Voter's wallet address
    pub voter: WalletAddress,
    /// Support (true) or oppose (false)
    pub support: bool,
    /// Calculated vote weight
    pub weight: u64,
    /// Timestamp of vote
    pub timestamp: u64,
    /// Optional delegation source
    pub delegation_from: Option<WalletAddress>,
}

/// Sophia AI's evaluation of a proposal
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SophiaEvaluation {
    /// Decision outcome
    pub decision: SophiaDecision,
    /// Public rationale
    pub rationale: String,
    /// Feasibility score (0.0 - 1.0)
    pub feasibility_score: f64,
    /// Risk assessment level
    pub risk_level: RiskLevel,
    /// Related precedent proposal IDs
    pub aligned_precedent: Vec<String>,
    /// Evaluation timestamp
    pub timestamp: u64,
}

/// Risk level assessment
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum RiskLevel {
    Low,
    Medium,
    High,
}

/// A governance proposal
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Proposal {
    /// Unique proposal ID (e.g., "RCP-0001")
    pub id: String,
    /// Proposal title
    pub title: String,
    /// Detailed description
    pub description: String,
    /// Type of proposal
    pub proposal_type: ProposalType,
    /// Proposer's wallet
    pub proposer: WalletAddress,
    /// Creation timestamp
    pub created_at: u64,
    /// Current status
    pub status: ProposalStatus,

    // Contract binding (RIP-0005)
    /// Optional contract hash to execute
    pub contract_hash: Option<String>,
    /// Requires multi-signature
    pub requires_multi_sig: bool,
    /// Blocks to wait before execution
    pub timelock_blocks: u64,
    /// Auto-expire if not executed
    pub auto_expire: bool,

    // Voting data
    /// All votes cast
    pub votes: Vec<Vote>,
    /// When voting begins
    pub voting_starts_at: Option<u64>,
    /// When voting ends
    pub voting_ends_at: Option<u64>,

    // Sophia evaluation (RIP-0002)
    /// Sophia's evaluation
    pub sophia_evaluation: Option<SophiaEvaluation>,

    // Execution
    /// Execution timestamp
    pub executed_at: Option<u64>,
    /// Execution transaction hash
    pub execution_tx_hash: Option<String>,
}

impl Proposal {
    /// Create a new proposal
    pub fn new(
        id: String,
        title: String,
        description: String,
        proposal_type: ProposalType,
        proposer: WalletAddress,
    ) -> Self {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        Self {
            id,
            title,
            description,
            proposal_type,
            proposer,
            created_at: now,
            status: ProposalStatus::Submitted,
            contract_hash: None,
            requires_multi_sig: false,
            timelock_blocks: EXECUTION_DELAY_BLOCKS,
            auto_expire: true,
            votes: Vec::new(),
            voting_starts_at: None,
            voting_ends_at: None,
            sophia_evaluation: None,
            executed_at: None,
            execution_tx_hash: None,
        }
    }

    /// Calculate total yes votes
    pub fn yes_votes(&self) -> u64 {
        self.votes.iter().filter(|v| v.support).map(|v| v.weight).sum()
    }

    /// Calculate total no votes
    pub fn no_votes(&self) -> u64 {
        self.votes.iter().filter(|v| !v.support).map(|v| v.weight).sum()
    }

    /// Calculate total votes
    pub fn total_votes(&self) -> u64 {
        self.votes.iter().map(|v| v.weight).sum()
    }

    /// Calculate approval percentage
    pub fn approval_percentage(&self) -> f64 {
        let total = self.total_votes();
        if total == 0 {
            return 0.0;
        }
        self.yes_votes() as f64 / total as f64
    }

    /// Check if voter has already voted
    pub fn has_voted(&self, voter: &WalletAddress) -> bool {
        self.votes.iter().any(|v| &v.voter == voter)
    }
}

// =============================================================================
// Reputation System (RIP-0006)
// =============================================================================

/// Node/wallet reputation score
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeReputation {
    /// Wallet address
    pub wallet: WalletAddress,
    /// Reputation score (0-100, starts at 50)
    pub score: f64,
    /// Number of governance participations
    pub participation_count: u32,
    /// Number of correct outcome predictions
    pub correct_predictions: u32,
    /// Uptime contribution factor
    pub uptime_contribution: f64,
    /// Correlation with Sophia decisions
    pub sophia_alignment: f64,
    /// Last activity timestamp
    pub last_activity: u64,
}

impl NodeReputation {
    /// Create new reputation entry
    pub fn new(wallet: WalletAddress) -> Self {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        Self {
            wallet,
            score: 50.0,
            participation_count: 0,
            correct_predictions: 0,
            uptime_contribution: 0.0,
            sophia_alignment: 0.0,
            last_activity: now,
        }
    }

    /// Apply decay for inactivity
    pub fn apply_decay(&mut self, weeks_inactive: u32) {
        let decay_factor = (1.0 - REPUTATION_DECAY_WEEKLY).powi(weeks_inactive as i32);
        self.score *= decay_factor;
    }

    /// Update Sophia alignment score
    pub fn update_alignment(&mut self, voted_with_sophia: bool) {
        let weight = 0.1;
        if voted_with_sophia {
            self.sophia_alignment = (self.sophia_alignment + weight).min(1.0);
        } else {
            self.sophia_alignment = (self.sophia_alignment - weight).max(0.0);
        }
    }

    /// Record participation
    pub fn record_participation(&mut self, activity_type: &str) {
        self.participation_count += 1;
        self.last_activity = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        // Small reputation boost for participation
        match activity_type {
            "vote" => self.score = (self.score + 0.5).min(100.0),
            "propose" => self.score = (self.score + 1.0).min(100.0),
            _ => {}
        }
    }
}

/// Voting power delegation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Delegation {
    /// Delegating wallet
    pub from_wallet: WalletAddress,
    /// Receiving wallet
    pub to_wallet: WalletAddress,
    /// Percentage of voting power (0.0 - 1.0)
    pub weight: f64,
    /// Creation timestamp
    pub created_at: u64,
    /// Optional expiration timestamp
    pub expires_at: Option<u64>,
}

impl Delegation {
    /// Check if delegation is still active
    pub fn is_active(&self, current_time: u64) -> bool {
        match self.expires_at {
            Some(expires) if current_time > expires => false,
            _ => true,
        }
    }
}

// =============================================================================
// Governance Engine
// =============================================================================

/// Main governance engine implementing RIP-0002, RIP-0005, RIP-0006
pub struct GovernanceEngine {
    /// All proposals by ID
    proposals: HashMap<String, Proposal>,
    /// Reputation scores by wallet address
    reputations: HashMap<String, NodeReputation>,
    /// Delegations by receiving wallet address
    delegations: HashMap<String, Vec<Delegation>>,
    /// Total token supply for quorum calculation
    total_supply: u64,
    /// Counter for proposal IDs
    proposal_counter: u32,
}

impl GovernanceEngine {
    /// Create new governance engine
    pub fn new(total_supply: u64) -> Self {
        Self {
            proposals: HashMap::new(),
            reputations: HashMap::new(),
            delegations: HashMap::new(),
            total_supply,
            proposal_counter: 0,
        }
    }

    /// Create a new governance proposal
    pub fn create_proposal(
        &mut self,
        title: String,
        description: String,
        proposal_type: ProposalType,
        proposer: WalletAddress,
        contract_hash: Option<String>,
    ) -> &Proposal {
        self.proposal_counter += 1;
        let proposal_id = format!("RCP-{:04}", self.proposal_counter);

        let mut proposal = Proposal::new(
            proposal_id.clone(),
            title,
            description,
            proposal_type,
            proposer.clone(),
        );
        proposal.contract_hash = contract_hash;

        // Update proposer reputation
        self.update_reputation(&proposer, "propose");

        self.proposals.insert(proposal_id.clone(), proposal);
        self.proposals.get(&proposal_id).unwrap()
    }

    /// Record Sophia AI's evaluation (RIP-0002)
    pub fn sophia_evaluate(
        &mut self,
        proposal_id: &str,
        decision: SophiaDecision,
        rationale: String,
        feasibility_score: f64,
        risk_level: RiskLevel,
    ) -> Result<&SophiaEvaluation, GovernanceError> {
        let proposal = self.proposals.get_mut(proposal_id)
            .ok_or(GovernanceError::ProposalNotFound)?;

        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        let evaluation = SophiaEvaluation {
            decision,
            rationale: rationale.clone(),
            feasibility_score,
            risk_level,
            aligned_precedent: Vec::new(),
            timestamp: now,
        };

        proposal.sophia_evaluation = Some(evaluation);

        match decision {
            SophiaDecision::Veto => {
                proposal.status = ProposalStatus::Vetoed;
            }
            SophiaDecision::Endorse | SophiaDecision::Analyze => {
                proposal.status = ProposalStatus::Voting;
                proposal.voting_starts_at = Some(now);
                proposal.voting_ends_at = Some(now + VOTING_PERIOD_SECONDS);
            }
            SophiaDecision::Pending => {}
        }

        Ok(proposal.sophia_evaluation.as_ref().unwrap())
    }

    /// Cast a vote on a proposal
    pub fn vote(
        &mut self,
        proposal_id: &str,
        voter: WalletAddress,
        support: bool,
        token_balance: u64,
    ) -> Result<&Vote, GovernanceError> {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        // Validate proposal exists and is in voting state
        let proposal = self.proposals.get(proposal_id)
            .ok_or(GovernanceError::ProposalNotFound)?;

        if proposal.status != ProposalStatus::Voting {
            return Err(GovernanceError::NotInVotingPhase);
        }

        if let Some(ends_at) = proposal.voting_ends_at {
            if now > ends_at {
                return Err(GovernanceError::VotingPeriodEnded);
            }
        }

        if proposal.has_voted(&voter) {
            return Err(GovernanceError::AlreadyVoted);
        }

        // Calculate voting weight (token + reputation weighted)
        let reputation = self.reputations.get(&voter.address);
        let rep_bonus = reputation.map(|r| r.score / 100.0).unwrap_or(0.5);
        let base_weight = (token_balance as f64 * (1.0 + rep_bonus * 0.2)) as u64;

        // Include delegated votes
        let delegated_weight = self.get_delegated_weight(&voter, now);
        let total_weight = base_weight + delegated_weight;

        let vote = Vote {
            voter: voter.clone(),
            support,
            weight: total_weight,
            timestamp: now,
            delegation_from: None,
        };

        // Mutably borrow to add vote
        let proposal = self.proposals.get_mut(proposal_id).unwrap();
        proposal.votes.push(vote);

        // Update reputation
        self.update_reputation(&voter, "vote");

        let proposal = self.proposals.get(proposal_id).unwrap();
        Ok(proposal.votes.last().unwrap())
    }

    /// Finalize a proposal after voting period ends
    pub fn finalize_proposal(&mut self, proposal_id: &str) -> Result<ProposalStatus, GovernanceError> {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        let proposal = self.proposals.get(proposal_id)
            .ok_or(GovernanceError::ProposalNotFound)?;

        if proposal.status != ProposalStatus::Voting {
            return Ok(proposal.status);
        }

        if let Some(ends_at) = proposal.voting_ends_at {
            if now < ends_at {
                return Ok(proposal.status); // Still voting
            }
        }

        // Check quorum
        let participation = proposal.total_votes() as f64 / self.total_supply as f64;

        let proposal = self.proposals.get_mut(proposal_id).unwrap();

        if participation < QUORUM_PERCENTAGE {
            proposal.status = ProposalStatus::Rejected;
            return Ok(proposal.status);
        }

        // Check approval
        if proposal.approval_percentage() > 0.5 {
            proposal.status = ProposalStatus::Passed;
            // Update Sophia alignment for voters
            self.update_sophia_alignment(proposal_id);
        } else {
            proposal.status = ProposalStatus::Rejected;
        }

        Ok(self.proposals.get(proposal_id).unwrap().status)
    }

    /// Execute a passed proposal (RIP-0005)
    pub fn execute_proposal(&mut self, proposal_id: &str) -> Result<String, GovernanceError> {
        let proposal = self.proposals.get(proposal_id)
            .ok_or(GovernanceError::ProposalNotFound)?;

        if proposal.status != ProposalStatus::Passed {
            return Err(GovernanceError::CannotExecute);
        }

        // Check for veto
        if let Some(ref eval) = proposal.sophia_evaluation {
            if eval.decision == SophiaDecision::Veto {
                return Err(GovernanceError::VetoedProposal);
            }
        }

        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        // Generate execution hash
        let tx_hash = {
            let mut hasher = Sha256::new();
            hasher.update(format!("{}:{}", proposal_id, now).as_bytes());
            hex::encode(hasher.finalize())
        };

        let proposal = self.proposals.get_mut(proposal_id).unwrap();
        proposal.status = ProposalStatus::Executed;
        proposal.executed_at = Some(now);
        proposal.execution_tx_hash = Some(tx_hash.clone());

        Ok(tx_hash)
    }

    /// Delegate voting power to another wallet (RIP-0006)
    pub fn delegate_voting_power(
        &mut self,
        from_wallet: WalletAddress,
        to_wallet: WalletAddress,
        weight: f64,
        duration_days: Option<u64>,
    ) -> Result<&Delegation, GovernanceError> {
        if weight < 0.0 || weight > 1.0 {
            return Err(GovernanceError::InvalidDelegationWeight);
        }

        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        let expires_at = duration_days.map(|days| now + days * 86400);

        let delegation = Delegation {
            from_wallet,
            to_wallet: to_wallet.clone(),
            weight,
            created_at: now,
            expires_at,
        };

        let key = to_wallet.address.clone();
        self.delegations.entry(key.clone()).or_insert_with(Vec::new).push(delegation);

        Ok(self.delegations.get(&key).unwrap().last().unwrap())
    }

    /// Get total delegated voting weight for a wallet
    fn get_delegated_weight(&self, wallet: &WalletAddress, current_time: u64) -> u64 {
        self.delegations
            .get(&wallet.address)
            .map(|delegations| {
                delegations
                    .iter()
                    .filter(|d| d.is_active(current_time))
                    .map(|d| (d.weight * 100.0) as u64) // Scale weight
                    .sum()
            })
            .unwrap_or(0)
    }

    /// Update wallet reputation
    fn update_reputation(&mut self, wallet: &WalletAddress, activity_type: &str) {
        let rep = self.reputations
            .entry(wallet.address.clone())
            .or_insert_with(|| NodeReputation::new(wallet.clone()));
        rep.record_participation(activity_type);
    }

    /// Update Sophia alignment for voters after proposal finishes
    fn update_sophia_alignment(&mut self, proposal_id: &str) {
        let proposal = match self.proposals.get(proposal_id) {
            Some(p) => p.clone(),
            None => return,
        };

        let sophia_decision = match &proposal.sophia_evaluation {
            Some(eval) => eval.decision,
            None => return,
        };

        if sophia_decision == SophiaDecision::Analyze {
            return; // Neutral, no alignment update
        }

        let sophia_supported = sophia_decision == SophiaDecision::Endorse;

        for vote in &proposal.votes {
            let voted_with_sophia = vote.support == sophia_supported;
            if let Some(rep) = self.reputations.get_mut(&vote.voter.address) {
                rep.update_alignment(voted_with_sophia);
            }
        }
    }

    /// Get a proposal by ID
    pub fn get_proposal(&self, proposal_id: &str) -> Option<&Proposal> {
        self.proposals.get(proposal_id)
    }

    /// Get all active (voting) proposals
    pub fn get_active_proposals(&self) -> Vec<&Proposal> {
        self.proposals
            .values()
            .filter(|p| p.status == ProposalStatus::Voting)
            .collect()
    }

    /// Get all proposals
    pub fn get_all_proposals(&self) -> Vec<&Proposal> {
        self.proposals.values().collect()
    }
}

// =============================================================================
// Errors
// =============================================================================

/// Governance operation errors
#[derive(Debug, Clone)]
pub enum GovernanceError {
    /// Proposal not found
    ProposalNotFound,
    /// Proposal not in voting phase
    NotInVotingPhase,
    /// Voting period has ended
    VotingPeriodEnded,
    /// Voter has already voted
    AlreadyVoted,
    /// Cannot execute proposal
    CannotExecute,
    /// Proposal was vetoed by Sophia
    VetoedProposal,
    /// Invalid delegation weight
    InvalidDelegationWeight,
}

impl std::fmt::Display for GovernanceError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::ProposalNotFound => write!(f, "Proposal not found"),
            Self::NotInVotingPhase => write!(f, "Proposal is not in voting phase"),
            Self::VotingPeriodEnded => write!(f, "Voting period has ended"),
            Self::AlreadyVoted => write!(f, "Already voted on this proposal"),
            Self::CannotExecute => write!(f, "Cannot execute proposal in current state"),
            Self::VetoedProposal => write!(f, "Vetoed proposals cannot be executed"),
            Self::InvalidDelegationWeight => write!(f, "Delegation weight must be between 0 and 1"),
        }
    }
}

impl std::error::Error for GovernanceError {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_proposal() {
        let mut engine = GovernanceEngine::new(8_388_608);
        let wallet = WalletAddress::new("RTC1TestWallet".to_string());

        let proposal = engine.create_proposal(
            "Test Proposal".to_string(),
            "A test proposal".to_string(),
            ProposalType::Community,
            wallet,
            None,
        );

        assert_eq!(proposal.id, "RCP-0001");
        assert_eq!(proposal.status, ProposalStatus::Submitted);
    }

    #[test]
    fn test_sophia_veto() {
        let mut engine = GovernanceEngine::new(8_388_608);
        let wallet = WalletAddress::new("RTC1TestWallet".to_string());

        engine.create_proposal(
            "Bad Proposal".to_string(),
            "This should be vetoed".to_string(),
            ProposalType::MonetaryPolicy,
            wallet,
            None,
        );

        engine.sophia_evaluate(
            "RCP-0001",
            SophiaDecision::Veto,
            "This proposal is harmful".to_string(),
            0.1,
            RiskLevel::High,
        ).unwrap();

        let proposal = engine.get_proposal("RCP-0001").unwrap();
        assert_eq!(proposal.status, ProposalStatus::Vetoed);
    }

    #[test]
    fn test_voting() {
        let mut engine = GovernanceEngine::new(8_388_608);
        let proposer = WalletAddress::new("RTC1Proposer".to_string());
        let voter = WalletAddress::new("RTC1Voter".to_string());

        engine.create_proposal(
            "Good Proposal".to_string(),
            "This should pass".to_string(),
            ProposalType::Community,
            proposer,
            None,
        );

        engine.sophia_evaluate(
            "RCP-0001",
            SophiaDecision::Endorse,
            "This proposal benefits the community".to_string(),
            0.9,
            RiskLevel::Low,
        ).unwrap();

        engine.vote("RCP-0001", voter, true, 1000).unwrap();

        let proposal = engine.get_proposal("RCP-0001").unwrap();
        assert_eq!(proposal.yes_votes(), 1100); // 1000 * (1 + 0.5 * 0.2) = 1100
    }
}
