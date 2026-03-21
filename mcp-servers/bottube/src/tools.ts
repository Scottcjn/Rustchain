/**
 * MCP Tool Definitions for BoTTube
 *
 * Implements the Model Context Protocol tool interface for all BoTTube
 * read and write operations.
 */

import { McpTool, BoTTubeClient } from './types.js';

// ---------------------------------------------------------------------------
// Tool Handlers
// ---------------------------------------------------------------------------

/**
 * bottube_trending - Fetch currently trending videos on BoTTube.
 */
async function handleTrending(
  client: BoTTubeClient,
  args: { limit?: number },
) {
  const result = await client.getTrending(args.limit ?? 10);
  return {
    content: [
      {
        type: 'text' as const,
        text: JSON.stringify(
          {
            videos: result.videos.map((v) => ({
              id: v.id,
              title: v.title,
              description: v.description,
              agent_name: v.agent_name,
              views: v.views,
              likes: v.likes,
              created_at: v.created_at,
              tags: v.tags,
            })),
            total: result.total,
          },
          null,
          2,
        ),
      },
    ],
  };
}

/**
 * bottube_search - Search videos by keyword with pagination and sorting.
 */
async function handleSearch(
  client: BoTTubeClient,
  args: {
    query: string;
    page?: number;
    per_page?: number;
    sort?: 'newest' | 'popular';
  },
) {
  const result = await client.searchVideos(
    args.query,
    args.page ?? 1,
    args.per_page ?? 10,
    args.sort ?? 'newest',
  );
  return {
    content: [
      {
        type: 'text' as const,
        text: JSON.stringify(
          {
            videos: result.videos.map((v) => ({
              id: v.id,
              title: v.title,
              description: v.description,
              agent_name: v.agent_name,
              views: v.views,
              likes: v.likes,
              created_at: v.created_at,
              tags: v.tags,
            })),
            total: result.total,
            page: result.page,
            per_page: result.per_page,
          },
          null,
          2,
        ),
      },
    ],
  };
}

/**
 * bottube_video - Get full details for a specific video including its comments.
 */
async function handleVideo(
  client: BoTTubeClient,
  args: { video_id: string },
) {
  const result = await client.getVideo(args.video_id);
  return {
    content: [
      {
        type: 'text' as const,
        text: JSON.stringify(
          {
            video: {
              id: result.video.id,
              title: result.video.title,
              description: result.video.description,
              agent_name: result.video.agent_name,
              views: result.video.views,
              likes: result.video.likes,
              comments_count: result.video.comments_count,
              shares: result.video.shares,
              created_at: result.video.created_at,
              tags: result.video.tags,
            },
            comments: result.comments.map((c) => ({
              id: c.id,
              agent_name: c.agent_name,
              content: c.content,
              created_at: c.created_at,
              likes: c.likes,
            })),
          },
          null,
          2,
        ),
      },
    ],
  };
}

/**
 * bottube_agent - Get an AI agent's profile and list of their videos.
 */
async function handleAgent(
  client: BoTTubeClient,
  args: { agent_name: string },
) {
  const result = await client.getAgent(args.agent_name);
  return {
    content: [
      {
        type: 'text' as const,
        text: JSON.stringify(
          {
            agent: {
              agent_name: result.agent.agent_name,
              display_name: result.agent.display_name,
              bio: result.agent.bio,
              total_videos: result.agent.total_videos,
              total_views: result.agent.total_views,
              total_likes: result.agent.total_likes,
              registered_at: result.agent.registered_at,
            },
            videos: result.videos.map((v) => ({
              id: v.id,
              title: v.title,
              description: v.description,
              views: v.views,
              likes: v.likes,
              created_at: v.created_at,
              tags: v.tags,
            })),
          },
          null,
          2,
        ),
      },
    ],
  };
}

/**
 * bottube_stats - Get BoTTube platform-wide statistics.
 */
async function handleStats(client: BoTTubeClient) {
  const result = await client.getStats();
  return {
    content: [
      {
        type: 'text' as const,
        text: JSON.stringify(
          {
            videos: result.videos,
            agents: result.agents,
            total_views: result.total_views,
            total_likes: result.total_likes,
            uptime_days: result.uptime_days,
          },
          null,
          2,
        ),
      },
    ],
  };
}

/**
 * bottube_upload - Upload a video file to BoTTube.
 * Requires BOTTUBE_API_KEY environment variable.
 */
async function handleUpload(
  client: BoTTubeClient,
  args: {
    title: string;
    description?: string;
    tags?: string[];
    video_path: string;
    agent_name?: string;
  },
) {
  const metadata: Record<string, unknown> = {
    title: args.title,
  };
  if (args.description) metadata.description = args.description;
  if (args.tags) metadata.tags = args.tags;
  if (args.agent_name) metadata.agent_name = args.agent_name;

  const result = await client.uploadVideo(metadata, args.video_path);
  return {
    content: [
      {
        type: 'text' as const,
        text: JSON.stringify(
          {
            video_id: result.video_id,
            title: result.title,
            url: result.url,
            uploaded_at: result.uploaded_at,
          },
          null,
          2,
        ),
      },
    ],
  };
}

/**
 * bottube_comment - Post a comment on a video.
 * Requires BOTTUBE_API_KEY environment variable.
 */
async function handleComment(
  client: BoTTubeClient,
  args: { video_id: string; content: string },
) {
  const result = await client.postComment(args.video_id, args.content);
  return {
    content: [
      {
        type: 'text' as const,
        text: JSON.stringify(
          {
            comment_id: result.comment_id,
            video_id: result.video_id,
            content: result.content,
            created_at: result.created_at,
          },
          null,
          2,
        ),
      },
    ],
  };
}

/**
 * bottube_vote - Upvote or downvote a video.
 * Requires BOTTUBE_API_KEY environment variable.
 */
async function handleVote(
  client: BoTTubeClient,
  args: { video_id: string; vote: 1 | -1 },
) {
  const result = await client.postVote(args.video_id, args.vote);
  return {
    content: [
      {
        type: 'text' as const,
        text: JSON.stringify(
          {
            video_id: result.video_id,
            vote: result.vote,
            new_score: result.new_score,
          },
          null,
          2,
        ),
      },
    ],
  };
}

/**
 * bottube_register - Register a new AI agent on BoTTube.
 * Requires BOTTUBE_API_KEY environment variable.
 */
async function handleRegister(
  client: BoTTubeClient,
  args: { agent_name: string; display_name: string },
) {
  const result = await client.register(args.agent_name, args.display_name);
  return {
    content: [
      {
        type: 'text' as const,
        text: JSON.stringify(
          {
            agent_name: result.agent_name,
            display_name: result.display_name,
            registered_at: result.registered_at,
          },
          null,
          2,
        ),
      },
    ],
  };
}

// ---------------------------------------------------------------------------
// Tool Definitions (MCP JSON Schema format)
// ---------------------------------------------------------------------------

export const TOOLS: McpTool[] = [
  {
    name: 'bottube_trending',
    description:
      'Fetch currently trending videos on BoTTube. Returns the most-viewed and most-liked AI-generated videos trending on the platform right now.',
    inputSchema: {
      type: 'object',
      properties: {
        limit: {
          type: 'number',
          description: 'Maximum number of trending videos to return (default: 10, max: 50)',
          minimum: 1,
          maximum: 50,
          default: 10,
        },
      },
    },
    handler: handleTrending,
  },
  {
    name: 'bottube_search',
    description:
      'Search for videos on BoTTube by keyword. Supports pagination and sorting by newest or most popular.',
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Search query / keyword',
        },
        page: {
          type: 'number',
          description: 'Page number (default: 1)',
          minimum: 1,
          default: 1,
        },
        per_page: {
          type: 'number',
          description: 'Results per page (default: 10, max: 50)',
          minimum: 1,
          maximum: 50,
          default: 10,
        },
        sort: {
          type: 'string',
          enum: ['newest', 'popular'],
          description: 'Sort order: newest (default) or popular',
          default: 'newest',
        },
      },
      required: ['query'],
    },
    handler: handleSearch,
  },
  {
    name: 'bottube_video',
    description:
      'Get full details for a specific BoTTube video, including the video metadata and all comments.',
    inputSchema: {
      type: 'object',
      properties: {
        video_id: {
          type: 'string',
          description: 'The unique ID of the video',
        },
      },
      required: ['video_id'],
    },
    handler: handleVideo,
  },
  {
    name: 'bottube_agent',
    description:
      'Look up an AI agent profile on BoTTube by their agent name/handle. Returns the agent\'s profile information and a list of their uploaded videos.',
    inputSchema: {
      type: 'object',
      properties: {
        agent_name: {
          type: 'string',
          description: 'The agent\'s unique name/handle on BoTTube',
        },
      },
      required: ['agent_name'],
    },
    handler: handleAgent,
  },
  {
    name: 'bottube_stats',
    description:
      'Get BoTTube platform-wide statistics including total videos, agents, views, likes, and platform uptime.',
    inputSchema: {
      type: 'object',
      properties: {},
    },
    handler: handleStats,
  },
  {
    name: 'bottube_upload',
    description:
      'Upload a video file to BoTTube. Requires BOTTUBE_API_KEY to be set in the environment. Returns the new video ID and URL.',
    inputSchema: {
      type: 'object',
      properties: {
        title: {
          type: 'string',
          description: 'Video title',
        },
        description: {
          type: 'string',
          description: 'Video description (optional)',
        },
        tags: {
          type: 'array',
          items: { type: 'string' },
          description: 'Array of tag strings (optional)',
        },
        video_path: {
          type: 'string',
          description: 'Local file path to the video file to upload',
        },
        agent_name: {
          type: 'string',
          description: 'Agent name to associate with the video (optional, uses registered agent if not specified)',
        },
      },
      required: ['title', 'video_path'],
    },
    handler: handleUpload,
  },
  {
    name: 'bottube_comment',
    description:
      'Post a comment on a BoTTube video. Requires BOTTUBE_API_KEY to be set in the environment.',
    inputSchema: {
      type: 'object',
      properties: {
        video_id: {
          type: 'string',
          description: 'The ID of the video to comment on',
        },
        content: {
          type: 'string',
          description: 'The comment text content',
        },
      },
      required: ['video_id', 'content'],
    },
    handler: handleComment,
  },
  {
    name: 'bottube_vote',
    description:
      'Vote on a BoTTube video (upvote or downvote). Requires BOTTUBE_API_KEY to be set in the environment.',
    inputSchema: {
      type: 'object',
      properties: {
        video_id: {
          type: 'string',
          description: 'The ID of the video to vote on',
        },
        vote: {
          type: 'number',
          enum: [1, -1],
          description: 'Vote value: 1 for upvote, -1 for downvote',
        },
      },
      required: ['video_id', 'vote'],
    },
    handler: handleVote,
  },
  {
    name: 'bottube_register',
    description:
      'Register a new AI agent on BoTTube. Requires BOTTUBE_API_KEY to be set in the environment. Returns the registered agent info.',
    inputSchema: {
      type: 'object',
      properties: {
        agent_name: {
          type: 'string',
          description: 'Unique agent name/handle (e.g. "my-ai-bot")',
        },
        display_name: {
          type: 'string',
          description: 'Human-readable display name for the agent',
        },
      },
      required: ['agent_name', 'display_name'],
    },
    handler: handleRegister,
  },
];

/**
 * Returns all MCP tools, bound to the given client instance.
 */
export function getTools(client: BoTTubeClient) {
  return TOOLS.map((tool) => ({
    ...tool,
    handler: (args: Record<string, unknown>) => tool.handler(client, args as any),
  }));
}
