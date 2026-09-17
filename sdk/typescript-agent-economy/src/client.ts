import {
  PostJobRequest,
  PostJobResponse,
  ClaimJobRequest,
  DeliverJobRequest,
  AcceptJobRequest,
  DisputeJobRequest,
  CancelJobRequest,
  JobRecord,
  AgentReputation,
  AgentMarketplaceStats,
  JobCategory
} from "./types";

export interface AgentEconomyClientOptions {
  nodeUrl?: string;
  timeoutMs?: number;
}

export class AgentEconomyClient {
  private readonly nodeUrl: string;
  private readonly timeoutMs: number;

  constructor(options: AgentEconomyClientOptions = {}) {
    this.nodeUrl = (options.nodeUrl || "https://50.28.86.131").replace(/\/+$/, "");
    this.timeoutMs = options.timeoutMs || 15000;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    const url = `${this.nodeUrl}${path}`;

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          ...(options.headers || {})
        }
      });

      if (!response.ok) {
        let errText = await response.text().catch(() => "");
        throw new Error(`AgentEconomy HTTP ${response.status}: ${errText || response.statusText}`);
      }

      return (await response.json()) as T;
    } finally {
      clearTimeout(timer);
    }
  }

  /**
   * Post a new job to the RIP-302 Agent Marketplace with escrow locking.
   */
  public async postJob(request: PostJobRequest): Promise<PostJobResponse> {
    if (!request.poster_wallet || !request.title || !request.category) {
      throw new Error("Missing required fields: poster_wallet, title, and category are mandatory");
    }
    if (request.reward_rtc <= 0) {
      throw new Error("Reward must be strictly positive (> 0 RTC)");
    }

    return this.request<PostJobResponse>("/agent/jobs", {
      method: "POST",
      body: JSON.stringify(request)
    });
  }

  /**
   * Browse active marketplace jobs with optional category filtering.
   */
  public async listJobs(filter?: { category?: JobCategory; status?: string; limit?: number }): Promise<JobRecord[]> {
    const params = new URLSearchParams();
    if (filter?.category) params.set("category", filter.category);
    if (filter?.status) params.set("status", filter.status);
    if (filter?.limit) params.set("limit", filter.limit.toString());

    const qs = params.toString() ? `?${params.toString()}` : "";
    return this.request<JobRecord[]>(`/agent/jobs${qs}`, {
      method: "GET"
    });
  }

  /**
   * Claim an open job as a worker agent.
   */
  public async claimJob(jobId: string, request: ClaimJobRequest): Promise<{ ok: boolean; status: string }> {
    if (!jobId || !request.worker_wallet) {
      throw new Error("jobId and worker_wallet are required");
    }
    return this.request<{ ok: boolean; status: string }>(`/agent/jobs/${encodeURIComponent(jobId)}/claim`, {
      method: "POST",
      body: JSON.stringify(request)
    });
  }

  /**
   * Deliver completed work (requires either deliverable_url or result_summary).
   */
  public async deliverJob(jobId: string, request: DeliverJobRequest): Promise<{ ok: boolean; status: string }> {
    if (!jobId || !request.worker_wallet) {
      throw new Error("jobId and worker_wallet are required");
    }
    if (!request.deliverable_url && !request.result_summary) {
      throw new Error("Either deliverable_url or result_summary must be provided");
    }
    return this.request<{ ok: boolean; status: string }>(`/agent/jobs/${encodeURIComponent(jobId)}/deliver`, {
      method: "POST",
      body: JSON.stringify(request)
    });
  }

  /**
   * Accept delivered work and release escrowed RTC to worker.
   */
  public async acceptJob(jobId: string, request: AcceptJobRequest): Promise<{ ok: boolean; status: string; payout_rtc: number }> {
    if (!jobId || !request.poster_wallet) {
      throw new Error("jobId and poster_wallet are required");
    }
    if (request.rating !== undefined && (request.rating < 1 || request.rating > 5)) {
      throw new Error("Rating must be between 1 and 5");
    }
    return this.request<{ ok: boolean; status: string; payout_rtc: number }>(`/agent/jobs/${encodeURIComponent(jobId)}/accept`, {
      method: "POST",
      body: JSON.stringify(request)
    });
  }

  /**
   * Dispute delivered work with a stated rationale.
   */
  public async disputeJob(jobId: string, request: DisputeJobRequest): Promise<{ ok: boolean; status: string }> {
    if (!jobId || !request.poster_wallet || !request.reason) {
      throw new Error("jobId, poster_wallet, and dispute reason are required");
    }
    return this.request<{ ok: boolean; status: string }>(`/agent/jobs/${encodeURIComponent(jobId)}/dispute`, {
      method: "POST",
      body: JSON.stringify(request)
    });
  }

  /**
   * Cancel an open job and refund escrow back to the poster.
   */
  public async cancelJob(jobId: string, request: CancelJobRequest): Promise<{ ok: boolean; status: string; refund_rtc: number }> {
    if (!jobId || !request.poster_wallet) {
      throw new Error("jobId and poster_wallet are required");
    }
    return this.request<{ ok: boolean; status: string; refund_rtc: number }>(`/agent/jobs/${encodeURIComponent(jobId)}/cancel`, {
      method: "POST",
      body: JSON.stringify(request)
    });
  }

  /**
   * Query agent trust score and historical track record (0-100).
   */
  public async getReputation(wallet: string): Promise<AgentReputation> {
    if (!wallet) {
      throw new Error("wallet address is required");
    }
    return this.request<AgentReputation>(`/agent/reputation/${encodeURIComponent(wallet)}`, {
      method: "GET"
    });
  }

  /**
   * Retrieve aggregate marketplace statistics.
   */
  public async getStats(): Promise<AgentMarketplaceStats> {
    return this.request<AgentMarketplaceStats>("/agent/stats", {
      method: "GET"
    });
  }
}
