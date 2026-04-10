#!/usr/bin/env python3
"""
RustChain Bounties MCP Server

Model Context Protocol (MCP) server for RustChain blockchain.
Exposes 7 tools over stdio, compatible with Claude Code / Cursor / VS Code Copilot MCP clients.

Tools:
    rustchain_health            — Node health probe
    rustchain_balance           — Wallet balance by miner_id
    rustchain_miners            — List active miners
    rustchain_epoch             — Current epoch info
    rustchain_verify_wallet     — Verify wallet presence for a miner
    rustchain_submit_attestation — Submit hardware attestation
    rustchain_bounties          — List open bounties (via GitHub API)

Usage:
    python -m rustchain_bounties_mcp.mcp_server

Environment:
    RUSTCHAIN_NODE_URL  — Node base URL (default: https://50.28.86.131)
    RUSTCHAIN_TIMEOUT   — Request timeout seconds (default: 30)
    RUSTCHAIN_RETRY     — Retry count (default: 2)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any, Optional

# ---------------------------------------------------------------------------
# MCP SDK — graceful fallback when not installed (for unit testing)
# ---------------------------------------------------------------------------
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

    class _MockServer:  # type: ignore[no-redef]
        def __init__(self, name: str) -> None: ...
        def list_tools(self):  # type: ignore
            return lambda f: f
        def call_tool(self):  # type: ignore
            return lambda f: f
        async def run(self, *a: Any, **kw: Any) -> None: ...
        def create_initialization_options(self) -> Any:
            return {}

    Server = _MockServer  # type: ignore

    class _MockStdio:  # type: ignore
        async def __aenter__(self):
            return (None, None)
        async def __aexit__(self, *a: Any) -> None:
            pass

    stdio_server = _MockStdio  # type: ignore

    class TextContent:  # type: ignore[no-redef]
        def __init__(self, *, type: str, text: str) -> None:
            self.type = type
            self.text = text

    class Tool:  # type: ignore[no-redef]
        def __init__(self, *, name: str, description: str, inputSchema: dict[str, Any]) -> None:
            self.name = name
            self.description = description
            self.inputSchema = inputSchema


from .client import RustChainClient
from .schemas import (
    APIError,
    BALANCE_SCHEMA,
    BOUNTIES_SCHEMA,
    EPOCH_SCHEMA,
    HEALTH_SCHEMA,
    MINERS_SCHEMA,
    SUBMIT_ATTESTATION_SCHEMA,
    VERIFY_WALLET_SCHEMA,
)

# ---------------------------------------------------------------------------
# Logging — stderr so it doesn't interfere with stdio MCP protocol
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("rustchain-bounties-mcp")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_NODE_URL = os.getenv("RUSTCHAIN_NODE_URL", "https://50.28.86.131")


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
class RustchainBountiesMCP:
    """MCP server exposing 7 RustChain tools over stdio."""

    def __init__(self, node_url: Optional[str] = None) -> None:
        self.node_url = node_url or DEFAULT_NODE_URL
        self.app = Server("rustchain-bounties-mcp")
        self.client: Optional[RustChainClient] = None
        self._register_handlers()

    # -- lifecycle ----------------------------------------------------------

    async def start(self) -> None:
        self.client = RustChainClient(node_url=self.node_url)
        await self.client._ensure_session()
        logger.info("Started (node=%s)", self.node_url)

    async def stop(self) -> None:
        if self.client:
            await self.client.close()
        logger.info("Stopped")

    # -- handler registration -----------------------------------------------

    def _register_handlers(self) -> None:
        @self.app.list_tools()
        async def _list_tools() -> list[Tool]:
            return [
                Tool(
                    name="rustchain_health",
                    description="Check RustChain node health status (ok, version, uptime, db_rw, tip_age)",
                    inputSchema=HEALTH_SCHEMA,
                ),
                Tool(
                    name="rustchain_balance",
                    description="Get RTC wallet balance for a miner by miner_id",
                    inputSchema=BALANCE_SCHEMA,
                ),
                Tool(
                    name="rustchain_miners",
                    description="List active miners with optional hardware_type filter and pagination",
                    inputSchema=MINERS_SCHEMA,
                ),
                Tool(
                    name="rustchain_epoch",
                    description="Get current epoch information (epoch number, slot, enrolled miners, epoch_pot)",
                    inputSchema=EPOCH_SCHEMA,
                ),
                Tool(
                    name="rustchain_verify_wallet",
                    description="Verify wallet presence for a miner_id on RustChain (queries balance endpoint; wallets are auto-provisioned on first activity)",
                    inputSchema=VERIFY_WALLET_SCHEMA,
                ),
                Tool(
                    name="rustchain_submit_attestation",
                    description="Submit a hardware attestation for a miner (device fingerprint required)",
                    inputSchema=SUBMIT_ATTESTATION_SCHEMA,
                ),
                Tool(
                    name="rustchain_bounties",
                    description="List RustChain bounties (default: open bounties)",
                    inputSchema=BOUNTIES_SCHEMA,
                ),
            ]

        @self.app.call_tool()
        async def _call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            handler = getattr(self, f"_tool_{name}", None)
            if handler is None:
                return [self._err(f"Unknown tool: {name}")]
            try:
                result = await handler(arguments)
                return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
            except APIError as exc:
                logger.error("APIError %s: %s", name, exc.message)
                return [TextContent(type="text", text=json.dumps(exc.to_dict(), indent=2))]
            except Exception as exc:
                logger.exception("Tool error %s", name)
                return [self._err(f"{name} failed: {exc}")]

    # -- tool implementations -----------------------------------------------

    async def _tool_rustchain_health(self, _args: dict[str, Any]) -> dict[str, Any]:
        h = await self._require_client().health()
        return {
            "ok": h.ok,
            "healthy": h.is_healthy,
            "version": h.version,
            "uptime_s": h.uptime_s,
            "db_rw": h.db_rw,
            "backup_age_hours": h.backup_age_hours,
            "tip_age_slots": h.tip_age_slots,
        }

    async def _tool_rustchain_balance(self, args: dict[str, Any]) -> dict[str, Any]:
        miner_id = args.get("miner_id", "")
        b = await self._require_client().balance(miner_id)
        return {
            "miner_id": b.miner_id,
            "amount_rtc": b.amount_rtc,
            "amount_i64": b.amount_i64,
        }

    async def _tool_rustchain_miners(self, args: dict[str, Any]) -> dict[str, Any]:
        limit = args.get("limit", 50)
        hw = args.get("hardware_type")
        result = await self._require_client().miners(limit=limit, hardware_type=hw)
        miners_out = []
        for m in result["miners"]:
            miners_out.append({
                "miner": m.miner,
                "hardware_type": m.hardware_type,
                "device_family": m.device_family,
                "device_arch": m.device_arch,
                "antiquity_multiplier": m.antiquity_multiplier,
                "entropy_score": m.entropy_score,
                "last_attest": m.last_attest,
                "epochs_mined": m.epochs_mined,
            })
        return {
            "total_count": result["total_count"],
            "limit": result["limit"],
            "offset": result["offset"],
            "miners": miners_out,
        }

    async def _tool_rustchain_epoch(self, _args: dict[str, Any]) -> dict[str, Any]:
        e = await self._require_client().epoch()
        return {
            "epoch": e.epoch,
            "slot": e.slot,
            "epoch_pot": e.epoch_pot,
            "enrolled_miners": e.enrolled_miners,
            "blocks_per_epoch": e.blocks_per_epoch,
            "total_supply_rtc": e.total_supply_rtc,
        }

    async def _tool_rustchain_verify_wallet(self, args: dict[str, Any]) -> dict[str, Any]:
        miner_id = args.get("miner_id", "")
        r = await self._require_client().verify_wallet(miner_id)
        return {
            "wallet_address": r.wallet_address,
            "exists": r.exists,
            "balance_rtc": r.balance_rtc,
            "message": r.message,
        }

    async def _tool_rustchain_submit_attestation(self, args: dict[str, Any]) -> dict[str, Any]:
        miner_id = args.get("miner_id", "")
        device = args.get("device")
        if not device or not isinstance(device, dict):
            return {"error": "VALIDATION_ERROR", "message": "device is required and must be a dict"}
        r = await self._require_client().submit_attestation(
            miner_id=miner_id,
            device=device,
            signature=args.get("signature"),
            public_key=args.get("public_key"),
        )
        out: dict[str, Any] = {"ok": r.ok, "message": r.message}
        if r.miner_id:
            out["miner_id"] = r.miner_id
        if r.enrolled_epoch is not None:
            out["enrolled_epoch"] = r.enrolled_epoch
        return out

    async def _tool_rustchain_bounties(self, args: dict[str, Any]) -> dict[str, Any]:
        status = args.get("status", "open")
        limit = args.get("limit", 50)
        bounties = await self._require_client().bounties(status=status, limit=limit)
        return {
            "count": len(bounties),
            "source": "github:Scottcjn/rustchain-bounties",
            "bounties": [
                {
                    "issue_number": b.issue_number,
                    "title": b.title,
                    "reward_rtc": b.reward_rtc,
                    "status": b.status,
                    "url": b.url,
                    "difficulty": b.difficulty,
                    "tags": b.tags,
                }
                for b in bounties
            ],
        }

    # -- helpers ------------------------------------------------------------

    def _require_client(self) -> RustChainClient:
        if self.client is None:
            raise RuntimeError("Client not initialized — call start() first")
        return self.client

    @staticmethod
    def _err(msg: str) -> TextContent:
        return TextContent(type="text", text=json.dumps({"error": msg}, indent=2))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
async def main() -> None:
    if not MCP_AVAILABLE:
        logger.error("MCP SDK not installed.  Install with: pip install mcp>=1.0.0")
        sys.exit(1)

    node_url = os.getenv("RUSTCHAIN_NODE_URL", DEFAULT_NODE_URL)
    server = RustchainBountiesMCP(node_url=node_url)

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


def entry() -> None:
    """Console-script entry (pyproject [project.scripts])."""
    asyncio.run(main())


if __name__ == "__main__":
    main()
