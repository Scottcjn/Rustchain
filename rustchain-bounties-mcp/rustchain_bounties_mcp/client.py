"""
RustChain Bounties MCP — API Client

Async HTTP client that talks to the RustChain node Flask API.
All endpoints match the actual routes in rustchain_v2_integrated_v2.2.1_rip200.py.

Bounties are sourced from the GitHub Issues API (the node does not expose
a native /api/bounties endpoint).  See _fetch_bounties_from_github().
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any, Optional

import aiohttp

from .schemas import (
    APIError,
    AttestChallenge,
    AttestSubmitResult,
    BountyInfo,
    EpochInfo,
    HealthStatus,
    MinerInfo,
    WalletBalance,
    WalletVerifyResult,
)

logger = logging.getLogger(__name__)

# Defaults — node URL is configurable, defaulting to the live node
DEFAULT_NODE_URL = os.getenv("RUSTCHAIN_NODE_URL", "https://50.28.86.131")
REQUEST_TIMEOUT = int(os.getenv("RUSTCHAIN_TIMEOUT", "30"))
RETRY_COUNT = int(os.getenv("RUSTCHAIN_RETRY", "2"))

# GitHub bounties repo — used as the authoritative source for open bounties
# because the node does not expose a native /api/bounties endpoint.
GITHUB_BOUNTIES_OWNER = "Scottcjn"
GITHUB_BOUNTIES_REPO = "rustchain-bounties"
GITHUB_API_BASE = "https://api.github.com"


class RustChainClient:
    """Async client for the RustChain node API."""

    def __init__(
        self,
        node_url: Optional[str] = None,
        timeout: int = REQUEST_TIMEOUT,
        retry_count: int = RETRY_COUNT,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        self.node_url = (node_url or DEFAULT_NODE_URL).rstrip("/")
        self.timeout = timeout
        self.retry_count = retry_count
        self._session = session
        self._owns_session = session is None

    async def __aenter__(self) -> "RustChainClient":
        await self._ensure_session()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def _ensure_session(self) -> None:
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={"User-Agent": "RustChain-Bounties-MCP/0.1", "Accept": "application/json"},
            )
            self._owns_session = True

    async def close(self) -> None:
        if self._owns_session and self._session:
            await self._session.close()
            self._session = None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """HTTP request with retry and self-signed-cert handling."""
        await self._ensure_session()
        url = f"{self.node_url}{path}"
        last_err: Optional[Exception] = None

        for attempt in range(self.retry_count + 1):
            try:
                async with self._session.request(
                    method, url, params=params, json=json_data, ssl=False,
                ) as resp:
                    body = await resp.json()
                    if resp.status >= 400:
                        raise APIError.from_response(resp.status, body)
                    return body
            except aiohttp.ClientError as exc:
                last_err = exc
                logger.warning("Request failed (attempt %d): %s", attempt + 1, exc)
                if attempt < self.retry_count:
                    await asyncio.sleep(0.5 * (attempt + 1))
            except APIError:
                raise

        raise APIError(
            code="CONNECTION_FAILED",
            message=f"Failed after {self.retry_count + 1} attempts: {last_err}",
            status_code=503,
        )

    # ---- Tool implementations ----

    async def health(self) -> HealthStatus:
        """GET /health — node health probe."""
        data = await self._request("GET", "/health")
        return HealthStatus.from_dict(data)

    async def epoch(self) -> EpochInfo:
        """GET /epoch — current epoch info."""
        data = await self._request("GET", "/epoch")
        return EpochInfo.from_dict(data)

    async def balance(self, miner_id: str) -> WalletBalance:
        """GET /wallet/balance?miner_id=…"""
        if not miner_id or not miner_id.strip():
            raise APIError(code="VALIDATION_ERROR", message="miner_id is required", status_code=400)
        data = await self._request("GET", "/wallet/balance", params={"miner_id": miner_id.strip()})
        if data.get("ok") is False and "error" in data:
            raise APIError.from_response(400, data)
        return WalletBalance.from_dict(data)

    async def miners(
        self,
        limit: int = 50,
        hardware_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """GET /api/miners — returns paginated list with metadata."""
        params: dict[str, Any] = {"limit": min(max(limit, 1), 1000)}
        data = await self._request("GET", "/api/miners", params=params)
        miners_raw = data.get("miners", [])
        miners = [MinerInfo.from_dict(m) for m in miners_raw]

        if hardware_type:
            ht = hardware_type.lower()
            miners = [m for m in miners if ht in m.hardware_type.lower() or ht in m.device_family.lower()]

        return {
            "miners": miners,
            "total_count": data.get("total_count", len(miners)),
            "limit": data.get("limit", limit),
            "offset": data.get("offset", 0),
        }

    async def verify_wallet(self, miner_id: str) -> WalletVerifyResult:
        """Verify wallet presence for a miner_id.

        The node does not expose a dedicated wallet-creation endpoint.
        Wallets are implicitly provisioned on first activity (mining payout,
        transfer).  This method queries the balance endpoint to confirm
        whether the miner_id has a wallet row, and returns its status.

        Returns a WalletVerifyResult indicating whether the wallet exists
        and its current balance.  This is a *verification* tool, not a
        *creation* tool — the name reflects the actual capability.
        """
        try:
            bal = await self.balance(miner_id)
            return WalletVerifyResult(
                wallet_address=bal.miner_id,
                exists=True,
                balance_rtc=bal.amount_rtc,
                message=f"Wallet found for {miner_id} with balance {bal.amount_rtc} RTC",
            )
        except APIError as exc:
            if exc.status_code == 400:
                return WalletVerifyResult(
                    wallet_address=miner_id,
                    exists=False,
                    balance_rtc=0.0,
                    message=f"Could not verify wallet: {exc.message}",
                )
            raise

    async def submit_attestation(
        self,
        miner_id: str,
        device: dict[str, Any],
        signature: Optional[str] = None,
        public_key: Optional[str] = None,
    ) -> AttestSubmitResult:
        """POST /attest/submit — submit hardware fingerprint for enrollment.

        Flow: the caller should first GET a challenge via /attest/challenge,
        sign it, then call this method.  For MCP convenience we accept the
        device dict and optional signature/pubkey and forward to the node.
        """
        payload: dict[str, Any] = {
            "miner_id": miner_id,
            "device": device,
        }
        if signature:
            payload["signature"] = signature
        if public_key:
            payload["public_key"] = public_key

        data = await self._request("POST", "/attest/submit", json_data=payload)
        return AttestSubmitResult.from_dict(data)

    async def get_attest_challenge(self) -> AttestChallenge:
        """POST /attest/challenge — get nonce for attestation signing."""
        data = await self._request("POST", "/attest/challenge")
        return AttestChallenge.from_dict(data)

    async def bounties(
        self,
        status: str = "open",
        limit: int = 50,
    ) -> list[BountyInfo]:
        """List bounties from the GitHub Issues API.

        The node does not expose a native /api/bounties endpoint (it returns
        404).  The authoritative source for bounty data is the GitHub repo
        at Scottcjn/rustchain-bounties.  We fetch open issues from that repo
        and parse reward amounts from labels / title patterns.

        If the GitHub API also fails, returns an empty list with a log warning.
        """
        return await self._fetch_bounties_from_github(status=status, limit=limit)

    async def _fetch_bounties_from_github(
        self,
        status: str = "open",
        limit: int = 50,
    ) -> list[BountyInfo]:
        """Fetch bounties from GitHub Issues API.

        Parses issue titles and labels to extract bounty info.
        Expected label format: "bounty: <amount> RTC" or similar.
        """
        await self._ensure_session()
        state = status if status in ("open", "closed", "all") else "open"
        url = f"{GITHUB_API_BASE}/repos/{GITHUB_BOUNTIES_OWNER}/{GITHUB_BOUNTIES_REPO}/issues"
        params = {"state": state, "per_page": min(limit, 100)}
        headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "RustChain-Bounties-MCP/0.1"}

        try:
            async with self._session.get(url, params=params, headers=headers, ssl=False) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    logger.warning("GitHub API returned %d: %s", resp.status, body[:200])
                    return []

                issues = await resp.json()
                bounties: list[BountyInfo] = []
                for issue in issues[:limit]:
                    # Skip PRs (issues with pull_request key)
                    if "pull_request" in issue:
                        continue

                    bounty = self._parse_github_issue(issue)
                    if bounty is not None:
                        bounties.append(bounty)

                return bounties
        except aiohttp.ClientError as exc:
            logger.warning("Failed to fetch bounties from GitHub: %s", exc)
            return []

    @staticmethod
    def _parse_github_issue(issue: dict[str, Any]) -> Optional[BountyInfo]:
        """Parse a GitHub issue into a BountyInfo, or None if not a bounty."""
        title = issue.get("title", "")
        number = issue.get("number", 0)
        html_url = issue.get("html_url", "")
        state = issue.get("state", "open")
        labels = issue.get("labels", [])
        body = issue.get("body", "") or ""

        # Extract reward from labels (e.g. "bounty: 500 RTC", "500 RTC", "tier: major")
        reward_rtc = 0.0
        difficulty: Optional[str] = None
        tags: list[str] = []

        for label in labels:
            label_name = label.get("name", "").lower()
            # Look for bounty amount in labels
            for token in label_name.split():
                try:
                    val = float(token)
                    if 0 < val <= 10000:  # reasonable bounty range
                        reward_rtc = val
                except ValueError:
                    pass
            # Difficulty from labels
            if any(t in label_name for t in ("easy", "micro", "small")):
                difficulty = "easy"
            elif any(t in label_name for t in ("medium", "standard")):
                difficulty = "medium"
            elif any(t in label_name for t in ("hard", "major", "critical")):
                difficulty = "hard"
            tags.append(label.get("name", ""))

        # Try to extract reward from title (e.g. "Bounty: MCP Server (500 RTC)")
        title_match = re.search(r"(\d+)\s*RTC", title, re.IGNORECASE)
        if title_match and reward_rtc == 0:
            reward_rtc = float(title_match.group(1))

        # If no reward found in labels or title, skip non-bounty issues
        if reward_rtc == 0 and not any("bounty" in (lbl.get("name", "") or "").lower() for lbl in labels):
            # Still include it but with 0 reward — better than nothing for discovery
            pass

        return BountyInfo(
            issue_number=number,
            title=title,
            reward_rtc=reward_rtc,
            status=state,
            url=html_url,
            description=body[:500] if body else None,  # truncate for MCP output
            difficulty=difficulty,
            tags=tags,
        )
