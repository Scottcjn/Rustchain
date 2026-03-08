import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import axios from 'axios';

// Node configuration
const NODES = [
  'https://50.28.86.131',  // Primary
  'https://50.28.87.10',   // Node 2
  'https://50.28.87.75',   // Node 3
];
let currentNodeIndex = 0;

function getApiBase(): string {
  return NODES[currentNodeIndex];
}

function switchNode(): string {
  currentNodeIndex = (currentNodeIndex + 1) % NODES.length;
  return getApiBase();
}

async function apiRequest(endpoint: string, method: 'GET' | 'POST' = 'GET', data?: any): Promise<any> {
  let lastError: Error | null = null;
  
  for (let attempt = 0; attempt < NODES.length; attempt++) {
    try {
      const baseUrl = getApiBase();
      const url = `${baseUrl}${endpoint}`;
      
      const response = method === 'GET' 
        ? await axios.get(url, { timeout: 10000 })
        : await axios.post(url, data, { timeout: 10000 });
      
      return response.data;
    } catch (error: any) {
      lastError = error;
      console.error(`Node ${getApiBase()} failed: ${error.message}`);
      switchNode();
    }
  }
  
  throw new Error(`All nodes failed. Last error: ${lastError?.message}`);
}

// Tool definitions - Required (75 RTC)
const tools = [
  {
    name: 'rustchain_balance',
    description: 'Check RTC balance for any wallet address on RustChain',
    inputSchema: {
      type: 'object',
      properties: {
        miner_id: {
          type: 'string',
          description: 'Wallet/miner ID to check balance for',
        },
      },
      required: ['miner_id'],
    },
  },
  {
    name: 'rustchain_miners',
    description: 'List active miners on RustChain with their hardware info',
    inputSchema: {
      type: 'object',
      properties: {
        limit: {
          type: 'number',
          description: 'Maximum number of miners to return',
          default: 20,
        },
      },
    },
  },
  {
    name: 'rustchain_epoch',
    description: 'Get current epoch information including slot, height, rewards, and supply',
    inputSchema: {
      type: 'object',
      properties: {},
    },
  },
  {
    name: 'rustchain_health',
    description: 'Check health status of all attestation nodes',
    inputSchema: {
      type: 'object',
      properties: {},
    },
  },
  {
    name: 'rustchain_transfer',
    description: 'Transfer RTC to another wallet (requires private key)',
    inputSchema: {
      type: 'object',
      properties: {
        from_private_key: {
          type: 'string',
          description: 'Sender private key',
        },
        to_miner_id: {
          type: 'string',
          description: 'Recipient wallet/miner ID',
        },
        amount: {
          type: 'number',
          description: 'Amount of RTC to transfer',
        },
      },
      required: ['from_private_key', 'to_miner_id', 'amount'],
    },
  },
  // Bonus tools (for 100 RTC)
  {
    name: 'rustchain_ledger',
    description: 'Query transaction history for a wallet',
    inputSchema: {
      type: 'object',
      properties: {
        miner_id: {
          type: 'string',
          description: 'Wallet/miner ID to query',
        },
        limit: {
          type: 'number',
          description: 'Maximum transactions to return',
          default: 20,
        },
      },
      required: ['miner_id'],
    },
  },
  {
    name: 'rustchain_register_wallet',
    description: 'Register/create a new wallet on RustChain',
    inputSchema: {
      type: 'object',
      properties: {
        miner_id: {
          type: 'string',
          description: 'Desired miner ID / wallet name',
        },
        private_key: {
          type: 'string',
          description: 'Private key for the wallet (optional, one will be generated if not provided)',
        },
      },
      required: ['miner_id'],
    },
  },
  {
    name: 'rustchain_bounties',
    description: 'List open bounties from RustChain bounties repository',
    inputSchema: {
      type: 'object',
      properties: {
        limit: {
          type: 'number',
          description: 'Maximum bounties to return',
          default: 10,
        },
      },
    },
  },
];

// API helper functions
async function getBalance(minerId: string) {
  return apiRequest(`/wallet/balance?miner_id=${encodeURIComponent(minerId)}`);
}

async function getMiners(limit: number = 20) {
  const data = await apiRequest('/api/miners');
  return Array.isArray(data) ? data.slice(0, limit) : data;
}

async function getEpoch() {
  return apiRequest('/epoch');
}

async function getHealth() {
  const results = await Promise.allSettled(
    NODES.map(async (node) => {
      try {
        const response = await axios.get(`${node}/health`, { timeout: 5000 });
        return { node, ...response.data, reachable: true };
      } catch (error: any) {
        return { node, ok: false, reachable: false, error: error.message };
      }
    })
  );
  
  return results.map((r: any) => r.value || r.reason);
}

async function transfer(fromPrivateKey: string, toMinerId: string, amount: number) {
  return apiRequest('/wallet/transfer', 'POST', {
    from_private_key: fromPrivateKey,
    to_miner_id: toMinerId,
    amount,
  });
}

async function getLedger(minerId: string, limit: number = 20) {
  try {
    const data = await apiRequest(`/wallet/ledger?miner_id=${encodeURIComponent(minerId)}`);
    return Array.isArray(data) ? data.slice(0, limit) : data;
  } catch (error: any) {
    // Ledger endpoint might not exist, return empty array
    return { error: 'Ledger not available', transactions: [] };
  }
}

async function registerWallet(minerId: string, privateKey?: string) {
  const data: any = { miner_id: minerId };
  if (privateKey) {
    data.private_key = privateKey;
  }
  return apiRequest('/wallet/register', 'POST', data);
}

async function getBounties(limit: number = 10) {
  try {
    // Fetch from GitHub API
    const response = await axios.get(
      'https://api.github.com/repos/Scottcjn/rustchain-bounties/issues',
      {
        params: { state: 'open', per_page: limit },
        headers: { 'Accept': 'application/vnd.github.v3+json' },
        timeout: 10000,
      }
    );
    
    return response.data.map((issue: any) => ({
      number: issue.number,
      title: issue.title,
      labels: issue.labels.map((l: any) => l.name),
      url: issue.html_url,
      created_at: issue.created_at,
    }));
  } catch (error: any) {
    return { error: error.message };
  }
}

// Create server
const server = new Server(
  {
    name: 'rustchain-mcp',
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
  const { name, arguments: args = {} } = request.params as { name: string; arguments?: Record<string, any> };

  try {
    let result;

    switch (name) {
      case 'rustchain_balance':
        result = await getBalance(args.miner_id as string);
        break;

      case 'rustchain_miners':
        result = await getMiners((args.limit as number) || 20);
        break;

      case 'rustchain_epoch':
        result = await getEpoch();
        break;

      case 'rustchain_health':
        result = await getHealth();
        break;

      case 'rustchain_transfer':
        result = await transfer(args.from_private_key as string, args.to_miner_id as string, args.amount as number);
        break;

      case 'rustchain_ledger':
        result = await getLedger(args.miner_id as string, (args.limit as number) || 20);
        break;

      case 'rustchain_register_wallet':
        result = await registerWallet(args.miner_id as string, args.private_key as string | undefined);
        break;

      case 'rustchain_bounties':
        result = await getBounties((args.limit as number) || 10);
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
