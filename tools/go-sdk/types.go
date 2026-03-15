package rustchain

// HealthResponse is returned by GET /health.
type HealthResponse struct {
	OK            bool    `json:"ok"`
	Version       string  `json:"version"`
	UptimeSeconds float64 `json:"uptime_s"`
	DBRW          bool    `json:"db_rw"`
	BackupAgeHrs  float64 `json:"backup_age_hours,omitempty"`
	TipAgeSlots   int     `json:"tip_age_slots,omitempty"`
}

// ReadinessResponse is returned by GET /ready.
type ReadinessResponse struct {
	Ready   bool   `json:"ready"`
	Version string `json:"version"`
}

// StatsResponse is returned by GET /api/stats.
type StatsResponse struct {
	Version            string   `json:"version"`
	ChainID            string   `json:"chain_id"`
	Epoch              int      `json:"epoch"`
	BlockTime          int      `json:"block_time"`
	TotalMiners        int      `json:"total_miners"`
	TotalBalance       float64  `json:"total_balance"`
	PendingWithdrawals int      `json:"pending_withdrawals"`
	Features           []string `json:"features"`
	Security           []string `json:"security"`
}

// EpochResponse is returned by GET /epoch.
type EpochResponse struct {
	Epoch          int     `json:"epoch"`
	Slot           int     `json:"slot"`
	EpochPot       float64 `json:"epoch_pot"`
	EnrolledMiners int     `json:"enrolled_miners"`
	BlocksPerEpoch int     `json:"blocks_per_epoch"`
	TotalSupplyRTC float64 `json:"total_supply_rtc"`
}

// EnrollRequest is sent to POST /epoch/enroll.
type EnrollRequest struct {
	MinerPubkey string       `json:"miner_pubkey"`
	MinerID     string       `json:"miner_id"`
	Device      EnrollDevice `json:"device"`
}

// EnrollDevice describes the miner hardware for enrollment.
type EnrollDevice struct {
	Family string `json:"family"`
	Arch   string `json:"arch"`
}

// EnrollResponse is returned by POST /epoch/enroll.
type EnrollResponse struct {
	OK                bool    `json:"ok"`
	Epoch             int     `json:"epoch"`
	Weight            float64 `json:"weight"`
	HWWeight          float64 `json:"hw_weight"`
	FingerprintFailed bool    `json:"fingerprint_failed"`
	MinerPK           string  `json:"miner_pk"`
	MinerID           string  `json:"miner_id"`
}

// EligibilityResponse is returned by GET /lottery/eligibility.
type EligibilityResponse struct {
	Eligible bool   `json:"eligible"`
	MinerID  string `json:"miner_id"`
	Slot     int    `json:"slot"`
	Reason   string `json:"reason"`
}

// EpochReward represents a single miner reward entry.
type EpochReward struct {
	MinerID  string  `json:"miner_id"`
	ShareI64 int64   `json:"share_i64"`
	ShareRTC float64 `json:"share_rtc"`
}

// EpochRewardsResponse is returned by GET /rewards/epoch/:epoch.
type EpochRewardsResponse struct {
	Epoch   int           `json:"epoch"`
	Rewards []EpochReward `json:"rewards"`
}

// BalanceResponse is returned by GET /balance/:minerPk.
type BalanceResponse struct {
	MinerPK    string  `json:"miner_pk"`
	BalanceRTC float64 `json:"balance_rtc"`
	AmountI64  int64   `json:"amount_i64"`
}

// WalletBalanceResponse is returned by GET /wallet/balance.
type WalletBalanceResponse struct {
	MinerID   string  `json:"miner_id"`
	AmountI64 int64   `json:"amount_i64"`
	AmountRTC float64 `json:"amount_rtc"`
}

// TransferHistoryEntry represents a single transfer record.
type TransferHistoryEntry struct {
	ID            int     `json:"id"`
	TxID          string  `json:"tx_id"`
	TxHash        string  `json:"tx_hash"`
	FromAddr      string  `json:"from_addr"`
	ToAddr        string  `json:"to_addr"`
	Amount        float64 `json:"amount"`
	AmountI64     int64   `json:"amount_i64"`
	AmountRTC     float64 `json:"amount_rtc"`
	Timestamp     int64   `json:"timestamp"`
	CreatedAt     int64   `json:"created_at"`
	ConfirmedAt   int64   `json:"confirmed_at"`
	ConfirmsAt    int64   `json:"confirms_at"`
	Status        string  `json:"status"`
	Direction     string  `json:"direction"`
	Counterparty  string  `json:"counterparty"`
	Reason        string  `json:"reason"`
	Memo          string  `json:"memo"`
	Confirmations int     `json:"confirmations"`
}

// SignedTransferRequest is sent to POST /wallet/transfer/signed.
type SignedTransferRequest struct {
	FromAddress string  `json:"from_address"`
	ToAddress   string  `json:"to_address"`
	AmountRTC   float64 `json:"amount_rtc"`
	Nonce       string  `json:"nonce"`
	Signature   string  `json:"signature"`
	PublicKey   string  `json:"public_key"`
	Memo        string  `json:"memo,omitempty"`
	ChainID     string  `json:"chain_id,omitempty"`
}

// SignedTransferResponse is returned by POST /wallet/transfer/signed.
type SignedTransferResponse struct {
	OK              bool    `json:"ok"`
	Verified        bool    `json:"verified"`
	SignatureType   string  `json:"signature_type"`
	ReplayProtected bool    `json:"replay_protected"`
	Phase           string  `json:"phase"`
	PendingID       int     `json:"pending_id"`
	TxHash          string  `json:"tx_hash"`
	FromAddress     string  `json:"from_address"`
	ToAddress       string  `json:"to_address"`
	AmountRTC       float64 `json:"amount_rtc"`
	ChainID         string  `json:"chain_id"`
	ConfirmsAt      int64   `json:"confirms_at"`
	ConfirmsInHours float64 `json:"confirms_in_hours"`
	Message         string  `json:"message"`
}

// ResolveWalletResponse is returned by GET /wallet/resolve.
type ResolveWalletResponse struct {
	OK        bool   `json:"ok"`
	BeaconID  string `json:"beacon_id"`
	PubkeyHex string `json:"pubkey_hex"`
	RTCAddr   string `json:"rtc_address"`
	Name      string `json:"name"`
	Status    string `json:"status"`
}

// ChainTipResponse is returned by GET /headers/tip.
type ChainTipResponse struct {
	Slot            int    `json:"slot"`
	Miner           string `json:"miner"`
	TipAge          int    `json:"tip_age"`
	SignaturePrefix string `json:"signature_prefix"`
}

// AttestChallengeResponse is returned by POST /attest/challenge.
type AttestChallengeResponse struct {
	Nonce      string `json:"nonce"`
	ExpiresAt  int64  `json:"expires_at"`
	ServerTime int64  `json:"server_time"`
}

// AttestSubmitRequest is sent to POST /attest/submit.
type AttestSubmitRequest struct {
	Miner       string              `json:"miner"`
	Nonce       string              `json:"nonce"`
	Report      AttestReport        `json:"report"`
	Device      AttestDevice        `json:"device"`
	Signals     AttestSignals       `json:"signals"`
	Fingerprint AttestFingerprint   `json:"fingerprint"`
}

// AttestReport is the hardware attestation report.
type AttestReport struct {
	Nonce          string   `json:"nonce"`
	DeviceModel    string   `json:"device_model"`
	DeviceArch     string   `json:"device_arch"`
	DeviceFamily   string   `json:"device_family"`
	Cores          int      `json:"cores"`
	CPUSerial      string   `json:"cpu_serial"`
	EntropySources []string `json:"entropy_sources"`
	EntropyScore   float64  `json:"entropy_score"`
}

// AttestDevice describes the attesting hardware.
type AttestDevice struct {
	DeviceModel  string `json:"device_model"`
	DeviceArch   string `json:"device_arch"`
	DeviceFamily string `json:"device_family"`
	Cores        int    `json:"cores"`
}

// AttestSignals carries MAC addresses for OUI validation.
type AttestSignals struct {
	MACs []string `json:"macs"`
}

// AttestFingerprint carries CPU fingerprint data.
type AttestFingerprint struct {
	CPUFlags string `json:"cpu_flags"`
	BootID   string `json:"boot_id"`
}

// AttestSubmitResponse is returned by POST /attest/submit.
type AttestSubmitResponse struct {
	OK                bool    `json:"ok"`
	Miner             string  `json:"miner"`
	Accepted          bool    `json:"accepted"`
	EntropyScore      float64 `json:"entropy_score"`
	FingerprintPassed bool    `json:"fingerprint_passed"`
	TemporalReview    bool    `json:"temporal_review_flag"`
	MACsRecorded      int     `json:"macs_recorded"`
	WarthogBonus      int     `json:"warthog_bonus"`
}

// Miner represents an active miner from GET /api/miners.
type Miner struct {
	MinerID             string  `json:"miner"`
	LastAttest          int64   `json:"last_attest"`
	FirstAttest         int64   `json:"first_attest"`
	DeviceFamily        string  `json:"device_family"`
	DeviceArch          string  `json:"device_arch"`
	HardwareType        string  `json:"hardware_type"`
	EntropyScore        float64 `json:"entropy_score"`
	AntiquityMultiplier float64 `json:"antiquity_multiplier"`
}

// MinerDashboardResponse is returned by GET /api/miner_dashboard/:minerID.
type MinerDashboardResponse struct {
	OK                 bool            `json:"ok"`
	MinerID            string          `json:"miner_id"`
	BalanceRTC         float64         `json:"balance_rtc"`
	TotalEarnedRTC     float64         `json:"total_earned_rtc"`
	RewardEvents       int             `json:"reward_events"`
	EpochParticipation int             `json:"epoch_participation"`
	RewardHistory      []RewardEntry   `json:"reward_history"`
	AttestTimeline24h  []AttestBucket  `json:"attest_timeline_24h"`
	GeneratedAt        int64           `json:"generated_at"`
}

// RewardEntry is a single epoch reward history item.
type RewardEntry struct {
	Epoch       int     `json:"epoch"`
	AmountRTC   float64 `json:"amount_rtc"`
	TxHash      string  `json:"tx_hash"`
	ConfirmedAt int64   `json:"confirmed_at"`
}

// AttestBucket is an hourly attestation count.
type AttestBucket struct {
	HourBucket int `json:"hour_bucket"`
	Count      int `json:"count"`
}

// BountyMultiplierResponse is returned by GET /api/bounty-multiplier.
type BountyMultiplierResponse struct {
	OK                   bool    `json:"ok"`
	DecayModel           string  `json:"decay_model"`
	HalfLifeRTC          float64 `json:"half_life_rtc"`
	InitialFundRTC       float64 `json:"initial_fund_rtc"`
	TotalPaidRTC         float64 `json:"total_paid_rtc"`
	RemainingRTC         float64 `json:"remaining_rtc"`
	CurrentMultiplier    float64 `json:"current_multiplier"`
	CurrentMultiplierPct string  `json:"current_multiplier_pct"`
}

// FeePoolResponse is returned by GET /api/fee_pool.
type FeePoolResponse struct {
	RIP                    int     `json:"rip"`
	Description            string  `json:"description"`
	TotalFeesCollectedRTC  float64 `json:"total_fees_collected_rtc"`
	TotalFeeEvents         int     `json:"total_fee_events"`
	Destination            string  `json:"destination"`
	DestinationBalanceRTC  float64 `json:"destination_balance_rtc"`
	WithdrawalFeeRTC       float64 `json:"withdrawal_fee_rtc"`
}

// WithdrawalRequest is sent to POST /withdraw/request.
type WithdrawalRequest struct {
	MinerPK     string  `json:"miner_pk"`
	Amount      float64 `json:"amount"`
	Destination string  `json:"destination"`
	Signature   string  `json:"signature"`
	Nonce       string  `json:"nonce"`
}

// WithdrawalResponse is returned by POST /withdraw/request.
type WithdrawalResponse struct {
	WithdrawalID string  `json:"withdrawal_id"`
	Status       string  `json:"status"`
	Amount       float64 `json:"amount"`
	Fee          float64 `json:"fee"`
	NetAmount    float64 `json:"net_amount"`
}

// WithdrawalStatus is returned by GET /withdraw/status/:id.
type WithdrawalStatus struct {
	WithdrawalID string  `json:"withdrawal_id"`
	MinerPK      string  `json:"miner_pk"`
	Amount       float64 `json:"amount"`
	Fee          float64 `json:"fee"`
	Destination  string  `json:"destination"`
	Status       string  `json:"status"`
	CreatedAt    int64   `json:"created_at"`
	ProcessedAt  *int64  `json:"processed_at"`
	TxHash       *string `json:"tx_hash"`
	ErrorMsg     *string `json:"error_msg"`
}

// Node represents a registered network node.
type Node struct {
	NodeID       string `json:"node_id"`
	Wallet       string `json:"wallet"`
	URL          string `json:"url"`
	Name         string `json:"name"`
	RegisteredAt int64  `json:"registered_at"`
	IsActive     bool   `json:"is_active"`
	Online       bool   `json:"online"`
}

// NodesResponse is returned by GET /api/nodes.
type NodesResponse struct {
	Nodes []Node `json:"nodes"`
	Count int    `json:"count"`
}

// BadgeResponse is returned by GET /api/badge/:minerID.
type BadgeResponse struct {
	SchemaVersion int    `json:"schemaVersion"`
	Label         string `json:"label"`
	Message       string `json:"message"`
	Color         string `json:"color"`
}

// BeaconSubmitRequest is sent to POST /beacon/submit.
type BeaconSubmitRequest struct {
	AgentID string `json:"agent_id"`
	Kind    string `json:"kind"`
	Nonce   string `json:"nonce"`
	Sig     string `json:"sig"`
	Pubkey  string `json:"pubkey"`
}

// BeaconSubmitResponse is returned by POST /beacon/submit.
type BeaconSubmitResponse struct {
	OK         bool `json:"ok"`
	EnvelopeID int  `json:"envelope_id"`
}

// BeaconDigestResponse is returned by GET /beacon/digest.
type BeaconDigestResponse struct {
	OK       bool   `json:"ok"`
	Digest   string `json:"digest"`
	Count    int    `json:"count"`
	LatestTS int64  `json:"latest_ts"`
}

// BeaconEnvelopesResponse is returned by GET /beacon/envelopes.
type BeaconEnvelopesResponse struct {
	OK        bool          `json:"ok"`
	Count     int           `json:"count"`
	Envelopes []interface{} `json:"envelopes"`
}

// GovernanceProposal represents a governance proposal.
type GovernanceProposal struct {
	ID              int     `json:"id"`
	ProposerWallet  string  `json:"proposer_wallet"`
	Title           string  `json:"title"`
	Description     string  `json:"description"`
	CreatedAt       int64   `json:"created_at"`
	ActivatedAt     int64   `json:"activated_at"`
	EndsAt          int64   `json:"ends_at"`
	Status          string  `json:"status"`
	YesWeight       float64 `json:"yes_weight"`
	NoWeight        float64 `json:"no_weight"`
	TotalWeight     float64 `json:"total_weight,omitempty"`
	Result          string  `json:"result,omitempty"`
}

// ProposalsResponse is returned by GET /governance/proposals.
type ProposalsResponse struct {
	OK        bool                 `json:"ok"`
	Count     int                  `json:"count"`
	Proposals []GovernanceProposal `json:"proposals"`
}

// ProposalDetailResponse is returned by GET /governance/proposal/:id.
type ProposalDetailResponse struct {
	OK       bool               `json:"ok"`
	Proposal GovernanceProposal `json:"proposal"`
	Votes    []ProposalVote     `json:"votes"`
}

// ProposalVote is a single vote on a proposal.
type ProposalVote struct {
	VoterWallet    string  `json:"voter_wallet"`
	Vote           string  `json:"vote"`
	Weight         float64 `json:"weight"`
	Multiplier     float64 `json:"multiplier"`
	BaseBalanceRTC float64 `json:"base_balance_rtc"`
	CreatedAt      int64   `json:"created_at"`
}

// ProposeRequest is sent to POST /governance/propose.
type ProposeRequest struct {
	Wallet      string `json:"wallet"`
	Title       string `json:"title"`
	Description string `json:"description"`
}

// VoteRequest is sent to POST /governance/vote.
type VoteRequest struct {
	ProposalID int    `json:"proposal_id"`
	Wallet     string `json:"wallet"`
	Vote       string `json:"vote"`
	Nonce      string `json:"nonce"`
	Signature  string `json:"signature"`
	PublicKey  string `json:"public_key"`
}

// VoteResponse is returned by POST /governance/vote.
type VoteResponse struct {
	OK                   bool    `json:"ok"`
	ProposalID           int     `json:"proposal_id"`
	VoterWallet          string  `json:"voter_wallet"`
	Vote                 string  `json:"vote"`
	BaseBalanceRTC       float64 `json:"base_balance_rtc"`
	AntiquityMultiplier  float64 `json:"antiquity_multiplier"`
	VoteWeight           float64 `json:"vote_weight"`
	Status               string  `json:"status"`
	YesWeight            float64 `json:"yes_weight"`
	NoWeight             float64 `json:"no_weight"`
	Result               string  `json:"result"`
}

// P2PStatsResponse is returned by GET /p2p/stats.
type P2PStatsResponse struct {
	OK        bool          `json:"ok"`
	Peers     []interface{} `json:"peers,omitempty"`
	SyncState interface{}   `json:"sync_state,omitempty"`
}

// ErrorResponse represents an API error.
type ErrorResponse struct {
	OK      bool   `json:"ok"`
	Error   string `json:"error"`
	Message string `json:"message,omitempty"`
	Code    string `json:"code,omitempty"`
}
