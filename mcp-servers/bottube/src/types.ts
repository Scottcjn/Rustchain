/**
 * Shared type definitions for the BoTTube MCP Server.
 */

import { BoTTubeClient } from './api.js';

// Re-export everything from api.ts
export type {
  Video,
  VideoDetails,
  Comment,
  AgentProfile,
  PlatformStats,
  TrendingResponse,
  SearchResponse,
  VideoResponse,
  AgentResponse,
  UploadResponse,
  CommentResponse,
  VoteResponse,
  RegisterResponse,
} from './api.js';

// Re-export client
export { BoTTubeClient } from './api.js';

/**
 * Shape of an MCP tool after being bound to a client.
 */
export interface McpTool {
  name: string;
  description: string;
  inputSchema: {
    type: 'object';
    properties?: Record<string, unknown>;
    required?: string[];
    [key: string]: unknown;
  };
  handler: (client: BoTTubeClient, args: Record<string, unknown>) => Promise<{
    content: Array<{ type: 'text'; text: string }>;
    isError?: boolean;
  }>;
}
