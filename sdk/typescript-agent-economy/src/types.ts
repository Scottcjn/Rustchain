export type JobCategory =
  | "research"
  | "code"
  | "video"
  | "audio"
  | "writing"
  | "translation"
  | "data"
  | "design"
  | "testing"
  | "other";

export type JobStatus =
  | "open"
  | "claimed"
  | "delivered"
  | "completed"
  | "disputed"
  | "cancelled";

export interface PostJobRequest {
  poster_wallet: string;
  title: string;
  category: JobCategory;
  reward_rtc: number;
  description?: string;
  timeout_seconds?: number;
}

export interface PostJobResponse {
  ok: boolean;
  job_id: string;
  status: JobStatus;
  escrow_locked_rtc: number;
  platform_fee_rtc: number;
}

export interface ClaimJobRequest {
  worker_wallet: string;
}

export interface DeliverJobRequest {
  worker_wallet: string;
  deliverable_url?: string;
  result_summary?: string;
}

export interface AcceptJobRequest {
  poster_wallet: string;
  rating?: number; // 1 to 5
}

export interface DisputeJobRequest {
  poster_wallet: string;
  reason: string;
}

export interface CancelJobRequest {
  poster_wallet: string;
}

export interface JobRecord {
  id: string;
  poster_wallet: string;
  worker_wallet?: string;
  title: string;
  category: JobCategory;
  reward_rtc: number;
  status: JobStatus;
  deliverable_url?: string;
  result_summary?: string;
  created_at: string;
  claimed_at?: string;
  delivered_at?: string;
  completed_at?: string;
}

export interface AgentReputation {
  wallet: string;
  trust_score: number; // 0 to 100
  jobs_completed: number;
  jobs_posted: number;
  dispute_count: number;
  average_rating: number;
}

export interface AgentMarketplaceStats {
  total_jobs: number;
  open_jobs: number;
  completed_jobs: number;
  total_volume_rtc: number;
  total_escrow_locked_rtc: number;
  active_agents: number;
}
