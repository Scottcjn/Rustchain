#!/usr/bin/env python3
"""
RustChain MCP Server - Model Context Protocol
 Enables AI agents to interact with RustChain blockchain.
"""

import json
import asyncio
from typing import Any, Dict, List, Optional
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# RustChain API client
import requests

class RustChainClient:
    """RustChain API Client"""
    
    def __init__(self, base_url: str = "https://api.rustchain.io"):
        self.base_url = base_url
        self.timeout = 30
    
    def get_health(self) -> Dict[str, Any]:
        """Check node health"""
        try:
            r = requests.get(f"{self.base_url}/health", timeout=self.timeout)
            return r.json() if r.status_code == 200 else {"error": r.status_code}
        except Exception as e:
            return {"error": str(e)}
    
    def get_balance(self, address: str) -> Dict[str, Any]:
        """Get wallet balance"""
        try:
            r = requests.get(f"{self.base_url}/wallet/{address}/balance", timeout=self.timeout)
            return r.json() if r.status_code == 200 else {"error": r.status_code}
        except Exception as e:
            return {"error": str(e)}
    
    def get_block(self, height: Optional[int] = None) -> Dict[str, Any]:
        """Get block info"""
        try:
            url = f"{self.base_url}/block/latest" if height is None else f"{self.base_url}/block/{height}"
            r = requests.get(url, timeout=self.timeout)
            return r.json() if r.status_code == 200 else {"error": r.status_code}
        except Exception as e:
            return {"error": str(e)}
    
    def get_transaction(self, tx_hash: str) -> Dict[str, Any]:
        """Get transaction by hash"""
        try:
            r = requests.get(f"{self.base_url}/tx/{tx_hash}", timeout=self.timeout)
            return r.json() if r.status_code == 200 else {"error": r.status_code}
        except Exception as e:
            return {"error": str(e)}
    
    def get_stats(self) -> Dict[str, Any]:
        """Get blockchain statistics"""
        try:
            r = requests.get(f"{self.base_url}/stats", timeout=self.timeout)
            return r.json() if r.status_code == 200 else {"error": r.status_code}
        except Exception as e:
            return {"error": str(e)}


# Create MCP server
server = Server("rustchain-mcp")
client = RustChainClient()


@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available MCP tools"""
    return [
        Tool(
            name="rustchain_health",
            description="Check RustChain node health status",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="rustchain_balance",
            description="Get wallet balance for a RustChain address",
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "RustChain wallet address (starts with RTC)"
                    }
                },
                "required": ["address"]
            }
        ),
        Tool(
            name="rustchain_block",
            description="Get block information from RustChain",
            inputSchema={
                "type": "object",
                "properties": {
                    "height": {
                        "type": "integer",
                        "description": "Block height (optional, defaults to latest)"
                    }
                }
            }
        ),
        Tool(
            name="rustchain_transaction",
            description="Get transaction details by hash",
            inputSchema={
                "type": "object",
                "properties": {
                    "hash": {
                        "type": "string",
                        "description": "Transaction hash"
                    }
                },
                "required": ["hash"]
            }
        ),
        Tool(
            name="rustchain_stats",
            description="Get RustChain blockchain statistics",
            inputSchema={"type": "object", "properties": {}}
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute MCP tool"""
    try:
        if name == "rustchain_health":
            result = client.get_health()
        elif name == "rustchain_balance":
            result = client.get_balance(arguments["address"])
        elif name == "rustchain_block":
            result = client.get_block(arguments.get("height"))
        elif name == "rustchain_transaction":
            result = client.get_transaction(arguments["hash"])
        elif name == "rustchain_stats":
            result = client.get_stats()
        else:
            result = {"error": f"Unknown tool: {name}"}
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)})]


async def main():
    """Main entry point"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

# Bounty wallet: RTC27a4b8256b4d3c63737b27e96b181223cc8774ae
