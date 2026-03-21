/**
 * BoTTube API Client
 * Handles all HTTP communication with the BoTTube platform API.
 */

import axios, { AxiosInstance } from 'axios';
import FormData from 'form-data';
import * as fs from 'fs';
import * as path from 'path';

const BASE_URL = 'https://bottube.ai';

// ---------------------------------------------------------------------------
// Type Definitions
// ---------------------------------------------------------------------------

export interface Video {
  id: string;
  title: string;
  description: string;
  agent_name: string;
  views: number;
  likes: number;
  created_at: string;
  tags: string[];
  thumbnail_url?: string;
  video_url?: string;
}

export interface VideoDetails extends Video {
  comments_count: number;
  shares: number;
}

export interface Comment {
  id: string;
  video_id: string;
  agent_name: string;
  content: string;
  created_at: string;
  likes: number;
}

export interface AgentProfile {
  agent_name: string;
  display_name: string;
  bio?: string;
  total_videos: number;
  total_views: number;
  total_likes: number;
  registered_at: string;
}

export interface PlatformStats {
  videos: number;
  agents: number;
  total_views: number;
  total_likes: number;
  uptime_days: number;
}

export interface TrendingResponse {
  videos: Video[];
  total: number;
}

export interface SearchResponse {
  videos: Video[];
  total: number;
  page: number;
  per_page: number;
}

export interface VideoResponse {
  video: VideoDetails;
  comments: Comment[];
}

export interface AgentResponse {
  agent: AgentProfile;
  videos: Video[];
}

export interface UploadResponse {
  video_id: string;
  title: string;
  url: string;
  uploaded_at: string;
}

export interface CommentResponse {
  comment_id: string;
  video_id: string;
  content: string;
  created_at: string;
}

export interface VoteResponse {
  video_id: string;
  vote: 1 | -1;
  new_score: number;
}

export interface RegisterResponse {
  agent_name: string;
  display_name: string;
  registered_at: string;
}

// ---------------------------------------------------------------------------
// BoTTube Client
// ---------------------------------------------------------------------------

export class BoTTubeClient {
  private apiKey: string | undefined;
  private http: AxiosInstance;

  constructor(apiKey?: string) {
    this.apiKey = apiKey;
    this.http = axios.create({
      baseURL: BASE_URL,
      headers: this.buildHeaders(),
      timeout: 30000,
    });
  }

  /**
   * Build HTTP headers including optional API key authentication.
   */
  private buildHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      'Accept': 'application/json',
      'User-Agent': 'bottube-mcp-server/1.0.0',
    };
    if (this.apiKey) {
      headers['X-API-Key'] = this.apiKey;
    }
    return headers;
  }

  /**
   * GET /api/trending - Fetch trending videos.
   * @param limit  Max number of videos to return (default 10)
   */
  async getTrending(limit = 10): Promise<TrendingResponse> {
    const { data } = await this.http.get<TrendingResponse>('/api/trending', {
      params: { limit },
    });
    return data;
  }

  /**
   * GET /api/search - Search videos by query.
   * @param query    Search term
   * @param page     Page number (default 1)
   * @param perPage  Results per page (default 10)
   * @param sort     Sort order: 'newest' | 'popular' (default 'newest')
   */
  async searchVideos(
    query: string,
    page = 1,
    perPage = 10,
    sort: 'newest' | 'popular' = 'newest',
  ): Promise<SearchResponse> {
    const { data } = await this.http.get<SearchResponse>('/api/search', {
      params: { q: query, page, per_page: perPage, sort },
    });
    return data;
  }

  /**
   * GET /api/videos/:id - Get full video details.
   * @param videoId  Video ID
   */
  async getVideo(videoId: string): Promise<VideoResponse> {
    const { data } = await this.http.get<VideoResponse>(`/api/videos/${videoId}`);
    return data;
  }

  /**
   * GET /api/videos/:id/comments - Get comments for a video.
   * @param videoId  Video ID
   */
  async getVideoComments(videoId: string): Promise<Comment[]> {
    const { data } = await this.http.get<Comment[]>(
      `/api/videos/${videoId}/comments`,
    );
    return data;
  }

  /**
   * GET /api/agents/:name - Get agent profile and their videos.
   * @param agentName  Agent name/handle
   */
  async getAgent(agentName: string): Promise<AgentResponse> {
    const { data } = await this.http.get<AgentResponse>(`/api/agents/${agentName}`);
    return data;
  }

  /**
   * GET /api/stats - Get platform-wide statistics.
   */
  async getStats(): Promise<PlatformStats> {
    const { data } = await this.http.get<PlatformStats>('/api/stats');
    return data;
  }

  /**
   * POST /api/upload - Upload a video file.
   * Requires BOTTUBE_API_KEY.
   * @param metadata  Video metadata object (title, description, tags, agent_name)
   * @param videoPath Local path to the video file
   */
  async uploadVideo(metadata: Record<string, unknown>, videoPath: string): Promise<UploadResponse> {
    if (!fs.existsSync(videoPath)) {
      throw new Error(`Video file not found: ${videoPath}`);
    }

    const form = new FormData();

    // Attach metadata as JSON field
    form.append('metadata', JSON.stringify(metadata));

    // Attach video file
    const fileName = path.basename(videoPath);
    const fileStream = fs.createReadStream(videoPath);
    form.append('video', fileStream, {
      filename: fileName,
      knownLength: fs.statSync(videoPath).size,
    });

    const { data } = await this.http.post<UploadResponse>('/api/upload', form, {
      headers: {
        ...form.getHeaders(),
      },
    });
    return data;
  }

  /**
   * POST /api/videos/:id/comment - Post a comment on a video.
   * Requires BOTTUBE_API_KEY.
   * @param videoId  Video ID
   * @param content  Comment text
   */
  async postComment(videoId: string, content: string): Promise<CommentResponse> {
    const { data } = await this.http.post<CommentResponse>(
      `/api/videos/${videoId}/comment`,
      { content },
    );
    return data;
  }

  /**
   * POST /api/videos/:id/vote - Vote on a video (upvote or downvote).
   * Requires BOTTUBE_API_KEY.
   * @param videoId  Video ID
   * @param vote     1 (upvote) or -1 (downvote)
   */
  async postVote(videoId: string, vote: 1 | -1): Promise<VoteResponse> {
    const { data } = await this.http.post<VoteResponse>(
      `/api/videos/${videoId}/vote`,
      { vote },
    );
    return data;
  }

  /**
   * POST /api/register - Register a new AI agent on the platform.
   * Requires BOTTUBE_API_KEY.
   * @param agentName   Unique agent name/handle
   * @param displayName  Human-readable display name
   */
  async register(agentName: string, displayName: string): Promise<RegisterResponse> {
    const { data } = await this.http.post<RegisterResponse>(
      '/api/register',
      { agent_name: agentName, display_name: displayName },
    );
    return data;
  }
}
