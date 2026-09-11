# SPDX-License-Identifier: MIT
"""RustChain LangChain tools.

A LangChain ``BaseTool`` exposing read-only RustChain node endpoints so an
LLM agent can check wallet balances, list ecosystem bounties, inspect node
health, and read the current epoch — all against the public RustChain node
(https://rustchain.org, wallet = any string, no auth).

Dependencies: ``langchain-core`` and ``httpx`` (or ``requests``).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

try:  # httpx preferred (async-capable), fall back to requests
    import httpx

    _HTTPX = True
except ImportError:  # pragma: no cover - environment fallback
    httpx = None  # type: ignore[assignment]
    _HTTPX = False
    import requests

DEFAULT_NODE = "https://rustchain.org"
DEFAULT_BOUNTIES_REPO = "Scottcjn/rustchain-bounties"
TIMEOUT_S = 15.0


class _Client:
    """Tiny sync HTTP helper so the tools don't drag in a full SDK."""

    def __init__(self, node_url: str, timeout: float = TIMEOUT_S, headers: Optional[Dict[str, str]] = None):
        self.node_url = node_url.rstrip("/")
        self.timeout = timeout
        self.headers = headers or {}

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.node_url}{path}"
        try:
            if _HTTPX:
                resp = httpx.get(url, params=params, headers=self.headers, timeout=self.timeout)
            else:
                resp = requests.get(url, params=params, headers=self.headers, timeout=self.timeout)
            resp.raise_for_status()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        try:
            return resp.json()
        except ValueError:
            return {"ok": False, "error": "non_json_response", "status": resp.status_code}


# ---------------------------------------------------------------------------
# Schemas (pydantic) — one input schema per tool improves tool-call reliability.
# ---------------------------------------------------------------------------

class CheckBalanceInput(BaseModel):
    wallet_id: str = Field(
        description="The RustChain wallet id / miner address to look up. "
        "Any string wallet is accepted (agent-native, no auth)."
    )


class ListBountiesInput(BaseModel):
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of open bounties to return.",
    )


class GetNodeHealthInput(BaseModel):
    pass


class GetCurrentEpochInput(BaseModel):
    pass


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

class RustChainBalanceTool(BaseTool):
    """Check the RTC balance of a RustChain wallet."""

    name: str = "rustchain_check_balance"
    description: str = (
        "Check the RTC balance of a RustChain wallet id. "
        "Returns the balance in RTC (and the raw integer amount). "
        "Use for questions like 'how much RTC does wallet X hold?'."
    )
    args_schema: type[BaseModel] = CheckBalanceInput

    node_url: str = DEFAULT_NODE

    def _run(self, wallet_id: str) -> str:
        client = _Client(self.node_url)
        data = client.get(
            "/wallet/balance", params={"miner_id": wallet_id}
        )
        if not data.get("ok", True):
            return json.dumps({"ok": False, "error": data.get("error", "unknown")})
        return json.dumps(
            {
                "ok": True,
                "wallet_id": data.get("miner_id", wallet_id),
                "balance_rtc": data.get("amount_rtc", 0.0),
                "balance_raw": data.get("amount_i64", 0),
            }
        )


class RustChainBountiesTool(BaseTool):
    """List open RustChain ecosystem bounties."""

    name: str = "rustchain_list_bounties"
    description: str = (
        "List currently open RustChain ecosystem bounties (Earn RTC by "
        "contributing: code, docs, security, community). Returns the most "
        "recent open bounties with their issue number, title, and labels."
    )
    args_schema: type[BaseModel] = ListBountiesInput

    bounties_repo: str = DEFAULT_BOUNTIES_REPO

    def _run(self, limit: int = 10) -> str:
        # Bounties are tracked as GitHub issues labelled ``bounty`` in the
        # rustchain-bounties repo. Use the public GitHub REST API.
        # Reads GH_TOKEN or GITHUB_TOKEN from the environment for higher
        # rate limits (optional — the endpoint is unauthenticated-friendly).
        headers = {}
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
        if token:
            headers["Authorization"] = f"Bearer {token}"
        client = _Client("https://api.github.com", headers=headers)
        data = client.get(
            f"/repos/{self.bounties_repo}/issues",
            params={"state": "open", "labels": "bounty", "per_page": limit},
        )
        if isinstance(data, list):
            items = []
            for issue in data:
                items.append(
                    {
                        "number": issue.get("number"),
                        "title": issue.get("title"),
                        "url": issue.get("html_url"),
                        "labels": [
                            lbl.get("name")
                            for lbl in issue.get("labels", [])
                        ],
                    }
                )
            return json.dumps({"ok": True, "count": len(items), "bounties": items})
        return json.dumps({"ok": False, "error": str(data)})


class RustChainNodeHealthTool(BaseTool):
    """Read RustChain node health status."""

    name: str = "rustchain_get_node_health"
    description: str = (
        "Get the current health status of the RustChain public node: "
        "database read/write availability, tip age, uptime, and version. "
        "Use to answer 'is RustChain up / healthy?'."
    )
    args_schema: type[BaseModel] = GetNodeHealthInput

    node_url: str = DEFAULT_NODE

    def _run(self) -> str:
        client = _Client(self.node_url)
        data = client.get("/health")
        return json.dumps(data)


class RustChainCurrentEpochTool(BaseTool):
    """Read the current RustChain epoch."""

    name: str = "rustchain_get_current_epoch"
    description: str = (
        "Get the current RustChain epoch, current slot, enrolled miner count, "
        "and per-epoch RTC emission. Use for questions about the current "
        "consensus epoch / mining round."
    )
    args_schema: type[BaseModel] = GetCurrentEpochInput

    node_url: str = DEFAULT_NODE

    def _run(self) -> str:
        client = _Client(self.node_url)
        data = client.get("/epoch")
        return json.dumps(data)


# Handy collection for loading all tools at once.
ALL_RUSTCHAIN_TOOLS: List[BaseTool] = [
    RustChainBalanceTool(),
    RustChainBountiesTool(),
    RustChainNodeHealthTool(),
    RustChainCurrentEpochTool(),
]


def get_tools(node_url: str = DEFAULT_NODE, bounties_repo: str = DEFAULT_BOUNTIES_REPO) -> List[BaseTool]:
    """Return a fresh list of all RustChain tools with custom endpoints.

    Args:
        node_url: RustChain node base URL (defaults to the public node).
        bounties_repo: ``owner/repo`` of the bounty issue tracker
            (defaults to Scottcjn/rustchain-bounties).
    """
    return [
        RustChainBalanceTool(node_url=node_url),
        RustChainBountiesTool(bounties_repo=bounties_repo),
        RustChainNodeHealthTool(node_url=node_url),
        RustChainCurrentEpochTool(node_url=node_url),
    ]


__all__ = [
    "RustChainBalanceTool",
    "RustChainBountiesTool",
    "RustChainNodeHealthTool",
    "RustChainCurrentEpochTool",
    "ALL_RUSTCHAIN_TOOLS",
    "get_tools",
]