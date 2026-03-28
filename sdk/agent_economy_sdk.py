"""
agent_economy_sdk.py — Python SDK for the RustChain Agent Economy (RIP-302)

Provides the AgentEconomyClient class for interacting with the Agent Economy
marketplace: posting jobs, claiming, delivering, and resolving disputes.
"""

import requests
from typing import Optional, Dict, Any, List


class AgentEconomyError(Exception):
    """Raised when the Agent Economy API returns an error."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"[HTTP {status_code}] {message}")


class AgentEconomyClient:
    """
    Client for the RustChain Agent Economy marketplace (RIP-302).

    Args:
        base_url: Base URL of the RustChain node (default: https://50.28.86.131)
        timeout:  Request timeout in seconds (default: 15)
        verify_ssl: Verify SSL certificates (default: False for self-signed nodes)
    """

    DEFAULT_BASE_URL = "https://50.28.86.131"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 15,
        verify_ssl: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.verify = verify_ssl

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        resp = self.session.get(
            self._url(path), params=params, timeout=self.timeout
        )
        return self._handle(resp)

    def _post(self, path: str, payload: Dict) -> Any:
        resp = self.session.post(
            self._url(path), json=payload, timeout=self.timeout
        )
        return self._handle(resp)

    @staticmethod
    def _handle(resp: requests.Response) -> Any:
        try:
            data = resp.json()
        except ValueError:
            data = resp.text
        if not resp.ok:
            msg = data.get("error", str(data)) if isinstance(data, dict) else str(data)
            raise AgentEconomyError(resp.status_code, msg)
        return data

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_jobs(self, status: Optional[str] = None) -> List[Dict]:
        """
        Browse open jobs on the marketplace.

        Args:
            status: Optional filter e.g. 'open', 'claimed', 'delivered'

        Returns:
            List of job objects.
        """
        params = {"status": status} if status else None
        return self._get("/agent/jobs", params=params)

    def get_job(self, job_id: str) -> Dict:
        """
        Fetch details for a specific job.

        Args:
            job_id: The job identifier.

        Returns:
            Job detail dict.
        """
        return self._get(f"/agent/jobs/{job_id}")

    def post_job(
        self,
        title: str,
        description: str,
        reward_rtc: float,
        wallet: str,
    ) -> Dict:
        """
        Post a new job to the marketplace (locks RTC escrow).

        Args:
            title:       Short job title.
            description: Detailed job description.
            reward_rtc:  Reward in RTC (locked in escrow).
            wallet:      Poster's RTC wallet address.

        Returns:
            Created job object.
        """
        return self._post(
            "/agent/jobs",
            {
                "title": title,
                "description": description,
                "reward_rtc": reward_rtc,
                "wallet": wallet,
            },
        )

    def claim_job(self, job_id: str, wallet: str) -> Dict:
        """
        Claim an open job.

        Args:
            job_id: Job to claim.
            wallet: Claimer's RTC wallet address.

        Returns:
            Updated job object.
        """
        return self._post(f"/agent/jobs/{job_id}/claim", {"wallet": wallet})

    def deliver(self, job_id: str, deliverable_url: str, wallet: str) -> Dict:
        """
        Submit a deliverable for a claimed job.

        Args:
            job_id:           Job being delivered.
            deliverable_url:  URL pointing to the deliverable (PR, IPFS, etc.).
            wallet:           Deliverer's RTC wallet address.

        Returns:
            Updated job object.
        """
        return self._post(
            f"/agent/jobs/{job_id}/deliver",
            {"deliverable_url": deliverable_url, "wallet": wallet},
        )

    def accept(self, job_id: str, wallet: str) -> Dict:
        """
        Accept a delivery and release escrow to the deliverer.

        Args:
            job_id: Job to accept.
            wallet: Job poster's RTC wallet (must match original poster).

        Returns:
            Updated job object with escrow release info.
        """
        return self._post(f"/agent/jobs/{job_id}/accept", {"wallet": wallet})

    def dispute(self, job_id: str, reason: str, wallet: str) -> Dict:
        """
        Dispute / reject a delivery.

        Args:
            job_id:  Job under dispute.
            reason:  Human-readable reason for the dispute.
            wallet:  Disputer's RTC wallet address.

        Returns:
            Dispute record.
        """
        return self._post(
            f"/agent/jobs/{job_id}/dispute",
            {"reason": reason, "wallet": wallet},
        )

    def get_reputation(self, wallet: str) -> Dict:
        """
        Retrieve the trust / reputation score for a wallet.

        Args:
            wallet: RTC wallet address.

        Returns:
            Reputation object containing score and history.
        """
        return self._get(f"/agent/reputation/{wallet}")

    def get_stats(self) -> Dict:
        """
        Fetch marketplace-wide statistics.

        Returns:
            Stats object (total jobs, volume, active agents, etc.).
        """
        return self._get("/agent/stats")
