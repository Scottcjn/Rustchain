"""
LangChain `BaseTool` and `RustChainToolkit` implementation for RustChain (`Bounty #3074`).

Supports both `langchain_core.tools.BaseTool` (when installed) and a zero-dependency
compatible `BaseTool` shim so unit tests and lightweight agents run in any Python environment.
"""

from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Type

try:
    from langchain_core.tools import BaseTool  # type: ignore
except ImportError:
    class BaseTool:  # type: ignore
        """Lightweight BaseTool fallback when `langchain_core` is not installed."""
        name: str = "base_tool"
        description: str = ""

        def __init__(self, **kwargs: Any) -> None:
            for k, v in kwargs.items():
                setattr(self, k, v)

        def invoke(self, input_data: Any = None, **kwargs: Any) -> Any:
            if isinstance(input_data, dict):
                return self._run(**input_data)
            if isinstance(input_data, str):
                return self._run(input_data)
            return self._run(**kwargs)

        def run(self, tool_input: Any = None, **kwargs: Any) -> Any:
            return self.invoke(tool_input, **kwargs)


DEFAULT_NODE_URLS = (
    "https://rustchain.org",
    "https://50.28.86.131",
)
BOUNTIES_API_URL = "https://api.github.com/repos/Scottcjn/rustchain-bounties/issues"
RTC_REWARD_RE = re.compile(r"(\d+(?:\.\d+)?)\s*RTC", re.IGNORECASE)


class RustChainTool(BaseTool):
    """
    Native LangChain tool for interacting with the RustChain Mainnet node and bounty board.

    Exposes:
      - `check_balance(wallet_id: str) -> float`
      - `list_bounties(limit: int = 10) -> list[dict]`
      - `get_node_health() -> dict`
      - `get_current_epoch() -> dict`
    """

    name: str = "rustchain"
    description: str = (
        "Interact with the RustChain Proof-of-Antiquity blockchain and bounty board: "
        "check RTC wallet balances, inspect node health and current epoch, and list open RTC bounties."
    )
    node_url: str = "https://50.28.86.131"
    fallback_node_url: str = "https://rustchain.org"
    verify_ssl: bool = False
    timeout: int = 15

    def _http_get_json(self, url: str, headers: Optional[Dict[str, str]] = None) -> Any:
        ctx = None if self.verify_ssl else ssl._create_unverified_context()
        req_headers = {
            "User-Agent": "langchain-rustchain/0.2.0",
            "Accept": "application/json",
        }
        if headers:
            req_headers.update(headers)
        req = urllib.request.Request(url, headers=req_headers, method="GET")
        with urllib.request.urlopen(req, context=ctx, timeout=self.timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}

    def _node_get(self, path: str) -> Dict[str, Any]:
        last_err: Optional[Exception] = None
        for base in (self.node_url, self.fallback_node_url):
            if not base:
                continue
            url = f"{base.rstrip('/')}/{path.lstrip('/')}"
            try:
                data = self._http_get_json(url)
                if isinstance(data, dict):
                    return data
            except Exception as e:
                last_err = e
        raise RuntimeError(f"RustChain node request failed for {path}: {last_err}")

    def check_balance(self, wallet_id: str) -> float:
        """Query the RTC balance of a RustChain wallet or miner ID."""
        if not wallet_id or not isinstance(wallet_id, str) or not wallet_id.strip():
            raise ValueError("wallet_id must be a non-empty string")
        encoded = urllib.parse.quote(wallet_id.strip())
        data = self._node_get(f"/wallet/balance?miner_id={encoded}")
        for key in ("amount_rtc", "balance_rtc", "balance", "rtc"):
            if key in data and data[key] is not None:
                return float(data[key])
        if "amount_i64" in data and data["amount_i64"] is not None:
            return round(float(data["amount_i64"]) / 1_000_000.0, 6)
        return 0.0

    def get_node_health(self) -> Dict[str, Any]:
        """Return live `/health` status from the RustChain Mainnet node."""
        return self._node_get("/health")

    def get_current_epoch(self) -> Dict[str, Any]:
        """Return live `/epoch` telemetry from the RustChain Mainnet node."""
        return self._node_get("/epoch")

    def list_bounties(self, limit: int = 10) -> List[Dict[str, Any]]:
        """List open bounties from `Scottcjn/rustchain-bounties` with parsed RTC rewards."""
        if limit <= 0:
            return []
        per_page = min(max(limit * 2, 20), 100)
        url = f"{BOUNTIES_API_URL}?state=open&labels=bounty&per_page={per_page}"
        raw_issues = self._http_get_json(url)
        if not isinstance(raw_issues, list):
            return []
        bounties: List[Dict[str, Any]] = []
        for iss in raw_issues:
            if not isinstance(iss, dict) or "pull_request" in iss:
                continue
            title = iss.get("title") or ""
            body = iss.get("body") or ""
            m = RTC_REWARD_RE.search(title) or RTC_REWARD_RE.search(body[:400])
            reward_rtc = float(m.group(1)) if m else 0.0
            bounties.append(
                {
                    "issue_number": int(iss["number"]),
                    "title": title,
                    "reward_rtc": reward_rtc,
                    "url": iss.get("html_url") or f"https://github.com/Scottcjn/rustchain-bounties/issues/{iss['number']}",
                    "labels": [lbl.get("name", "") for lbl in iss.get("labels", []) if isinstance(lbl, dict)],
                    "comments": int(iss.get("comments", 0)),
                }
            )
            if len(bounties) >= limit:
                break
        return bounties

    def _run(
        self,
        action: str = "health",
        wallet_id: Optional[str] = None,
        limit: int = 10,
        **kwargs: Any,
    ) -> Any:
        """Dispatch a tool action (`balance`, `bounties`, `health`, `epoch`)."""
        act = (action or "health").strip().lower()
        if act in ("balance", "check_balance"):
            if not wallet_id:
                raise ValueError("wallet_id is required when action='balance'")
            return self.check_balance(wallet_id)
        if act in ("bounties", "list_bounties"):
            return self.list_bounties(limit=int(limit))
        if act in ("health", "get_node_health"):
            return self.get_node_health()
        if act in ("epoch", "get_current_epoch"):
            return self.get_current_epoch()
        raise ValueError(f"Unsupported RustChainTool action: {action!r}")


class RustChainBalanceTool(BaseTool):
    name: str = "rustchain_check_balance"
    description: str = "Check the RTC balance for a RustChain wallet address or miner ID."

    def __init__(self, client: Optional[RustChainTool] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._client = client or RustChainTool()

    def _run(self, wallet_id: str, **kwargs: Any) -> float:
        return self._client.check_balance(wallet_id)


class RustChainBountiesTool(BaseTool):
    name: str = "rustchain_list_bounties"
    description: str = "List open RustChain bounties from Scottcjn/rustchain-bounties."

    def __init__(self, client: Optional[RustChainTool] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._client = client or RustChainTool()

    def _run(self, limit: int = 10, **kwargs: Any) -> List[Dict[str, Any]]:
        return self._client.list_bounties(limit=int(limit))


class RustChainHealthTool(BaseTool):
    name: str = "rustchain_node_health"
    description: str = "Get live health status of the RustChain Mainnet node."

    def __init__(self, client: Optional[RustChainTool] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._client = client or RustChainTool()

    def _run(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._client.get_node_health()


class RustChainEpochTool(BaseTool):
    name: str = "rustchain_current_epoch"
    description: str = "Get current epoch, slot, and miner count from the RustChain Mainnet node."

    def __init__(self, client: Optional[RustChainTool] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._client = client or RustChainTool()

    def _run(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._client.get_current_epoch()


class RustChainToolkit:
    """Toolkit bundling all 4 RustChain tools for LangChain agents."""

    def __init__(self, node_url: str = "https://50.28.86.131") -> None:
        self.tool = RustChainTool(node_url=node_url)

    def get_tools(self) -> List[BaseTool]:
        return [
            RustChainBalanceTool(client=self.tool),
            RustChainBountiesTool(client=self.tool),
            RustChainHealthTool(client=self.tool),
            RustChainEpochTool(client=self.tool),
        ]
