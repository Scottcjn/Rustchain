"""
RustChain API client using the ``requests`` library.

Covers the public endpoints documented in ``RustChain_API.postman_collection.json``
and ``API_WALKTHROUGH.md``.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests


class RustChainError(Exception):
    """Base exception for all RustChain SDK errors."""


class APIError(RustChainError):
    """Raised when the node returns a non-2xx response."""

    def __init__(self, message: str, status_code: Optional[int] = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class RustChainClient:
    """Synchronous client for the RustChain node HTTP API.

    Parameters
    ----------
    base_url:
        Root URL of the RustChain node (default: mainnet node).
    verify_ssl:
        Whether to verify the server TLS certificate.  ``False`` by default
        because the mainnet node uses a self-signed certificate.
    timeout:
        Per-request timeout in seconds.
    retries:
        Number of automatic retries on transient failures.
    retry_delay:
        Base delay (seconds) between retries — multiplied by attempt number.
    admin_key:
        Optional ``X-Admin-Key`` header value for admin endpoints.

    Example
    -------
    >>> from rustchain import RustChainClient
    >>> client = RustChainClient()
    >>> client.get_health()
    {'ok': True, 'version': '2.2.1-rip200', ...}
    """

    DEFAULT_BASE_URL = "https://50.28.86.131"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        verify_ssl: bool = False,
        timeout: int = 30,
        retries: int = 3,
        retry_delay: float = 1.0,
        admin_key: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.retries = retries
        self.retry_delay = retry_delay

        self.session = requests.Session()
        self.session.verify = self.verify_ssl
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        if admin_key:
            self.session.headers["X-Admin-Key"] = admin_key

        # Suppress InsecureRequestWarning when verify_ssl is off
        if not verify_ssl:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Execute an HTTP request with retry logic.

        Returns the decoded JSON body on success or raises :class:`APIError`.
        """
        url = self._url(path)
        last_exc: Optional[Exception] = None

        for attempt in range(1, self.retries + 1):
            try:
                resp = self.session.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    timeout=self.timeout,
                )
                if resp.ok:
                    return resp.json()
                raise APIError(
                    f"HTTP {resp.status_code}: {resp.text[:300]}",
                    status_code=resp.status_code,
                    body=resp.text,
                )
            except APIError:
                raise
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.retries:
                    time.sleep(self.retry_delay * attempt)

        raise APIError(f"Request failed after {self.retries} retries: {last_exc}")

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return self._request("GET", path, params=params)

    def _post(self, path: str, json: Optional[Dict[str, Any]] = None) -> Any:
        return self._request("POST", path, json=json)

    # ------------------------------------------------------------------
    # Health & Status
    # ------------------------------------------------------------------

    def get_health(self) -> Dict[str, Any]:
        """Node health check.

        Returns dict with ``ok``, ``version``, ``uptime_s``, ``db_rw``, etc.
        """
        return self._get("/health")

    def get_ready(self) -> Dict[str, Any]:
        """Readiness probe (DB reachable, migrations applied)."""
        return self._get("/ready")

    def get_stats(self) -> Dict[str, Any]:
        """General network statistics (``/api/stats``)."""
        return self._get("/api/stats")

    def get_metrics(self) -> Any:
        """Prometheus-style metrics."""
        return self._get("/metrics")

    # ------------------------------------------------------------------
    # Epoch & Lottery
    # ------------------------------------------------------------------

    def get_epoch(self) -> Dict[str, Any]:
        """Current epoch, slot, height, and reward-pot info."""
        return self._get("/epoch")

    def enroll_epoch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Enroll a miner in the current epoch."""
        return self._post("/epoch/enroll", json=payload)

    def get_eligibility(self, miner_id: str) -> Dict[str, Any]:
        """Check lottery eligibility for *miner_id*."""
        return self._get("/lottery/eligibility", params={"miner_id": miner_id})

    # ------------------------------------------------------------------
    # Chain / Headers
    # ------------------------------------------------------------------

    def get_chain_tip(self) -> Dict[str, Any]:
        """Return the latest header / chain tip (``/headers/tip``)."""
        return self._get("/headers/tip")

    def get_bounty_multiplier(self) -> Dict[str, Any]:
        """Deflationary bounty-decay multiplier (RIP-0200b)."""
        return self._get("/api/bounty-multiplier")

    # ------------------------------------------------------------------
    # Miners & Network
    # ------------------------------------------------------------------

    def get_miners(self) -> List[Dict[str, Any]]:
        """List all active miners."""
        return self._get("/api/miners")

    def get_nodes(self) -> List[Dict[str, Any]]:
        """List connected peer nodes."""
        return self._get("/api/nodes")

    def get_miner_badge(self, miner_id: str) -> Dict[str, Any]:
        """Badge metadata for a specific miner."""
        return self._get(f"/api/badge/{miner_id}")

    def get_miner_dashboard(self, miner_id: str) -> Dict[str, Any]:
        """Full dashboard data for a miner."""
        return self._get(f"/api/miner_dashboard/{miner_id}")

    def get_miner_attestations(
        self, miner_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Recent attestation records for a miner."""
        return self._get(
            f"/api/miner/{miner_id}/attestations",
            params={"limit": limit},
        )

    # ------------------------------------------------------------------
    # Wallet / Balance
    # ------------------------------------------------------------------

    def get_balance(self, miner_id: str) -> Dict[str, Any]:
        """Wallet balance for *miner_id*.

        Returns dict with ``amount_rtc``, ``amount_i64``, ``miner_id``.
        """
        return self._get("/wallet/balance", params={"miner_id": miner_id})

    def get_balance_by_pk(self, public_key: str) -> Dict[str, Any]:
        """Balance lookup by public-key address."""
        return self._get(f"/balance/{public_key}")

    def get_all_balances(self) -> Any:
        """Return every wallet balance (``/wallet/balances/all``)."""
        return self._get("/wallet/balances/all")

    def get_wallet_history(
        self, miner_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Transaction history for a wallet."""
        return self._get(
            "/wallet/history", params={"miner_id": miner_id, "limit": limit}
        )

    def get_wallet_ledger(self, miner_id: str) -> Dict[str, Any]:
        """Detailed ledger entries for a wallet."""
        return self._get("/wallet/ledger", params={"miner_id": miner_id})

    def resolve_wallet(self, address: str) -> Dict[str, Any]:
        """Resolve a BCN / alias address to a wallet ID."""
        return self._get("/wallet/resolve", params={"address": address})

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    def submit_transaction(
        self,
        from_wallet: str,
        to_wallet: str,
        amount: int,
        fee: float,
        signature: str,
        timestamp: int,
    ) -> Dict[str, Any]:
        """Submit a signed transfer (``POST /wallet/transfer/signed``).

        Parameters
        ----------
        from_wallet:
            Sender RustChain wallet ID.
        to_wallet:
            Recipient wallet ID.
        amount:
            Amount in smallest units (1 RTC = 1 000 000).
        fee:
            Transaction fee.
        signature:
            Hex-encoded Ed25519 signature of the transfer payload.
        timestamp:
            Unix timestamp for replay protection.
        """
        payload = {
            "from": from_wallet,
            "to": to_wallet,
            "amount": amount,
            "fee": fee,
            "signature": signature,
            "timestamp": timestamp,
        }
        return self._post("/wallet/transfer/signed", json=payload)

    # ------------------------------------------------------------------
    # Attestation
    # ------------------------------------------------------------------

    def get_attest_challenge(self) -> Dict[str, Any]:
        """Request an attestation challenge."""
        return self._post("/attest/challenge", json={})

    def submit_attestation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a signed attestation."""
        return self._post("/attest/submit", json=payload)

    # ------------------------------------------------------------------
    # Fee Pool (RIP-0301)
    # ------------------------------------------------------------------

    def get_fee_pool(self) -> Dict[str, Any]:
        """Current fee-pool balance and stats."""
        return self._get("/api/fee_pool")

    # ------------------------------------------------------------------
    # Rewards
    # ------------------------------------------------------------------

    def get_epoch_rewards(self, epoch: int) -> Dict[str, Any]:
        """Rewards breakdown for a specific epoch."""
        return self._get(f"/rewards/epoch/{epoch}")

    def settle_rewards(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Settle outstanding epoch rewards (admin)."""
        return self._post("/rewards/settle", json=payload)

    # ------------------------------------------------------------------
    # Pending / 2-Phase Commit
    # ------------------------------------------------------------------

    def list_pending(
        self, status: str = "pending", limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List pending 2-phase commit operations."""
        return self._get("/pending/list", params={"status": status, "limit": limit})

    def confirm_pending(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Confirm a pending operation."""
        return self._post("/pending/confirm", json=payload)

    def void_pending(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Void / cancel a pending operation."""
        return self._post("/pending/void", json=payload)

    # ------------------------------------------------------------------
    # Withdrawals (RIP-0008)
    # ------------------------------------------------------------------

    def register_withdrawal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new withdrawal request."""
        return self._post("/withdraw/register", json=payload)

    def request_withdrawal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a registered withdrawal."""
        return self._post("/withdraw/request", json=payload)

    def get_withdrawal_status(self, withdrawal_id: str) -> Dict[str, Any]:
        """Check status of a specific withdrawal."""
        return self._get(f"/withdraw/status/{withdrawal_id}")

    def get_withdrawal_history(
        self, public_key: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Withdrawal history for a wallet (by public key)."""
        return self._get(
            f"/withdraw/history/{public_key}", params={"limit": limit}
        )

    # ------------------------------------------------------------------
    # Governance (RIP-0142)
    # ------------------------------------------------------------------

    def create_proposal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a governance proposal."""
        return self._post("/governance/propose", json=payload)

    def list_proposals(self) -> List[Dict[str, Any]]:
        """List all governance proposals."""
        return self._get("/governance/proposals")

    def get_proposal(self, proposal_id: int) -> Dict[str, Any]:
        """Fetch a single proposal by ID."""
        return self._get(f"/governance/proposal/{proposal_id}")

    def vote(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Cast a governance vote."""
        return self._post("/governance/vote", json=payload)

    # ------------------------------------------------------------------
    # P2P
    # ------------------------------------------------------------------

    def get_p2p_stats(self) -> Dict[str, Any]:
        """Peer-to-peer network statistics."""
        return self._get("/p2p/stats")

    def p2p_ping(self) -> Dict[str, Any]:
        """Ping the node's P2P layer."""
        return self._get("/p2p/ping")

    def get_p2p_blocks(self, start: int = 0, limit: int = 100) -> Any:
        """Fetch blocks from the P2P layer."""
        return self._get("/p2p/blocks", params={"start": start, "limit": limit})

    # ------------------------------------------------------------------
    # Beacon Protocol
    # ------------------------------------------------------------------

    def submit_beacon(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a beacon envelope."""
        return self._post("/beacon/submit", json=payload)

    def get_beacon_digest(self) -> Dict[str, Any]:
        """Latest beacon digest."""
        return self._get("/beacon/digest")

    def get_beacon_envelopes(
        self, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List beacon envelopes."""
        return self._get(
            "/beacon/envelopes", params={"limit": limit, "offset": offset}
        )

    # ------------------------------------------------------------------
    # Genesis
    # ------------------------------------------------------------------

    def export_genesis(self) -> Dict[str, Any]:
        """Export genesis snapshot."""
        return self._get("/genesis/export")

    # ------------------------------------------------------------------
    # Mining (compat)
    # ------------------------------------------------------------------

    def mine(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a mining payload (``POST /api/mine``)."""
        return self._post("/api/mine", json=payload)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self.session.close()

    def __enter__(self) -> "RustChainClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"RustChainClient(base_url={self.base_url!r})"
