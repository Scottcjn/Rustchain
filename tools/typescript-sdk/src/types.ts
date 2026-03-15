// ---------------------------------------------------------------------------
// Health & Status
// ---------------------------------------------------------------------------

export interface HealthResponse {
  ok: boolean;
  version: string;
  uptime_s: number;
  db_rw?: boolean;
  backup_age_hours?: number;
  tip_age_slots?: number;
}

export interface ReadinessResponse {
  ready: boolean;
  version: string;
}

export interface ReadinessCheck {
  name: string;
  ok: boolean;
  val?: number;
  keys?: string[];
}

export interface OpsReadinessResponse {
  ok: boolean;
  checks?: ReadinessCheck[];
}

export interface StatsResponse {
  version: string;
  chain_id: string;
  epoch: number;
  block_time: number;
  total_miners: number;
  total_balance: number;
  pending_withdrawals: number;
  features: string[];
  security: string[];
}

export interface OuiEnforceStatusResponse {
  enforce: number;
}

// ---------------------------------------------------------------------------
// Attestation
// ---------------------------------------------------------------------------

export interface AttestChallengeResponse {
  nonce: string;
  expires_at: number;
  server_time: number;
}

export interface AttestDevice {
  device_model: string;
  device_arch: string;
  device_family: string;
  cores: number;
}

export interface AttestReport extends AttestDevice {
  nonce: string;
  cpu_serial?: string;
  entropy_sources?: string[];
  entropy_score?: number;
}

export interface AttestSignals {
  macs: string[];
}

export interface AttestFingerprint {
  cpu_flags?: string;
  boot_id?: string;
}

export interface AttestSubmitRequest {
  miner: string;
  nonce: string;
  report: AttestReport;
  device: AttestDevice;
  signals: AttestSignals;
  fingerprint?: AttestFingerprint;
}

export interface AttestSubmitResponse {
  ok: boolean;
  miner: string;
  accepted: boolean;
  entropy_score: number;
  fingerprint_passed: boolean;
  temporal_review_flag: boolean;
  macs_recorded: number;
  warthog_bonus: number;
}

export interface AttestDebugResponse {
  miner: string;
  timestamp: number;
  config: Record<string, unknown>;
  attestation: {
    found: boolean;
    ts_ok: number;
    age_seconds: number;
    is_fresh: boolean;
    device_family: string;
    device_arch: string;
    entropy_score: number;
  };
  macs: {
    unique_24h: number;
    entries: unknown[];
  };
  would_pass_enrollment: boolean;
  check_result: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Epochs & Enrollment
// ---------------------------------------------------------------------------

export interface EpochResponse {
  epoch: number;
  slot: number;
  epoch_pot: number;
  enrolled_miners: number;
  blocks_per_epoch: number;
  total_supply_rtc: number;
}

export interface EnrollRequest {
  miner_pubkey: string;
  miner_id: string;
  device: {
    family: string;
    arch: string;
  };
}

export interface EnrollResponse {
  ok: boolean;
  epoch: number;
  weight: number;
  hw_weight: number;
  fingerprint_failed: boolean;
  miner_pk: string;
  miner_id: string;
}

export interface LotteryEligibilityResponse {
  eligible: boolean;
  miner_id: string;
  slot: number;
  reason: string;
}

export interface EpochRewardEntry {
  miner_id: string;
  share_i64: number;
  share_rtc: number;
}

export interface EpochRewardsResponse {
  epoch: number;
  rewards: EpochRewardEntry[];
}

export interface SettleRewardsRequest {
  epoch: number;
}

// ---------------------------------------------------------------------------
// Block Headers
// ---------------------------------------------------------------------------

export interface SetHeaderKeyRequest {
  miner_id: string;
  pubkey_hex: string;
}

export interface SetHeaderKeyResponse {
  ok: boolean;
  miner_id: string;
  pubkey_hex: string;
}

export interface IngestHeaderRequest {
  miner_id: string;
  header: {
    slot: number;
    parent_hash: string;
    state_root: string;
  };
  message: string;
  signature: string;
  pubkey?: string;
}

export interface IngestHeaderResponse {
  ok: boolean;
  slot: number;
  miner: string;
  ms: number;
}

export interface ChainTipResponse {
  slot: number;
  miner: string;
  tip_age: number;
  signature_prefix: string;
}

// ---------------------------------------------------------------------------
// Wallet & Balance
// ---------------------------------------------------------------------------

export interface BalanceByPkResponse {
  miner_pk: string;
  balance_rtc: number;
  amount_i64: number;
}

export interface WalletBalanceResponse {
  miner_id: string;
  amount_i64: number;
  amount_rtc: number;
}

export interface TransferHistoryEntry {
  id: number;
  tx_id: string;
  tx_hash: string;
  from_addr: string;
  to_addr: string;
  amount: number;
  amount_i64: number;
  amount_rtc: number;
  timestamp: number;
  created_at: number;
  confirmed_at: number | null;
  confirms_at: number;
  status: string;
  direction: string;
  counterparty: string;
  reason: string;
  memo: string;
  confirmations: number;
}

export interface SignedTransferRequest {
  from_address: string;
  to_address: string;
  amount_rtc: number;
  nonce: string;
  signature: string;
  public_key: string;
  memo?: string;
  chain_id?: string;
}

export interface SignedTransferResponse {
  ok: boolean;
  verified: boolean;
  signature_type: string;
  replay_protected: boolean;
  phase: string;
  pending_id: number;
  tx_hash: string;
  from_address: string;
  to_address: string;
  amount_rtc: number;
  chain_id: string;
  confirms_at: number;
  confirms_in_hours: number;
  message: string;
}

export interface AdminTransferRequest {
  from_miner: string;
  to_miner: string;
  amount_rtc: number;
  reason: string;
}

export interface AdminTransferResponse {
  ok: boolean;
  phase: string;
  pending_id: number;
  tx_hash: string;
  from_miner: string;
  to_miner: string;
  amount_rtc: number;
  confirms_at: number;
  confirms_in_hours: number;
  message: string;
}

export interface ResolveWalletResponse {
  ok: boolean;
  beacon_id: string;
  pubkey_hex: string;
  rtc_address: string;
  name: string;
  status: string;
}

export interface BalanceEntry {
  miner_id: string;
  amount_i64: number;
  amount_rtc: number;
}

export interface AllBalancesResponse {
  ok: boolean;
  count: number;
  balances: BalanceEntry[];
}

export interface AllWalletBalancesResponse {
  balances: BalanceEntry[];
  total_i64: number;
  total_rtc: number;
}

export interface LedgerEntry {
  ts: number;
  epoch: number;
  miner_id: string;
  delta_i64: number;
  delta_rtc: number;
  reason: string;
}

export interface LedgerResponse {
  items: LedgerEntry[];
}

// ---------------------------------------------------------------------------
// Pending Ledger (2-Phase Commit)
// ---------------------------------------------------------------------------

export interface PendingTransfer {
  id: number;
  ts: number;
  from_miner: string;
  to_miner: string;
  amount_rtc: number;
  reason: string;
  status: string;
  confirms_at: number;
  voided_by: string | null;
  voided_reason: string | null;
  tx_hash: string;
}

export interface PendingListResponse {
  ok: boolean;
  count: number;
  pending: PendingTransfer[];
}

export interface VoidPendingRequest {
  pending_id?: number;
  tx_hash?: string;
  reason: string;
  voided_by: string;
}

export interface VoidPendingResponse {
  ok: boolean;
  voided_id: number;
  from_miner: string;
  to_miner: string;
  amount_rtc: number;
  voided_by: string;
  reason: string;
}

export interface ConfirmPendingResponse {
  ok: boolean;
  confirmed_count: number;
  confirmed_ids: number[];
  errors: unknown[] | null;
}

export interface IntegrityResponse {
  ok: boolean;
  total_miners_checked: number;
  mismatches: unknown[] | null;
  pending_transfers: number;
}

// ---------------------------------------------------------------------------
// Withdrawals
// ---------------------------------------------------------------------------

export interface RegisterWithdrawKeyRequest {
  miner_pk: string;
  pubkey_sr25519: string;
}

export interface RegisterWithdrawKeyResponse {
  miner_pk: string;
  pubkey_registered: boolean;
  can_withdraw: boolean;
}

export interface WithdrawRequest {
  miner_pk: string;
  amount: number;
  destination: string;
  signature: string;
  nonce: string;
}

export interface WithdrawResponse {
  withdrawal_id: string;
  status: string;
  amount: number;
  fee: number;
  net_amount: number;
}

export interface WithdrawStatusResponse {
  withdrawal_id: string;
  miner_pk: string;
  amount: number;
  fee: number;
  destination: string;
  status: string;
  created_at: number;
  processed_at: number | null;
  tx_hash: string | null;
  error_msg: string | null;
}

export interface WithdrawHistoryEntry {
  withdrawal_id: string;
  amount: number;
  fee: number;
  destination: string;
  status: string;
  created_at: number;
  processed_at: number | null;
  tx_hash: string | null;
}

export interface WithdrawHistoryResponse {
  miner_pk: string;
  current_balance: number;
  withdrawals: WithdrawHistoryEntry[];
}

export interface FeePoolResponse {
  rip: number;
  description: string;
  total_fees_collected_rtc: number;
  total_fee_events: number;
  fees_by_source: Record<string, { total_rtc: number; count: number }>;
  destination: string;
  destination_balance_rtc: number;
  withdrawal_fee_rtc: number;
  recent_events: unknown[];
}

// ---------------------------------------------------------------------------
// Governance (RIP-0142)
// ---------------------------------------------------------------------------

export interface GovRotateMember {
  signer_id: number;
  pubkey_hex: string;
}

export interface GovRotateStageRequest {
  epoch_effective: number;
  threshold: number;
  members: GovRotateMember[];
}

export interface GovRotateStageResponse {
  ok: boolean;
  staged_epoch: number;
  members: number;
  threshold: number;
  message: string;
}

export interface GovRotateMessageResponse {
  ok: boolean;
  epoch_effective: number;
  message: string;
}

export interface GovRotateApproveRequest {
  epoch_effective: number;
  signer_id: number;
  sig_hex: string;
}

export interface GovRotateApproveResponse {
  ok: boolean;
  epoch_effective: number;
  approvals: number;
  threshold: number;
  ready: boolean;
}

export interface GovRotateCommitRequest {
  epoch_effective: number;
}

export interface GovRotateCommitResponse {
  ok: boolean;
  epoch_effective: number;
  committed: number;
  approvals: number;
  threshold: number;
}

export interface GovProposalRequest {
  wallet: string;
  title: string;
  description: string;
}

export interface GovProposal {
  id: number;
  proposer_wallet?: string;
  wallet?: string;
  title: string;
  description: string;
  status: string;
  created_at: number;
  activated_at: number;
  ends_at: number;
  yes_weight: number;
  no_weight: number;
  total_weight?: number;
  result?: string;
  rules?: Record<string, string>;
}

export interface GovProposalCreateResponse {
  ok: boolean;
  proposal: GovProposal;
}

export interface GovProposalListResponse {
  ok: boolean;
  count: number;
  proposals: GovProposal[];
}

export interface GovVote {
  voter_wallet: string;
  vote: string;
  weight: number;
  multiplier: number;
  base_balance_rtc: number;
  created_at: number;
}

export interface GovProposalDetailResponse {
  ok: boolean;
  proposal: GovProposal;
  votes: GovVote[];
}

export interface GovVoteRequest {
  proposal_id: number;
  wallet: string;
  vote: "yes" | "no";
  nonce: string;
  signature: string;
  public_key: string;
}

export interface GovVoteResponse {
  ok: boolean;
  proposal_id: number;
  voter_wallet: string;
  vote: string;
  base_balance_rtc: number;
  antiquity_multiplier: number;
  vote_weight: number;
  status: string;
  yes_weight: number;
  no_weight: number;
  result: string;
}

// ---------------------------------------------------------------------------
// Genesis
// ---------------------------------------------------------------------------

export interface GenesisExportResponse {
  chain_id: string;
  created_ts: number;
  threshold: number;
  signers: GovRotateMember[];
  params: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Miners & Network
// ---------------------------------------------------------------------------

export interface ActiveMiner {
  miner: string;
  last_attest: number;
  first_attest: number;
  device_family: string;
  device_arch: string;
  hardware_type: string;
  entropy_score: number;
  antiquity_multiplier: number;
}

export interface NodeInfo {
  node_id: string;
  wallet: string;
  url: string;
  name: string;
  registered_at: number;
  is_active: boolean;
  online: boolean;
}

export interface NodesResponse {
  nodes: NodeInfo[];
  count: number;
}

export interface BadgeResponse {
  schemaVersion: number;
  label: string;
  message: string;
  color: string;
}

export interface RewardHistoryEntry {
  epoch: number;
  amount_rtc: number;
  tx_hash: string;
  confirmed_at: number;
}

export interface AttestTimeline {
  hour_bucket: number;
  count: number;
}

export interface MinerDashboardResponse {
  ok: boolean;
  miner_id: string;
  balance_rtc: number;
  total_earned_rtc: number;
  reward_events: number;
  epoch_participation: number;
  reward_history: RewardHistoryEntry[];
  attest_timeline_24h: AttestTimeline[];
  generated_at: number;
}

export interface MinerAttestationEntry {
  ts_ok: number;
  device_family: string;
  device_arch: string;
}

export interface MinerAttestationHistoryResponse {
  ok: boolean;
  miner: string;
  count: number;
  attestations: MinerAttestationEntry[];
}

export interface BountyMultiplierMilestone {
  multiplier: number;
  rtc_paid_threshold: number;
  status: string;
}

export interface BountyMultiplierResponse {
  ok: boolean;
  decay_model: string;
  half_life_rtc: number;
  initial_fund_rtc: number;
  total_paid_rtc: number;
  remaining_rtc: number;
  current_multiplier: number;
  current_multiplier_pct: string;
  example: {
    face_value: number;
    actual_payout: number;
    note: string;
  };
  milestones: BountyMultiplierMilestone[];
}

// ---------------------------------------------------------------------------
// Admin - OUI Denylist
// ---------------------------------------------------------------------------

export interface OuiEntry {
  oui: string;
  vendor: string;
  added_ts?: number;
  enforce: number;
}

export interface OuiListResponse {
  ok: boolean;
  count: number;
  entries: OuiEntry[];
}

export interface OuiAddRequest {
  oui: string;
  vendor: string;
  enforce?: number;
}

export interface OuiAddResponse {
  ok: boolean;
  oui: string;
  vendor: string;
  enforce: number;
}

export interface OuiRemoveResponse {
  ok: boolean;
  removed: string;
}

export interface OuiToggleRequest {
  enforce: string;
}

export interface OuiToggleResponse {
  ok: boolean;
  enforce: number;
}

// ---------------------------------------------------------------------------
// Admin - Wallet Review
// ---------------------------------------------------------------------------

export interface WalletReviewHold {
  id: number;
  wallet: string;
  status: string;
  reason: string;
  coach_note: string;
  reviewer_note: string;
  created_at: number;
  reviewed_at: number;
}

export interface WalletReviewListResponse {
  ok: boolean;
  count: number;
  entries: WalletReviewHold[];
}

export interface WalletReviewCreateRequest {
  wallet: string;
  status: "needs_review" | "held" | "escalated" | "blocked";
  reason: string;
  coach_note?: string;
}

export interface WalletReviewCreateResponse {
  ok: boolean;
  id: number;
  wallet: string;
  status: string;
  reason: string;
}

export interface WalletReviewResolveRequest {
  action: "release" | "dismiss" | "escalate" | "block";
  reviewer_note?: string;
  coach_note?: string;
}

export interface WalletReviewResolveResponse {
  ok: boolean;
  id: number;
  wallet: string;
  status: string;
}

// ---------------------------------------------------------------------------
// Beacon Protocol
// ---------------------------------------------------------------------------

export interface BeaconSubmitRequest {
  agent_id: string;
  kind: string;
  nonce: string;
  sig: string;
  pubkey: string;
}

export interface BeaconSubmitResponse {
  ok: boolean;
  envelope_id: number;
}

export interface BeaconDigestResponse {
  ok: boolean;
  digest: string;
  count: number;
  latest_ts: number;
}

export interface BeaconEnvelopesResponse {
  ok: boolean;
  count: number;
  envelopes: unknown[];
}

// ---------------------------------------------------------------------------
// P2P Sync
// ---------------------------------------------------------------------------

export interface P2PPingResponse {
  ok: boolean;
  timestamp: number;
}

export interface P2PBlocksResponse {
  ok: boolean;
  blocks: unknown[];
}

export interface P2PAddPeerRequest {
  peer_url: string;
}

export interface P2PAddPeerResponse {
  ok: boolean;
}

// ---------------------------------------------------------------------------
// Client config
// ---------------------------------------------------------------------------

export interface RustChainClientConfig {
  /** Base URL of the RustChain node (e.g. "http://50.28.86.131:8099") */
  baseUrl: string;
  /** Admin API key for privileged endpoints (X-API-Key / X-Admin-Key header) */
  adminKey?: string;
  /** Override the default fetch implementation */
  fetch?: typeof globalThis.fetch;
  /** Skip TLS certificate verification (Node 18+, sets rejectUnauthorized) */
  rejectUnauthorized?: boolean;
}
