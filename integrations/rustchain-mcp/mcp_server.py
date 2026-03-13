#!/usr/bin/env python3
"""
RustChain MCP Server

Model Context Protocol (MCP) server for RustChain blockchain.
Provides tools for health checks, epoch info, wallet balances, and queries.

Usage:
    python -m rustchain_mcp.mcp_server

Or via MCP client configuration pointing to this module.
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Optional

# MCP SDK imports with fallback for testing
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        Prompt,
        Resource,
        ResourceTemplate,
        TextContent,
        Tool,
    )
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    # Mock classes for testing without MCP SDK
    class _MockServer:
        def __init__(self, name): pass
        def list_tools(self): return lambda f: f
        def list_resources(self): return lambda f: f
        def list_resource_templates(self): return lambda f: f
        def list_prompts(self): return lambda f: f
        def call_tool(self): return lambda f: f
        def read_resource(self): return lambda f: f
        async def run(self, *args): pass
        def create_initialization_options(self): return {}
    Server = _MockServer

    class _MockStdio:
        async def __aenter__(self): return (None, None)
        async def __aexit__(self, *args): pass
    stdio_server = _MockStdio

    class Prompt:
        def __init__(self, name, description, arguments=None):
            self.name = name
            self.description = description
            self.arguments = arguments or []
    
    class Resource:
        def __init__(self, uri, name, description, mimeType):
            self.uri = uri
            self.name = name
            self.description = description
            self.mimeType = mimeType
    
    class ResourceTemplate:
        def __init__(self, uriTemplate, name, description):
            self.uriTemplate = uriTemplate
            self.name = name
            self.description = description
    
    class TextContent:
        def __init__(self, type, text):
            self.type = type
            self.text = text
    
    class Tool:
        def __init__(self, name, description, inputSchema):
            self.name = name
            self.description = description
            self.inputSchema = inputSchema

# Import client and schemas
try:
    from .client import RustChainClient
    from .schemas import (
        APIError,
        BALANCE_SCHEMA,
        EPOCH_SCHEMA,
        HEALTH_SCHEMA,
        QUERY_SCHEMA,
        HealthStatus,
        EpochInfo,
        WalletBalance,
        QueryResult,
    )
except ImportError:
    from client import RustChainClient
    from schemas import (
        APIError,
        BALANCE_SCHEMA,
        EPOCH_SCHEMA,
        HEALTH_SCHEMA,
        QUERY_SCHEMA,
        HealthStatus,
        EpochInfo,
        WalletBalance,
        QueryResult,
    )

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("rustchain-mcp")

# Configuration from environment
RUSTCHAIN_API_BASE = os.getenv("RUSTCHAIN_API_BASE", "https://50.28.86.131")
RUSTCHAIN_NODE_URL = os.getenv("RUSTCHAIN_NODE_URL", "https://50.28.86.131:5000")


class RustChainMCP:
    """RustChain MCP Server implementation."""

    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize MCP server.

        Args:
            base_url: Optional override for RustChain API base URL
        """
        self.base_url = base_url or RUSTCHAIN_API_BASE
        self.app = Server("rustchain-mcp")
        self.client: Optional[RustChainClient] = None
        self._setup_handlers()

    async def start(self) -> None:
        """Initialize client session."""
        self.client = RustChainClient(base_url=self.base_url)
        await self.client._ensure_session()
        logger.info(f"RustChain MCP Server started (API: {self.base_url})")

    async def stop(self) -> None:
        """Cleanup resources."""
        if self.client:
            await self.client.close()
        logger.info("RustChain MCP Server stopped")

    def _setup_handlers(self) -> None:
        """Setup MCP request handlers."""

        # List available tools
        @self.app.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="rustchain_health",
                    description="Check RustChain API health status and service availability",
                    inputSchema=HEALTH_SCHEMA,
                ),
                Tool(
                    name="rustchain_epoch",
                    description="Get current epoch information or details for a specific epoch",
                    inputSchema=EPOCH_SCHEMA,
                ),
                Tool(
                    name="rustchain_balance",
                    description="Get RTC wallet balance for a miner by ID or wallet name",
                    inputSchema=BALANCE_SCHEMA,
                ),
                Tool(
                    name="rustchain_query",
                    description="Execute a generic query against RustChain (miners, blocks, transactions)",
                    inputSchema=QUERY_SCHEMA,
                ),
            ]

        # List available resources
        @self.app.list_resources()
        async def list_resources() -> list[Resource]:
            return [
                Resource(
                    uri="rustchain://health",
                    name="RustChain Health Status",
                    description="Current health status of RustChain API",
                    mimeType="application/json",
                ),
                Resource(
                    uri="rustchain://epoch/current",
                    name="Current Epoch",
                    description="Information about the current epoch",
                    mimeType="application/json",
                ),
                Resource(
                    uri="rustchain://docs/api",
                    name="API Documentation",
                    description="Quick reference for RustChain API endpoints",
                    mimeType="text/markdown",
                ),
            ]

        # List resource templates
        @self.app.list_resource_templates()
        async def list_resource_templates() -> list[ResourceTemplate]:
            return [
                ResourceTemplate(
                    uriTemplate="rustchain://epoch/{epoch_number}",
                    name="Epoch Information",
                    description="Get information about a specific epoch",
                ),
                ResourceTemplate(
                    uriTemplate="rustchain://wallet/{miner_id}",
                    name="Wallet Balance",
                    description="Get wallet balance for a specific miner",
                ),
            ]

        # List available prompts
        @self.app.list_prompts()
        async def list_prompts() -> list[Prompt]:
            return [
                Prompt(
                    name="check_rustchain_status",
                    description="Check RustChain network health and current epoch",
                    arguments=[],
                ),
                Prompt(
                    name="check_wallet_balance",
                    description="Check RTC balance for a wallet",
                    arguments=[
                        {
                            "name": "miner_id",
                            "description": "Miner ID or wallet name",
                            "required": True,
                        }
                    ],
                ),
                Prompt(
                    name="query_miners",
                    description="Query miners with optional filters",
                    arguments=[
                        {
                            "name": "hardware_type",
                            "description": "Filter by hardware (e.g., 'PowerPC G4')",
                            "required": False,
                        },
                        {
                            "name": "min_score",
                            "description": "Minimum score threshold",
                            "required": False,
                        },
                    ],
                ),
            ]

        # Handle tool calls
        @self.app.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            handler = getattr(self, f"_tool_{name}", None)
            if not handler:
                raise ValueError(f"Unknown tool: {name}")

            try:
                result = await handler(arguments)
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            except APIError as e:
                logger.error(f"API error {name}: {e.code} - {e.message}")
                return [TextContent(type="text", text=json.dumps(e.to_dict(), indent=2))]
            except Exception as e:
                logger.error(f"Tool error {name}: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        # Handle resource reads
        @self.app.read_resource()
        async def read_resource(uri: str) -> tuple[str, str]:
            try:
                result = await self._read_resource_impl(uri)
                return result
            except Exception as e:
                logger.error(f"Resource error {uri}: {e}")
                raise

    # Tool implementations

    async def _tool_rustchain_health(self, args: dict[str, Any]) -> dict[str, Any]:
        """Check API health status."""
        if not self.client:
            return {"error": "Client not initialized"}
        
        health = await self.client.health()
        return {
            "status": health.status,
            "healthy": health.is_healthy,
            "timestamp": health.timestamp,
            "service": health.service,
            "version": health.version,
            "uptime_s": health.uptime_s,
        }

    async def _tool_rustchain_epoch(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get epoch information."""
        if not self.client:
            return {"error": "Client not initialized"}
        
        epoch_num = args.get("epoch")
        epoch_info = await self.client.epoch(epoch_num)
        
        result = {
            "epoch": epoch_info.epoch,
            "slot": epoch_info.slot,
            "height": epoch_info.height,
        }
        if epoch_info.start_time:
            result["start_time"] = epoch_info.start_time
        if epoch_info.end_time:
            result["end_time"] = epoch_info.end_time
        if epoch_info.status:
            result["status"] = epoch_info.status
        
        return result

    async def _tool_rustchain_balance(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get wallet balance."""
        if not self.client:
            return {"error": "Client not initialized"}
        
        miner_id = args.get("miner_id", "")
        if not miner_id:
            return {"error": "miner_id is required"}
        
        balance = await self.client.balance(miner_id)
        return {
            "miner_id": balance.miner_id,
            "balance_rtc": balance.amount_rtc,
            "balance_i64": balance.amount_i64,
            "total_rtc": balance.total_rtc,
            "pending": balance.pending,
            "staked": balance.staked,
        }

    async def _tool_rustchain_query(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute generic query."""
        if not self.client:
            return {"error": "Client not initialized"}
        
        query_type = args.get("query_type", "")
        if not query_type:
            return {"error": "query_type is required"}
        
        params = args.get("params", {})
        limit = args.get("limit", 50)
        
        result = await self.client.query(query_type, params, limit)
        return {
            "success": result.success,
            "query_type": result.query_type or query_type,
            "count": result.count,
            "data": result.data,
            "error": result.error,
        }

    # Resource implementations

    async def _read_resource_impl(self, uri: str) -> tuple[str, str]:
        """Read resource implementation."""
        if not self.client:
            raise ValueError("Client not initialized")

        if uri == "rustchain://health":
            health = await self.client.health()
            data = {
                "status": health.status,
                "healthy": health.is_healthy,
                "timestamp": health.timestamp,
                "service": health.service,
                "version": health.version,
                "uptime_s": health.uptime_s,
            }
            return json.dumps(data, indent=2), "application/json"

        elif uri == "rustchain://epoch/current":
            epoch = await self.client.epoch()
            data = {
                "epoch": epoch.epoch,
                "slot": epoch.slot,
                "height": epoch.height,
            }
            return json.dumps(data, indent=2), "application/json"

        elif uri == "rustchain://docs/api":
            content = self._get_api_docs()
            return content, "text/markdown"

        # Handle templates
        elif uri.startswith("rustchain://epoch/"):
            epoch_str = uri.split("/")[-1]
            if epoch_str.isdigit():
                epoch = await self.client.epoch(int(epoch_str))
                data = {
                    "epoch": epoch.epoch,
                    "slot": epoch.slot,
                    "height": epoch.height,
                }
                return json.dumps(data, indent=2), "application/json"
            raise ValueError(f"Invalid epoch number: {epoch_str}")

        elif uri.startswith("rustchain://wallet/"):
            miner_id = uri.split("/")[-1]
            balance = await self.client.balance(miner_id)
            data = {
                "miner_id": balance.miner_id,
                "balance_rtc": balance.amount_rtc,
                "balance_i64": balance.amount_i64,
            }
            return json.dumps(data, indent=2), "application/json"

        raise ValueError(f"Unknown resource: {uri}")

    def _get_api_docs(self) -> str:
        """Return API quick reference documentation."""
        return """# RustChain API Quick Reference

## Endpoints

### Health Check
```
GET /api/health
```
Returns service health status.

### Epoch Info
```
GET /epoch              # Current epoch
GET /api/epochs/{n}     # Specific epoch
```

### Wallet Balance
```
GET /wallet/balance?miner_id={id}
```
Returns balance in RTC.

### Query
```
GET /api/query?type={type}&limit={n}
```
Generic query endpoint for miners, blocks, transactions.

## Response Formats

### Health
```json
{
  "status": "ok",
  "timestamp": 1234567890,
  "service": "beacon-atlas-api",
  "version": "2.2.1"
}
```

### Epoch
```json
{
  "epoch": 95,
  "slot": 12345,
  "height": 67890
}
```

### Balance
```json
{
  "miner_id": "scott",
  "amount_rtc": 155.0,
  "amount_i64": 155000000
}
```

## Rate Limits
- Health: 60/min
- Epoch/Balance: 30/min
- Query: 30/min

## Notes
- Self-signed certificate: use `-k` with curl
- All amounts in RTC (1 RTC = 1,000,000 smallest units)
"""


async def main() -> None:
    """Main entry point."""
    if not MCP_AVAILABLE:
        logger.error("MCP SDK not available. Install with: pip install mcp")
        sys.exit(1)

    server = RustChainMCP()
    
    try:
        await server.start()
        async with stdio_server() as (read_stream, write_stream):
            await server.app.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
