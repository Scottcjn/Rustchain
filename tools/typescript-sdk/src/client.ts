import type {
  RustChainClientConfig,
  HealthResponse,
  ReadinessResponse,
  OpsReadinessResponse,
  StatsResponse,
  OuiEnforceStatusResponse,
  AttestChallengeResponse,
  AttestSubmitRequest,
  AttestSubmitResponse,
  AttestDebugResponse,
  EpochResponse,
  EnrollRequest,
  EnrollResponse,
  LotteryEligibilityResponse,
  EpochRewardsResponse,
  SettleRewardsRequest,
  SetHeaderKeyRequest,
  SetHeaderKeyResponse,
  IngestHeaderRequest,
  IngestHeaderResponse,
  ChainTipResponse,
  BalanceByPkResponse,
  WalletBalanceResponse,
  TransferHistoryEntry,
  SignedTransferRequest,
  SignedTransferResponse,
  AdminTransferRequest,
  AdminTransferResponse,
  ResolveWalletResponse,
  AllBalancesResponse,
  AllWalletBalancesResponse,
  LedgerResponse,
  PendingListResponse,
  VoidPendingRequest,
  VoidPendingResponse,
  ConfirmPendingResponse,
  IntegrityResponse,
  RegisterWithdrawKeyRequest,
  RegisterWithdrawKeyResponse,
  WithdrawRequest,
  WithdrawResponse,
  WithdrawStatusResponse,
  WithdrawHistoryResponse,
  FeePoolResponse,
  GovRotateStageRequest,
  GovRotateStageResponse,
  GovRotateMessageResponse,
  GovRotateApproveRequest,
  GovRotateApproveResponse,
  GovRotateCommitRequest,
  GovRotateCommitResponse,
  GovProposalRequest,
  GovProposalCreateResponse,
  GovProposalListResponse,
  GovProposalDetailResponse,
  GovVoteRequest,
  GovVoteResponse,
  GenesisExportResponse,
  ActiveMiner,
  NodesResponse,
  BadgeResponse,
  MinerDashboardResponse,
  MinerAttestationHistoryResponse,
  BountyMultiplierResponse,
  OuiToggleRequest,
  OuiToggleResponse,
  OuiListResponse,
  OuiAddRequest,
  OuiAddResponse,
  OuiRemoveResponse,
  WalletReviewListResponse,
  WalletReviewCreateRequest,
  WalletReviewCreateResponse,
  WalletReviewResolveRequest,
  WalletReviewResolveResponse,
  BeaconSubmitRequest,
  BeaconSubmitResponse,
  BeaconDigestResponse,
  BeaconEnvelopesResponse,
  P2PPingResponse,
  P2PBlocksResponse,
  P2PAddPeerRequest,
  P2PAddPeerResponse,
} from "./types";

export class RustChainError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
    message?: string,
  ) {
    super(message ?? `RustChain API error ${status}`);
    this.name = "RustChainError";
  }
}

export class RustChainClient {
  private readonly baseUrl: string;
  private readonly adminKey?: string;
  private readonly _fetch: typeof globalThis.fetch;
  private readonly fetchOptions: Record<string, unknown>;

  constructor(config: RustChainClientConfig) {
    this.baseUrl = config.baseUrl.replace(/\/+$/, "");
    this.adminKey = config.adminKey;
    this._fetch = config.fetch ?? globalThis.fetch;
    this.fetchOptions =
      config.rejectUnauthorized === false
        ? {
            // Node 18+ with --experimental-fetch honours this via the
            // underlying undici dispatcher.  For older runtimes callers can
            // pass a custom fetch that disables TLS verification.
          }
        : {};
  }

  // -----------------------------------------------------------------------
  // Internal helpers
  // -----------------------------------------------------------------------

  private async request<T>(
    method: string,
    path: string,
    options: {
      body?: unknown;
      query?: Record<string, string | number | undefined>;
      admin?: boolean;
      adminHeader?: "X-API-Key" | "X-Admin-Key";
    } = {},
  ): Promise<T> {
    const url = new URL(path, this.baseUrl);
    if (options.query) {
      for (const [k, v] of Object.entries(options.query)) {
        if (v !== undefined) url.searchParams.set(k, String(v));
      }
    }

    const headers: Record<string, string> = {};
    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
    }
    if (options.admin && this.adminKey) {
      const hdr = options.adminHeader ?? "X-API-Key";
      headers[hdr] = this.adminKey;
    }

    const res = await this._fetch(url.toString(), {
      method,
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      ...this.fetchOptions,
    });

    const text = await res.text();
    let json: unknown;
    try {
      json = JSON.parse(text);
    } catch {
      json = text;
    }

    if (!res.ok) {
      throw new RustChainError(res.status, json, `${method} ${path} -> ${res.status}`);
    }

    return json as T;
  }

  private get<T>(
    path: string,
    query?: Record<string, string | number | undefined>,
    admin?: boolean,
    adminHeader?: "X-API-Key" | "X-Admin-Key",
  ): Promise<T> {
    return this.request<T>("GET", path, { query, admin, adminHeader });
  }

  private post<T>(
    path: string,
    body?: unknown,
    admin?: boolean,
    adminHeader?: "X-API-Key" | "X-Admin-Key",
  ): Promise<T> {
    return this.request<T>("POST", path, { body, admin, adminHeader });
  }

  // =======================================================================
  // Health & Status
  // =======================================================================

  /** Basic health check. */
  health(): Promise<HealthResponse> {
    return this.get("/health");
  }

  /** Kubernetes-style readiness probe. */
  ready(): Promise<ReadinessResponse> {
    return this.get("/ready");
  }

  /** Ops readiness aggregator (RIP-0143). Admin key yields detailed output. */
  opsReadiness(): Promise<OpsReadinessResponse> {
    return this.get("/ops/readiness", undefined, true);
  }

  /** System-wide statistics. */
  stats(): Promise<StatsResponse> {
    return this.get("/api/stats");
  }

  /** Prometheus-format metrics (returns raw text). */
  async metrics(): Promise<string> {
    return this.get<string>("/metrics");
  }

  /** MAC / attestation metrics (returns raw text). */
  async metricsMac(): Promise<string> {
    return this.get<string>("/metrics_mac");
  }

  /** OpenAPI 3.0.3 specification. */
  openApiSpec(): Promise<unknown> {
    return this.get("/openapi.json");
  }

  /** OUI enforcement toggle status. */
  ouiEnforceStatus(): Promise<OuiEnforceStatusResponse> {
    return this.get("/ops/oui/enforce");
  }

  // =======================================================================
  // Attestation
  // =======================================================================

  /** Request a hardware attestation challenge nonce. */
  attestChallenge(): Promise<AttestChallengeResponse> {
    return this.post("/attest/challenge");
  }

  /** Submit hardware attestation. */
  attestSubmit(data: AttestSubmitRequest): Promise<AttestSubmitResponse> {
    return this.post("/attest/submit", data);
  }

  /** Admin: debug attestation state for a miner. */
  attestDebug(minerId: string): Promise<AttestDebugResponse> {
    return this.post("/ops/attest/debug", { miner: minerId }, true);
  }

  // =======================================================================
  // Epochs & Enrollment
  // =======================================================================

  /** Get current epoch info. */
  epoch(): Promise<EpochResponse> {
    return this.get("/epoch");
  }

  /** Enroll a miner in the current epoch. */
  epochEnroll(data: EnrollRequest): Promise<EnrollResponse> {
    return this.post("/epoch/enroll", data);
  }

  /** Lottery eligibility check (RIP-0200). */
  lotteryEligibility(minerId: string): Promise<LotteryEligibilityResponse> {
    return this.get("/lottery/eligibility", { miner_id: minerId });
  }

  /** Get reward distribution for a specific epoch. */
  epochRewards(epoch: number): Promise<EpochRewardsResponse> {
    return this.get(`/rewards/epoch/${epoch}`);
  }

  /** Admin: settle (distribute) rewards for an epoch. */
  settleRewards(data: SettleRewardsRequest): Promise<unknown> {
    return this.post("/rewards/settle", data, true);
  }

  // =======================================================================
  // Block Headers
  // =======================================================================

  /** Admin: set miner header-signing public key. */
  setMinerHeaderKey(data: SetHeaderKeyRequest): Promise<SetHeaderKeyResponse> {
    return this.post("/miner/headerkey", data, true);
  }

  /** Ingest a signed block header. */
  ingestSignedHeader(data: IngestHeaderRequest): Promise<IngestHeaderResponse> {
    return this.post("/headers/ingest_signed", data);
  }

  /** Get the current chain tip. */
  chainTip(): Promise<ChainTipResponse> {
    return this.get("/headers/tip");
  }

  // =======================================================================
  // Wallet & Balance
  // =======================================================================

  /** Get balance by miner public key / address. */
  balanceByPk(minerPk: string): Promise<BalanceByPkResponse> {
    return this.get(`/balance/${minerPk}`);
  }

  /** Get wallet balance by miner_id. */
  walletBalance(minerId: string): Promise<WalletBalanceResponse> {
    return this.get("/wallet/balance", { miner_id: minerId });
  }

  /** Get public transfer history for a wallet. */
  walletHistory(
    minerId: string,
    limit?: number,
  ): Promise<TransferHistoryEntry[]> {
    return this.get("/wallet/history", { miner_id: minerId, limit });
  }

  /** Transfer RTC with Ed25519 signature. */
  signedTransfer(data: SignedTransferRequest): Promise<SignedTransferResponse> {
    return this.post("/wallet/transfer/signed", data);
  }

  /** Admin: initiate a 2-phase commit transfer. */
  adminTransfer(data: AdminTransferRequest): Promise<AdminTransferResponse> {
    return this.post("/wallet/transfer", data, true, "X-Admin-Key");
  }

  /** Resolve a bcn_ beacon address to an RTC wallet. */
  resolveWallet(address: string): Promise<ResolveWalletResponse> {
    return this.get("/wallet/resolve", { address });
  }

  /** Admin: get all balances sorted by amount descending. */
  allBalances(limit?: number): Promise<AllBalancesResponse> {
    return this.get("/api/balances", { limit }, true);
  }

  /** Admin: export all wallet balances with grand total. */
  allWalletBalances(): Promise<AllWalletBalancesResponse> {
    return this.get("/wallet/balances/all", undefined, true, "X-Admin-Key");
  }

  /** Admin: get immutable transaction ledger entries. */
  ledger(minerId?: string): Promise<LedgerResponse> {
    return this.get("/wallet/ledger", { miner_id: minerId }, true, "X-Admin-Key");
  }

  // =======================================================================
  // Pending Ledger (2-Phase Commit)
  // =======================================================================

  /** Admin: list pending transfers. */
  pendingList(
    status?: "pending" | "confirmed" | "voided" | "all",
    limit?: number,
  ): Promise<PendingListResponse> {
    return this.get("/pending/list", { status, limit }, true, "X-Admin-Key");
  }

  /** Admin: void a pending transfer before confirmation. */
  pendingVoid(data: VoidPendingRequest): Promise<VoidPendingResponse> {
    return this.post("/pending/void", data, true, "X-Admin-Key");
  }

  /** Admin: confirm all pending transfers whose delay has elapsed. */
  pendingConfirm(): Promise<ConfirmPendingResponse> {
    return this.post("/pending/confirm", undefined, true, "X-Admin-Key");
  }

  /** Admin: balance integrity check. */
  pendingIntegrity(): Promise<IntegrityResponse> {
    return this.get("/pending/integrity", undefined, true);
  }

  // =======================================================================
  // Withdrawals (RIP-0008)
  // =======================================================================

  /** Admin: register an sr25519 withdrawal key. */
  registerWithdrawKey(
    data: RegisterWithdrawKeyRequest,
  ): Promise<RegisterWithdrawKeyResponse> {
    return this.post("/withdraw/register", data, true, "X-Admin-Key");
  }

  /** Request an RTC withdrawal. */
  withdrawRequest(data: WithdrawRequest): Promise<WithdrawResponse> {
    return this.post("/withdraw/request", data);
  }

  /** Get status of a specific withdrawal. */
  withdrawStatus(withdrawalId: string): Promise<WithdrawStatusResponse> {
    return this.get(`/withdraw/status/${withdrawalId}`);
  }

  /** Admin: get withdrawal history for a miner. */
  withdrawHistory(
    minerPk: string,
    limit?: number,
  ): Promise<WithdrawHistoryResponse> {
    return this.get(`/withdraw/history/${minerPk}`, { limit }, true);
  }

  /** Fee pool statistics (RIP-301). */
  feePool(): Promise<FeePoolResponse> {
    return this.get("/api/fee_pool");
  }

  // =======================================================================
  // Governance (RIP-0142)
  // =======================================================================

  /** Admin: stage a governance rotation proposal. */
  govRotateStage(data: GovRotateStageRequest): Promise<GovRotateStageResponse> {
    return this.post("/gov/rotate/stage", data, true);
  }

  /** Get the canonical rotation message for signing. */
  govRotateMessage(epochEffective: number): Promise<GovRotateMessageResponse> {
    return this.get(`/gov/rotate/message/${epochEffective}`);
  }

  /** Submit an approval signature for a staged rotation. */
  govRotateApprove(
    data: GovRotateApproveRequest,
  ): Promise<GovRotateApproveResponse> {
    return this.post("/gov/rotate/approve", data);
  }

  /** Commit a governance rotation after threshold approvals. */
  govRotateCommit(
    data: GovRotateCommitRequest,
  ): Promise<GovRotateCommitResponse> {
    return this.post("/gov/rotate/commit", data);
  }

  /** Create a governance proposal. */
  govPropose(data: GovProposalRequest): Promise<GovProposalCreateResponse> {
    return this.post("/governance/propose", data);
  }

  /** List all governance proposals. */
  govProposals(): Promise<GovProposalListResponse> {
    return this.get("/governance/proposals");
  }

  /** Get detailed info for a specific proposal. */
  govProposalDetail(proposalId: number): Promise<GovProposalDetailResponse> {
    return this.get(`/governance/proposal/${proposalId}`);
  }

  /** Cast a vote on an active proposal. */
  govVote(data: GovVoteRequest): Promise<GovVoteResponse> {
    return this.post("/governance/vote", data);
  }

  // =======================================================================
  // Genesis (RIP-0144)
  // =======================================================================

  /** Admin: export deterministic genesis.json. */
  genesisExport(): Promise<GenesisExportResponse> {
    return this.get("/genesis/export", undefined, true);
  }

  // =======================================================================
  // Miners & Network
  // =======================================================================

  /** List miners attested in the last hour. */
  miners(): Promise<ActiveMiner[]> {
    return this.get("/api/miners");
  }

  /** List registered attestation nodes. */
  nodes(): Promise<NodesResponse> {
    return this.get("/api/nodes");
  }

  /** Shields.io-compatible badge for a miner. */
  minerBadge(minerId: string): Promise<BadgeResponse> {
    return this.get(`/api/badge/${minerId}`);
  }

  /** Aggregated miner dashboard data. */
  minerDashboard(minerId: string): Promise<MinerDashboardResponse> {
    return this.get(`/api/miner_dashboard/${minerId}`);
  }

  /** Admin: miner attestation history. */
  minerAttestationHistory(
    minerId: string,
    limit?: number,
  ): Promise<MinerAttestationHistoryResponse> {
    return this.get(
      `/api/miner/${minerId}/attestations`,
      { limit },
      true,
    );
  }

  /** Bounty decay multiplier (RIP-0200b). */
  bountyMultiplier(): Promise<BountyMultiplierResponse> {
    return this.get("/api/bounty-multiplier");
  }

  // =======================================================================
  // Admin - OUI Denylist
  // =======================================================================

  /** Admin: toggle OUI enforcement. */
  ouiToggle(data: OuiToggleRequest): Promise<OuiToggleResponse> {
    return this.post("/admin/oui_deny/enforce", data, true);
  }

  /** Admin: list denied OUIs. */
  ouiList(): Promise<OuiListResponse> {
    return this.get("/admin/oui_deny/list", undefined, true);
  }

  /** Admin: add OUI to denylist. */
  ouiAdd(data: OuiAddRequest): Promise<OuiAddResponse> {
    return this.post("/admin/oui_deny/add", data, true);
  }

  /** Admin: remove OUI from denylist. */
  ouiRemove(oui: string): Promise<OuiRemoveResponse> {
    return this.post("/admin/oui_deny/remove", { oui }, true);
  }

  // =======================================================================
  // Admin - Wallet Review
  // =======================================================================

  /** Admin: list wallet review holds. */
  walletReviewList(status?: string): Promise<WalletReviewListResponse> {
    return this.get("/admin/wallet-review-holds", { status }, true);
  }

  /** Admin: create a wallet review hold. */
  walletReviewCreate(
    data: WalletReviewCreateRequest,
  ): Promise<WalletReviewCreateResponse> {
    return this.post("/admin/wallet-review-holds", data, true);
  }

  /** Admin: resolve a wallet review hold. */
  walletReviewResolve(
    holdId: number,
    data: WalletReviewResolveRequest,
  ): Promise<WalletReviewResolveResponse> {
    return this.post(
      `/admin/wallet-review-holds/${holdId}/resolve`,
      data,
      true,
    );
  }

  // =======================================================================
  // Beacon Protocol
  // =======================================================================

  /** Submit a beacon envelope for anchoring. */
  beaconSubmit(data: BeaconSubmitRequest): Promise<BeaconSubmitResponse> {
    return this.post("/beacon/submit", data);
  }

  /** Get the current beacon digest. */
  beaconDigest(): Promise<BeaconDigestResponse> {
    return this.get("/beacon/digest");
  }

  /** List recent beacon envelopes. */
  beaconEnvelopes(
    limit?: number,
    offset?: number,
  ): Promise<BeaconEnvelopesResponse> {
    return this.get("/beacon/envelopes", { limit, offset });
  }

  // =======================================================================
  // P2P Sync
  // =======================================================================

  /** Get P2P network stats. */
  p2pStats(): Promise<unknown> {
    return this.get("/p2p/stats");
  }

  /** P2P peer health check. */
  p2pPing(): Promise<P2PPingResponse> {
    return this.post("/p2p/ping");
  }

  /** Get blocks for P2P sync. */
  p2pBlocks(start?: number, limit?: number): Promise<P2PBlocksResponse> {
    return this.get("/p2p/blocks", { start, limit });
  }

  /** Add a new peer. */
  p2pAddPeer(data: P2PAddPeerRequest): Promise<P2PAddPeerResponse> {
    return this.post("/p2p/add_peer", data);
  }
}
