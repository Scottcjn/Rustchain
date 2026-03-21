/**
 * BoTTube MCP Server - Main Entry Point
 *
 * A Model Context Protocol (MCP) server that provides tools for
 * interacting with the BoTTube AI video platform.
 *
 * Usage:
 *   npx bottube-mcp-server
 *
 * Environment variables:
 *   BOTTUBE_API_KEY  - Optional API key for authenticated operations
 *                      (upload, comment, vote, register)
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';

import { BoTTubeClient } from './api.js';
import { getTools } from './tools.js';

// ---------------------------------------------------------------------------
// Server Bootstrap
// ---------------------------------------------------------------------------

const API_KEY = process.env.BOTTUBE_API_KEY;
const client = new BoTTubeClient(API_KEY);
const tools = getTools(client);

const server = new Server(
  {
    name: 'bottube-mcp-server',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {}, // Will be populated with our tool list
    },
  },
);

// ---------------------------------------------------------------------------
// Request Handlers
// ---------------------------------------------------------------------------

/**
 * ListToolsRequestSchema - Returns the list of all available MCP tools.
 */
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: tools.map((tool) => ({
      name: tool.name,
      description: tool.description,
      inputSchema: tool.inputSchema,
    })),
  };
});

/**
 * CallToolRequestSchema - Dispatches a tool call to the appropriate handler.
 */
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args = {} } = request.params;

  const tool = tools.find((t) => t.name === name);
  if (!tool) {
    return {
      content: [{ type: 'text', text: `Error: Unknown tool "${name}"` }],
      isError: true,
    };
  }

  // Validate required arguments
  const schema = tool.inputSchema;
  if (schema.required) {
    for (const required of schema.required) {
      if (!(required in args)) {
        return {
          content: [
            {
              type: 'text',
              text: `Error: Missing required argument "${required}" for tool "${name}"`,
            },
          ],
          isError: true,
        };
      }
    }
  }

  try {
    const result = await tool.handler(args);
    return result;
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    return {
      content: [{ type: 'text', text: `Error: ${message}` }],
      isError: true,
    };
  }
});

// ---------------------------------------------------------------------------
// Transport & Connect
// ---------------------------------------------------------------------------

const transport = new StdioServerTransport();

server.connect(transport).catch((err: unknown) => {
  const message = err instanceof Error ? err.message : String(err);
  console.error(`[bottube-mcp] Failed to connect transport: ${message}`);
  process.exit(1);
});
