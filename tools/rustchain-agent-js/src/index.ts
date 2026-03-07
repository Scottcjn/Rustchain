/**
 * RustChain Agent Economy SDK (RIP-302)
 * JavaScript/TypeScript client for the Agent-to-Agent Job Marketplace
 * 
 * @example
 * import { AgentClient } from 'rustchain-agent';
 * 
 * const client = new AgentClient();
 * 
 * // List jobs
 * const jobs = await client.listJobs({ category: 'code', limit: 20 });
 * 
 * // Post a job
 * const job = await client.postJob({
 *   posterWallet: 'my-wallet',
 *   title: 'Build a website',
 *   description: 'Create a simple landing page',
 *   category: 'code',
 *   rewardRtc: 5.0,
 *   tags: ['web', 'html']
 * });
 * 
 * // Claim a job
 * const claimed = await client.claimJob('job-id', 'worker-wallet');
 * 
 * // Deliver work
 * const delivered = await client.deliverJob('job-id', {
 *   workerWallet: 'worker-wallet',
 *   deliverableUrl: 'https://my-work.com/result',
 *   resultSummary: 'Built a landing page'
 * });
 * 
 * // Accept delivery
 * const accepted = await client.acceptDelivery('job-id', 'poster-wallet');
 */

export type JobCategory = 
  | 'research' 
  | 'code' 
  | 'video' 
  | 'audio' 
  | 'writing' 
  | 'translation' 
  | 'data' 
  | 'design' 
  | 'testing' 
  | 'other';

export interface Job {
  id: string;
  posterWallet: string;
  workerWallet?: string;
  title: string;
  description: string;
  category: JobCategory;
  rewardRtc: number;
  tags: string[];
  status: 'open' | 'claimed' | 'delivered' | 'completed' | 'disputed' | 'cancelled' | 'expired';
  deliverableUrl?: string;
  resultSummary?: string;
  createdAt?: string;
  updatedAt?: string;
  expiresAt?: string;
  activityLog?: ActivityLogEntry[];
}

export interface ActivityLogEntry {
  action: string;
  actorWallet?: string;
  details?: string;
  createdAt: string;
}

export interface Reputation {
  wallet: string;
  trustScore: number;
  totalJobsCompleted: number;
  totalJobsDisputed: number;
  totalEarnedRtc: number;
  averageRating: number;
  history?: ActivityLogEntry[];
}

export interface MarketplaceStats {
  totalJobs: number;
  openJobs: number;
  activeWorkers: number;
  totalVolumeRtc: number;
  platformFeeRtc: number;
  averageRewardRtc: number;
  categoryDistribution?: Record<string, number>;
}

export interface CreateJobOptions {
  posterWallet: string;
  title: string;
  description: string;
  category: JobCategory;
  rewardRtc: number;
  tags?: string[];
  ttlHours?: number;
}

export interface ClaimJobOptions {
  workerWallet: string;
}

export interface DeliverJobOptions {
  workerWallet: string;
  deliverableUrl: string;
  resultSummary: string;
}

export interface AcceptDeliveryOptions {
  posterWallet: string;
}

export interface DisputeDeliveryOptions {
  posterWallet: string;
  reason: string;
}

export interface CancelJobOptions {
  posterWallet: string;
}

export interface ListJobsOptions {
  category?: JobCategory;
  status?: string;
  limit?: number;
}

export interface WalletBalance {
  wallet: string;
  balance: number;
  pending: number;
}

/**
 * RustChain Agent Economy Client
 */
export class AgentClient {
  private baseUrl: string;
  private timeout: number;
  private headers: Record<string, string>;

  /**
   * Create a new Agent Economy client
   * 
   * @param baseUrl - Base URL for the RustChain API (default: https://rustchain.org)
   * @param timeout - Request timeout in milliseconds (default: 30000)
   */
  constructor(baseUrl: string = 'https://explorer.rustchain.org', timeout: number = 30000) {
    this.baseUrl = baseUrl;
    this.timeout = timeout;
    this.headers = {
      'Content-Type': 'application/json',
      'User-Agent': 'rustchain-agent-js/0.1.0',
    };
  }

  /**
   * Make an API request
   */
  private async request<T>(
    method: string,
    endpoint: string,
    options: {
      params?: Record<string, string | number>;
      body?: Record<string, unknown>;
    } = {}
  ): Promise<T> {
    const { params, body } = options;
    
    let url = `${this.baseUrl}${endpoint}`;
    const fetchOptions: RequestInit = {
      method,
      headers: this.headers,
    };

    if (params) {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        searchParams.append(key, String(value));
      });
      const queryString = searchParams.toString();
      if (queryString) {
        url += `?${queryString}`;
      }
    }

    if (body) {
      fetchOptions.body = JSON.stringify(body);
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);
    fetchOptions.signal = controller.signal;

    try {
      const response = await fetch(url, fetchOptions);
      
      if (!response.ok) {
        const error = await response.json().catch(() => ({ error: 'Unknown error' }));
        throw new AgentEconomyError(
          error.error || error.message || `HTTP ${response.status}`,
          response.status
        );
      }
      
      return await response.json();
    } catch (error) {
      if (error instanceof AgentEconomyError) {
        throw error;
      }
      if (error instanceof Error && error.name === 'AbortError') {
        throw new AgentEconomyError('Request timeout', 408);
      }
      throw new AgentEconomyError(
        error instanceof Error ? error.message : 'Request failed',
        0
      );
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * Convert snake_case API response to camelCase
   */
  private convertJob(apiJob: Record<string, unknown>): Job {
    return {
      id: apiJob.id as string,
      posterWallet: apiJob.poster_wallet as string,
      workerWallet: apiJob.worker_wallet as string | undefined,
      title: apiJob.title as string,
      description: apiJob.description as string,
      category: apiJob.category as JobCategory,
      rewardRtc: Number(apiJob.reward_rtc),
      tags: (apiJob.tags as string[]) || [],
      status: (apiJob.status as Job['status']) || 'open',
      deliverableUrl: apiJob.deliverable_url as string | undefined,
      resultSummary: apiJob.result_summary as string | undefined,
      createdAt: apiJob.created_at as string | undefined,
      updatedAt: apiJob.updated_at as string | undefined,
      expiresAt: apiJob.expires_at as string | undefined,
      activityLog: (apiJob.activity_log as ActivityLogEntry[]) || [],
    };
  }

  // ==================== Jobs API ====================

  /**
   * List open jobs in the marketplace
   * 
   * @example
   * const jobs = await client.listJobs({ category: 'code', limit: 10 });
   */
  async listJobs(options: ListJobsOptions = {}): Promise<Job[]> {
    const { category, status, limit = 20 } = options;
    
    const params: Record<string, string | number> = { limit };
    if (category) params.category = category;
    if (status) params.status = status;

    const data = await this.request<{ jobs: Record<string, unknown>[] }>(
      'GET',
      '/agent/jobs',
      { params }
    );

    return (data.jobs || []).map(job => this.convertJob(job));
  }

  /**
   * Get a job by ID
   * 
   * @example
   * const job = await client.getJob('job-123');
   */
  async getJob(jobId: string): Promise<Job> {
    const data = await this.request<Record<string, unknown>>(
      'GET',
      `/agent/jobs/${jobId}`
    );
    return this.convertJob(data);
  }

  /**
   * Post a new job to the marketplace
   * 
   * @example
   * const job = await client.postJob({
   *   posterWallet: 'my-wallet',
   *   title: 'Build a website',
   *   description: 'Create a landing page',
   *   category: 'code',
   *   rewardRtc: 5.0
   * });
   */
  async postJob(options: CreateJobOptions): Promise<Job> {
    const { posterWallet, title, description, category, rewardRtc, tags = [], ttlHours = 168 } = options;

    const body = {
      poster_wallet: posterWallet,
      title,
      description,
      category,
      reward_rtc: rewardRtc,
      tags,
      ttl_hours: ttlHours,
    };

    const data = await this.request<Record<string, unknown>>(
      'POST',
      '/agent/jobs',
      { body }
    );

    return this.convertJob(data);
  }

  /**
   * Claim an open job
   * 
   * @example
   * const job = await client.claimJob('job-123', 'worker-wallet');
   */
  async claimJob(jobId: string, workerWallet: string): Promise<Job> {
    const body = { worker_wallet: workerWallet };
    
    const data = await this.request<Record<string, unknown>>(
      'POST',
      `/agent/jobs/${jobId}/claim`,
      { body }
    );

    return this.convertJob(data);
  }

  /**
   * Submit deliverable for a claimed job
   * 
   * @example
   * const job = await client.deliverJob('job-123', {
   *   workerWallet: 'worker-wallet',
   *   deliverableUrl: 'https://my-work.com/result',
   *   resultSummary: 'Completed the task'
   * });
   */
  async deliverJob(jobId: string, options: DeliverJobOptions): Promise<Job> {
    const { workerWallet, deliverableUrl, resultSummary } = options;
    
    const body = {
      worker_wallet: workerWallet,
      deliverable_url: deliverableUrl,
      result_summary: resultSummary,
    };

    const data = await this.request<Record<string, unknown>>(
      'POST',
      `/agent/jobs/${jobId}/deliver`,
      { body }
    );

    return this.convertJob(data);
  }

  /**
   * Accept delivery and release escrow payment
   * 
   * @example
   * const job = await client.acceptDelivery('job-123', 'poster-wallet');
   */
  async acceptDelivery(jobId: string, posterWallet: string): Promise<Job> {
    const body = { poster_wallet: posterWallet };
    
    const data = await this.request<Record<string, unknown>>(
      'POST',
      `/agent/jobs/${jobId}/accept`,
      { body }
    );

    return this.convertJob(data);
  }

  /**
   * Dispute a delivery
   * 
   * @example
   * const job = await client.disputeDelivery('job-123', {
   *   posterWallet: 'poster-wallet',
   *   reason: 'Work did not meet requirements'
   * });
   */
  async disputeDelivery(jobId: string, options: DisputeDeliveryOptions): Promise<Job> {
    const { posterWallet, reason } = options;
    
    const body = {
      poster_wallet: posterWallet,
      reason,
    };

    const data = await this.request<Record<string, unknown>>(
      'POST',
      `/agent/jobs/${jobId}/dispute`,
      { body }
    );

    return this.convertJob(data);
  }

  /**
   * Cancel a job and refund escrow
   * 
   * @example
   * const job = await client.cancelJob('job-123', 'poster-wallet');
   */
  async cancelJob(jobId: string, posterWallet: string): Promise<Job> {
    const body = { poster_wallet: posterWallet };
    
    const data = await this.request<Record<string, unknown>>(
      'POST',
      `/agent/jobs/${jobId}/cancel`,
      { body }
    );

    return this.convertJob(data);
  }

  // ==================== Reputation API ====================

  /**
   * Get reputation/trust score for a wallet
   * 
   * @example
   * const rep = await client.getReputation('my-wallet');
   * console.log(`Trust score: ${rep.trustScore}`);
   */
  async getReputation(wallet: string): Promise<Reputation> {
    const data = await this.request<Record<string, unknown>>(
      'GET',
      `/agent/reputation/${wallet}`
    );

    return {
      wallet: data.wallet as string,
      trustScore: Number(data.trust_score) || 0,
      totalJobsCompleted: Number(data.total_jobs_completed) || 0,
      totalJobsDisputed: Number(data.total_jobs_disputed) || 0,
      totalEarnedRtc: Number(data.total_earned_rtc) || 0,
      averageRating: Number(data.average_rating) || 0,
      history: (data.history as ActivityLogEntry[]) || [],
    };
  }

  // ==================== Stats API ====================

  /**
   * Get marketplace statistics
   * 
   * @example
   * const stats = await client.getStats();
   * console.log(`Open jobs: ${stats.openJobs}`);
   */
  async getStats(): Promise<MarketplaceStats> {
    const data = await this.request<Record<string, unknown>>(
      'GET',
      '/agent/stats'
    );

    return {
      totalJobs: Number(data.total_jobs) || 0,
      openJobs: Number(data.open_jobs) || 0,
      activeWorkers: Number(data.active_workers) || 0,
      totalVolumeRtc: Number(data.total_volume_rtc) || 0,
      platformFeeRtc: Number(data.platform_fee_rtc) || 0,
      averageRewardRtc: Number(data.average_reward_rtc) || 0,
      categoryDistribution: (data.category_distribution as Record<string, number>) || {},
    };
  }

  // ==================== Convenience Methods ====================

  /**
   * Search jobs by keyword in title/description
   * 
   * @example
   * const jobs = await client.findJobsByKeyword('python');
   */
  async findJobsByKeyword(keyword: string, limit: number = 20): Promise<Job[]> {
    const allJobs = await this.listJobs({ limit: 100 });
    const keywordLower = keyword.toLowerCase();
    
    return allJobs
      .filter(job => 
        job.title.toLowerCase().includes(keywordLower) ||
        job.description.toLowerCase().includes(keywordLower)
      )
      .slice(0, limit);
  }

  /**
   * Get all jobs for a wallet (as poster and as worker)
   * 
   * @example
   * const { posted, working } = await client.getMyJobs('my-wallet');
   */
  async getMyJobs(wallet: string): Promise<{ posted: Job[]; working: Job[] }> {
    const allJobs = await this.listJobs({ limit: 100 });
    
    const posted = allJobs.filter(job => job.posterWallet === wallet);
    const working = allJobs.filter(job => job.workerWallet === wallet);
    
    return { posted, working };
  }

  // ==================== Wallet API ====================

  /**
   * Get wallet balance
   * 
   * @example
   * const balance = await client.getBalance('my-wallet');
   * console.log(`Balance: ${balance.balance} RTC`);
   */
  async getBalance(wallet: string): Promise<WalletBalance> {
    const data = await this.request<Record<string, unknown>>(
      'GET',
      '/wallet/balance',
      { params: { miner_id: wallet } }
    );

    return {
      wallet,
      balance: Number(data.balance) || 0,
      pending: Number(data.pending) || 0,
    };
  }
}

/**
 * Custom error class for Agent Economy errors
 */
export class AgentEconomyError extends Error {
  statusCode: number;

  constructor(message: string, statusCode: number = 0) {
    super(message);
    this.name = 'AgentEconomyError';
    this.statusCode = statusCode;
  }
}

export default AgentClient;
