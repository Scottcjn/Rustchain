import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import axios from 'axios';

const API_BASE = process.env.RUSTCHAIN_API_URL || 'https://rustchain.org';

// Tool definitions
const tools = [
  {
    name: 'rustchain_get_market_stats',
    description: 'Get RustChain Agent Economy marketplace statistics',
    inputSchema: {
      type: 'object',
      properties: {},
    },
  },
  {
    name: 'rustchain_get_jobs',
    description: 'Browse open jobs in the RustChain marketplace',
    inputSchema: {
      type: 'object',
      properties: {
        category: {
          type: 'string',
          description: 'Filter by category (research, code, video, audio, writing, translation, data, design, testing, other)',
        },
        limit: {
          type: 'number',
          description: 'Maximum number of jobs to return',
          default: 10,
        },
      },
    },
  },
  {
    name: 'rustchain_get_job',
    description: 'Get detailed information about a specific job',
    inputSchema: {
      type: 'object',
      properties: {
        job_id: {
          type: 'string',
          description: 'The job ID',
        },
      },
      required: ['job_id'],
    },
  },
  {
    name: 'rustchain_post_job',
    description: 'Post a new job to the RustChain marketplace',
    inputSchema: {
      type: 'object',
      properties: {
        poster_wallet: {
          type: 'string',
          description: 'Wallet address posting the job',
        },
        title: {
          type: 'string',
          description: 'Job title',
        },
        description: {
          type: 'string',
          description: 'Job description',
        },
        category: {
          type: 'string',
          description: 'Category (research, code, video, audio, writing, translation, data, design, testing, other)',
        },
        reward_rtc: {
          type: 'number',
          description: 'Reward in RTC',
        },
        tags: {
          type: 'array',
          items: { type: 'string' },
          description: 'Optional tags',
        },
      },
      required: ['poster_wallet', 'title', 'description', 'category', 'reward_rtc'],
    },
  },
  {
    name: 'rustchain_claim_job',
    description: 'Claim a job from the marketplace',
    inputSchema: {
      type: 'object',
      properties: {
        job_id: {
          type: 'string',
          description: 'Job ID to claim',
        },
        worker_wallet: {
          type: 'string',
          description: 'Worker wallet address',
        },
      },
      required: ['job_id', 'worker_wallet'],
    },
  },
  {
    name: 'rustchain_deliver_job',
    description: 'Submit deliverable for a claimed job',
    inputSchema: {
      type: 'object',
      properties: {
        job_id: {
          type: 'string',
          description: 'Job ID',
        },
        worker_wallet: {
          type: 'string',
          description: 'Worker wallet',
        },
        deliverable_url: {
          type: 'string',
          description: 'URL to the deliverable',
        },
        result_summary: {
          type: 'string',
          description: 'Summary of work completed',
        },
      },
      required: ['job_id', 'worker_wallet', 'deliverable_url', 'result_summary'],
    },
  },
  {
    name: 'rustchain_accept_delivery',
    description: 'Accept delivered work and release RTC escrow',
    inputSchema: {
      type: 'object',
      properties: {
        job_id: {
          type: 'string',
          description: 'Job ID',
        },
        poster_wallet: {
          type: 'string',
          description: 'Poster wallet address',
        },
      },
      required: ['job_id', 'poster_wallet'],
    },
  },
  {
    name: 'rustchain_get_reputation',
    description: 'Check agent reputation in the marketplace',
    inputSchema: {
      type: 'object',
      properties: {
        wallet: {
          type: 'string',
          description: 'Wallet address to check',
        },
      },
      required: ['wallet'],
    },
  },
];

// API helper functions
async function getMarketStats() {
  const response = await axios.get(`${API_BASE}/agent/stats`);
  return response.data;
}

async function getJobs(category?: string, limit: number = 10) {
  const params: any = { limit };
  if (category) params.category = category;
  const response = await axios.get(`${API_BASE}/agent/jobs`, { params });
  return response.data;
}

async function getJob(jobId: string) {
  const response = await axios.get(`${API_BASE}/agent/jobs/${jobId}`);
  return response.data;
}

async function postJob(data: any) {
  const response = await axios.post(`${API_BASE}/agent/jobs`, data);
  return response.data;
}

async function claimJob(jobId: string, workerWallet: string) {
  const response = await axios.post(`${API_BASE}/agent/jobs/${jobId}/claim`, {
    worker_wallet: workerWallet,
  });
  return response.data;
}

async function deliverJob(jobId: string, data: any) {
  const response = await axios.post(`${API_BASE}/agent/jobs/${jobId}/deliver`, data);
  return response.data;
}

async function acceptDelivery(jobId: string, posterWallet: string) {
  const response = await axios.post(`${API_BASE}/agent/jobs/${jobId}/accept`, {
    poster_wallet: posterWallet,
  });
  return response.data;
}

async function getReputation(wallet: string) {
  const response = await axios.get(`${API_BASE}/agent/reputation/${wallet}`);
  return response.data;
}

// Create server
const server = new Server(
  {
    name: 'rustchain-agent-mcp',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// List tools handler
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return { tools };
});

// Call tool handler
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    let result;

    switch (name) {
      case 'rustchain_get_market_stats':
        result = await getMarketStats();
        break;

      case 'rustchain_get_jobs':
        result = await getJobs(args.category, args.limit || 10);
        break;

      case 'rustchain_get_job':
        result = await getJob(args.job_id);
        break;

      case 'rustchain_post_job':
        result = await postJob({
          poster_wallet: args.poster_wallet,
          title: args.title,
          description: args.description,
          category: args.category,
          reward_rtc: args.reward_rtc,
          tags: args.tags,
        });
        break;

      case 'rustchain_claim_job':
        result = await claimJob(args.job_id, args.worker_wallet);
        break;

      case 'rustchain_deliver_job':
        result = await deliverJob(args.job_id, {
          worker_wallet: args.worker_wallet,
          deliverable_url: args.deliverable_url,
          result_summary: args.result_summary,
        });
        break;

      case 'rustchain_accept_delivery':
        result = await acceptDelivery(args.job_id, args.poster_wallet);
        break;

      case 'rustchain_get_reputation':
        result = await getReputation(args.wallet);
        break;

      default:
        return {
          content: [
            {
              type: 'text',
              text: `Unknown tool: ${name}`,
            },
          ],
          isError: true,
        };
    }

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  } catch (error: any) {
    return {
      content: [
        {
          type: 'text',
          text: `Error: ${error.message}`,
        },
      ],
      isError: true,
    };
  }
});

// Start server
const transport = new StdioServerTransport();
await server.connect(transport);
