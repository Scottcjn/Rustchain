"""
RustChain Client

Main client for interacting with RustChain node API.
"""

from typing import Dict, List, Optional, Any
import requests
import json
from rustchain.exceptions import (
    RustChainError,
    ConnectionError,
    ValidationError,
    APIError,
    AttestationError,
    TransferError,
)


class RustChainClient:
    """
    Client for interacting with RustChain node API.

    Args:
        base_url: Base URL of RustChain node (e.g., "https://50.28.86.131")
        verify_ssl: Whether to verify SSL certificates (default: True)
        timeout: Request timeout in seconds (default: 30)
    """

    def __init__(
        self,
        base_url: str,
        verify_ssl: bool = True,
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.verify_ssl = verify_ssl
        self.timeout = timeout

        # Initialize session for connection pooling
        self.session = requests.Session()
        self.session.verify = verify_ssl

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Dict = None,
        data: Dict = None,
        json_payload: Dict = None,
    ) -> Dict:
        """
        Make HTTP request to RustChain node.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: URL query parameters
            data: Form data
            json_payload: JSON payload

        Returns:
            Response JSON as dict

        Raises:
            ConnectionError: If request fails
            APIError: If API returns error
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = {"Content-Type": "application/json"}

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                data=data,
                json=json_payload,
                headers=headers,
                timeout=self.timeout,
            )

            # Check for HTTP errors
            try:
                response.raise_for_status()
            except requests.HTTPError as e:
                raise APIError(
                    f"HTTP {response.status_code}: {e}",
                    status_code=response.status_code,
                ) from e

            # Parse JSON response
            try:
                return response.json()
            except json.JSONDecodeError as e:
                return {"raw_response": response.text}

        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"Failed to connect to {url}: {e}") from e
        except requests.exceptions.Timeout as e:
            raise ConnectionError(f"Request timeout to {url}: {e}") from e
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Request failed: {e}") from e

    def health(self) -> Dict[str, Any]:
        """
        Get node health status.

        Returns:
            Dict with health information:
                - ok (bool): Node is healthy
                - uptime_s (int): Uptime in seconds
                - version (str): Node version
                - db_rw (bool): Database read/write status

        Raises:
            ConnectionError: If connection fails
            APIError: If API returns error

        Example:
            >>> client = RustChainClient("https://50.28.86.131")
            >>> health = client.health()
            >>> print(health["version"])
            '2.2.1-rip200'
        """
        return self._request("GET", "/health")

    def epoch(self) -> Dict[str, Any]:
        """
        Get current epoch information.

        Returns:
            Dict with epoch information:
                - epoch (int): Current epoch number
                - slot (int): Current slot
                - blocks_per_epoch (int): Blocks per epoch
                - enrolled_miners (int): Number of enrolled miners
                - epoch_pot (float): Current epoch PoT

        Raises:
            ConnectionError: If connection fails
            APIError: If API returns error

        Example:
            >>> client = RustChainClient("https://50.28.86.131")
            >>> epoch = client.epoch()
            >>> print(f"Current epoch: {epoch['epoch']}")
        """
        return self._request("GET", "/epoch")

    def miners(self) -> List[Dict[str, Any]]:
        """
        Get list of all miners.

        Returns:
            List of miner dicts with:
                - miner (str): Miner wallet address
                - antiquity_multiplier (float): Hardware antiquity multiplier
                - hardware_type (str): Hardware type description
                - device_arch (str): Device architecture
                - last_attest (int): Last attestation timestamp

        Raises:
            ConnectionError: If connection fails
            APIError: If API returns error

        Example:
            >>> client = RustChainClient("https://50.28.86.131")
            >>> miners = client.miners()
            >>> print(f"Total miners: {len(miners)}")
        """
        result = self._request("GET", "/api/miners")
        return result if isinstance(result, list) else []

    def balance(self, miner_id: str) -> Dict[str, Any]:
        """
        Get wallet balance for a miner.

        Args:
            miner_id: Miner wallet address

        Returns:
            Dict with balance information:
                - miner_pk (str): Wallet address
                - balance (float): Current balance in RTC
                - epoch_rewards (float): Rewards in current epoch
                - total_earned (float): Total RTC earned

        Raises:
            ConnectionError: If connection fails
            APIError: If API returns error
            ValidationError: If miner_id is invalid

        Example:
            >>> client = RustChainClient("https://50.28.86.131")
            >>> balance = client.balance("wallet_address")
            >>> print(f"Balance: {balance['balance']} RTC")
        """
        if not miner_id or not isinstance(miner_id, str):
            raise ValidationError("miner_id must be a non-empty string")

        return self._request("GET", "/balance", params={"miner_id": miner_id})

    def transfer(
        self,
        from_addr: str,
        to_addr: str,
        amount: float,
        signature: str = None,
        fee: float = 0.01,
    ) -> Dict[str, Any]:
        """
        Transfer RTC from one wallet to another.

        Args:
            from_addr: Source wallet address
            to_addr: Destination wallet address
            amount: Amount to transfer (in RTC)
            signature: Transaction signature (if signed offline)
            fee: Transfer fee (default: 0.01 RTC)

        Returns:
            Dict with transfer result:
                - success (bool): Transfer succeeded
                - tx_id (str): Transaction ID
                - fee (float): Fee deducted
                - new_balance (float): New balance after transfer

        Raises:
            ConnectionError: If connection fails
            APIError: If API returns error
            ValidationError: If parameters are invalid
            TransferError: If transfer fails

        Example:
            >>> client = RustChainClient("https://50.28.86.131")
            >>> result = client.transfer(
            ...     from_addr="wallet1",
            ...     to_addr="wallet2",
            ...     amount=10.0
            ... )
            >>> print(f"TX ID: {result['tx_id']}")
        """
        # Validate parameters
        if not from_addr or not isinstance(from_addr, str):
            raise ValidationError("from_addr must be a non-empty string")
        if not to_addr or not isinstance(to_addr, str):
            raise ValidationError("to_addr must be a non-empty string")
        if amount <= 0:
            raise ValidationError("amount must be positive")

        payload = {
            "from": from_addr,
            "to": to_addr,
            "amount": amount,
            "fee": fee,
        }

        if signature:
            payload["signature"] = signature

        try:
            result = self._request("POST", "/wallet/transfer/signed", json_payload=payload)

            if not result.get("success", False):
                error_msg = result.get("error", "Transfer failed")
                raise TransferError(f"Transfer failed: {error_msg}")

            return result

        except APIError as e:
            raise TransferError(f"Transfer failed: {e}") from e

    def transfer_history(self, miner_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get transfer history for a wallet.

        Args:
            miner_id: Wallet address
            limit: Maximum number of records to return (default: 50)

        Returns:
            List of transfer dicts with:
                - tx_id (str): Transaction ID
                - from_addr (str): Source address
                - to_addr (str): Destination address
                - amount (float): Amount transferred
                - timestamp (int): Unix timestamp
                - status (str): Transaction status

        Raises:
            ConnectionError: If connection fails
            APIError: If API returns error
            ValidationError: If miner_id is invalid

        Example:
            >>> client = RustChainClient("https://50.28.86.131")
            >>> history = client.transfer_history("wallet_address", limit=10)
            >>> for tx in history:
            ...     print(f"{tx['tx_id']}: {tx['amount']} RTC")
        """
        if not miner_id or not isinstance(miner_id, str):
            raise ValidationError("miner_id must be a non-empty string")

        result = self._request(
            "GET",
            "/wallet/history",
            params={"miner_id": miner_id, "limit": limit},
        )
        return result if isinstance(result, list) else []

    def submit_attestation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit hardware attestation to the node.

        Args:
            payload: Attestation payload containing:
                - miner_id (str): Miner wallet address
                - device (dict): Device information
                - fingerprint (dict): Fingerprint check results
                - nonce (str): Unique nonce for replay protection

        Returns:
            Dict with attestation result:
                - success (bool): Attestation accepted
                - epoch (int): Epoch number
                - slot (int): Slot number
                - multiplier (float): Applied antiquity multiplier

        Raises:
            ConnectionError: If connection fails
            APIError: If API returns error
            ValidationError: If payload is invalid
            AttestationError: If attestation fails

        Example:
            >>> client = RustChainClient("https://50.28.86.131")
            >>> attestation = {
            ...     "miner_id": "wallet_address",
            ...     "device": {"arch": "G4", "cores": 1},
            ...     "fingerprint": {"checks": {...}},
            ...     "nonce": "unique_nonce"
            ... }
            >>> result = client.submit_attestation(attestation)
            >>> print(f"Multiplier: {result['multiplier']}x")
        """
        if not payload or not isinstance(payload, dict):
            raise ValidationError("payload must be a non-empty dict")

        # Validate required fields
        required_fields = ["miner_id", "device", "fingerprint"]
        for field in required_fields:
            if field not in payload:
                raise ValidationError(f"Missing required field: {field}")

        try:
            result = self._request("POST", "/attest/submit", json_payload=payload)

            if not result.get("success", False):
                error_msg = result.get("error", "Attestation failed")
                raise AttestationError(f"Attestation failed: {error_msg}")

            return result

        except APIError as e:
            raise AttestationError(f"Attestation failed: {e}") from e

    def enroll_miner(self, miner_id: str) -> Dict[str, Any]:
        """
        Enroll a new miner in the network.

        Args:
            miner_id: Wallet address to enroll

        Returns:
            Dict with enrollment result:
                - success (bool): Enrollment succeeded
                - miner_id (str): Enrolled wallet address
                - enrolled_at (int): Unix timestamp

        Raises:
            ConnectionError: If connection fails
            APIError: If API returns error
            ValidationError: If miner_id is invalid

        Example:
            >>> client = RustChainClient("https://50.28.86.131")
            >>> result = client.enroll_miner("wallet_address")
            >>> if result["success"]:
            ...     print("Enrolled successfully!")
        """
        if not miner_id or not isinstance(miner_id, str):
            raise ValidationError("miner_id must be a non-empty string")

        try:
            result = self._request("POST", "/enroll", json_payload={"miner_id": miner_id})
            return result

        except APIError as e:
            raise RustChainError(f"Enrollment failed: {e}") from e

    def close(self):
        """Close the HTTP session"""
        self.session.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
