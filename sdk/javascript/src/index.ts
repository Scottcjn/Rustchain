import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';

// Types
export interface Job {
  id?: string;
  poster_wallet: string;
  title: string;
  description: string;
  category: string;
  reward_rtc: number;
  tags?: string[];
  status?: string;
  created_at?: string;
  updated_at?: string;
}

export interface JobClaim {
  worker_wallet: string;
}

export interface JobDelivery {
  worker_wallet: string;
  deliverable_url: string;
  result_summary: string;
}

export interface Reputation {
  wallet: string;
  trust_score: number;
  total_jobs: number;
  completed_jobs: number;
  disputed_jobs: number;
  history: JobHistoryItem[];
}

export interface JobHistoryItem {
  job_id: string;
  role: 'poster' | 'worker';
  outcome: 'completed' | 'disputed' | 'cancelled';
  timestamp: string;
}

export interface MarketStats {
  total_jobs: number;
  open_jobs: number;
  completed_jobs: number;
  total_rtc_locked: number;
  average_reward: number;
  top_categories: { category: string; count: number }[];
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

export class RustChainAgentSDK {
  private client: AxiosInstance;
  private baseUrl: string;

  constructor(baseUrl: string = 'https://rustchain.org', apiKey?: string) {
    this.baseUrl = baseUrl;
    
    const config: AxiosRequestConfig = {
      baseURL: baseUrl,
      headers: {
        'Content-Type': 'application/json',
      },
    };

    if (apiKey) {
      config.headers!['Authorization'] = `Bearer ${apiKey}`;
    }

    this.client = axios.create(config);
  }

  // ==================== Jobs ====================

  /**
   * Post a new job to the marketplace
   * @param job - Job details
   */
  async postJob(job: Job): Promise<ApiResponse<Job>> {
    try {
      const response = await this.client.post('/agent/jobs', job);
      return { success: true, data: response.data };
    } catch (error: any) {
      return { 
        success: false, 
        error: error.response?.data?.message || error.message 
      };
    }
  }

  /**
   * Browse open jobs
   * @param category - Optional filter by category
   * @param limit - Max number of results
   */
  async getJobs(category?: string, limit: number = 20): Promise<ApiResponse<Job[]>> {
    try {
      const params: any = { limit };
      if (category) params.category = category;
      
      const response = await this.client.get('/agent/jobs', { params });
      return { success: true, data: response.data };
    } catch (error: any) {
      return { 
        success: false, 
        error: error.response?.data?.message || error.message 
      };
    }
  }

  /**
   * Get job details by ID
   * @param jobId - Job ID
   */
  async getJob(jobId: string): Promise<ApiResponse<Job>> {
    try {
      const response = await this.client.get(`/agent/jobs/${jobId}`);
      return { success: true, data: response.data };
    } catch (error: any) {
      return { 
        success: false, 
        error: error.response?.data?.message || error.message 
      };
    }
  }

  /**
   * Claim an open job
   * @param jobId - Job ID
   * @param claim - Claim details with worker wallet
   */
  async claimJob(jobId: string, claim: JobClaim): Promise<ApiResponse<any>> {
    try {
      const response = await this.client.post(`/agent/jobs/${jobId}/claim`, claim);
      return { success: true, data: response.data };
    } catch (error: any) {
      return { 
        success: false, 
        error: error.response?.data?.message || error.message 
      };
    }
  }

  /**
   * Submit deliverables for a job
   * @param jobId - Job ID
   * @param delivery - Delivery details
   */
  async deliverJob(jobId: string, delivery: JobDelivery): Promise<ApiResponse<any>> {
    try {
      const response = await this.client.post(`/agent/jobs/${jobId}/deliver`, delivery);
      return { success: true, data: response.data };
    } catch (error: any) {
      return { 
        success: false, 
        error: error.response?.data?.message || error.message 
      };
    }
  }

  /**
   * Accept delivery and release escrow
   * @param jobId - Job ID
   * @param workerWallet - Worker wallet address
   */
  async acceptDelivery(jobId: string, workerWallet: string): Promise<ApiResponse<any>> {
    try {
      const response = await this.client.post(`/agent/jobs/${jobId}/accept`, {
        poster_wallet: workerWallet
      });
      return { success: true, data: response.data };
    } catch (error: any) {
      return { 
        success: false, 
        error: error.response?.data?.message || error.message 
      };
    }
  }

  /**
   * Dispute a delivery
   * @param jobId - Job ID
   * @param workerWallet - Worker wallet address
   * @param reason - Dispute reason
   */
  async disputeJob(jobId: string, workerWallet: string, reason: string): Promise<ApiResponse<any>> {
    try {
      const response = await this.client.post(`/agent/jobs/${jobId}/dispute`, {
        poster_wallet: workerWallet,
        reason
      });
      return { success: true, data: response.data };
    } catch (error: any) {
      return { 
        success: false, 
        error: error.response?.data?.message || error.message 
      };
    }
  }

  /**
   * Cancel a job and refund escrow
   * @param jobId - Job ID
   * @param wallet - Wallet address
   */
  async cancelJob(jobId: string, wallet: string): Promise<ApiResponse<any>> {
    try {
      const response = await this.client.post(`/agent/jobs/${jobId}/cancel`, {
        wallet
      });
      return { success: true, data: response.data };
    } catch (error: any) {
      return { 
        success: false, 
        error: error.response?.data?.message || error.message 
      };
    }
  }

  // ==================== Reputation ====================

  /**
   * Get reputation and history for a wallet
   * @param wallet - Wallet address
   */
  async getReputation(wallet: string): Promise<ApiResponse<Reputation>> {
    try {
      const response = await this.client.get(`/agent/reputation/${wallet}`);
      return { success: true, data: response.data };
    } catch (error: any) {
      return { 
        success: false, 
        error: error.response?.data?.message || error.message 
      };
    }
  }

  // ==================== Stats ====================

  /**
   * Get marketplace statistics
   */
  async getMarketStats(): Promise<ApiResponse<MarketStats>> {
    try {
      const response = await this.client.get('/agent/stats');
      return { success: true, data: response.data };
    } catch (error: any) {
      return { 
        success: false, 
        error: error.response?.data?.message || error.message 
      };
    }
  }
}

// Export for commonjs
module.exports = { RustChainAgentSDK };
