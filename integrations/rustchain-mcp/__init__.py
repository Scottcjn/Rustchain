#!/usr/bin/env python3
"""
RustChain MCP - Model Context Protocol server for RustChain blockchain.

Provides AI assistants with tools to interact with RustChain:
- Health checks
- Epoch information
- Wallet balances
- Generic queries

Usage:
    python -m rustchain_mcp.mcp_server
"""

try:
    from .client import RustChainClient, get_balance, get_epoch, get_health, run_query
    from .schemas import (
        APIError,
        EpochInfo,
        HealthStatus,
        QueryResult,
        WalletBalance,
    )
except ImportError:
    from client import RustChainClient, get_balance, get_epoch, get_health, run_query
    from schemas import (
        APIError,
        EpochInfo,
        HealthStatus,
        QueryResult,
        WalletBalance,
    )

__version__ = "1.0.0"
__all__ = [
    # Client
    "RustChainClient",
    "get_health",
    "get_epoch",
    "get_balance",
    "run_query",
    # Schemas
    "HealthStatus",
    "EpochInfo",
    "WalletBalance",
    "QueryResult",
    "APIError",
]
