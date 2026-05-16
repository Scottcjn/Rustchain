"""
RustChain Async HTTP Client
Provides async access to the RustChain network RPC API.
"""

import httpx
import json
from typing import Dict, List, Any, Optional

from .exceptions import (
    RustChainError,
    ConnectionError as RCConnectionError,
    APIError,
    ValidationError,
)


class RustChainClient:
    """
    Async HTTP client for the RustChain blockchain network.

    Args:
        base_url: Base URL of the RustChain node RPC endpoint.
                   Defaults to "https://50.28.86.131".
        timeout: Request timeout in seconds. Defaults to 30.

    Example:
        import asyncio
        from rustchain_sdk import RustChainClient

        async def main():
            client = RustChainClient()
            health = await client.health()
            print(health)
            balance = await client.get_balance("RTC...")
            print(balance)

        asyncio.run(main())
    """

    def __init__(
        self,
        base_url: str = "https://50.28.86.131",
        timeout: float = 30.0,
        verify: Optional[bool] = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        # Use pinned cert if available, else system CA bundle
        import os
        if verify is not None:
            self._tls_verify = verify
        else:
            cert = os.path.expanduser("~/.rustchain/node_cert.pem")
            if os.path.exists(cert):
                self._tls_verify = cert
            else:
                import logging
                logging.warning("RustChain node cert not found at ~/.rustchain/node_cert.pem. Falling back to system CA (SSL verification may fail for self-signed nodes). Set verify=False or use R_CA_CERT= to override.")
                self._tls_verify = True

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazily create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                verify=self._tls_verify,
            )
        return self._client

    async def _post(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Internal POST helper.

        Args:
            path: API endpoint path (e.g. "/health").
            params: Optional query parameters.
            json_data: Optional JSON body.

        Returns:
            Parsed JSON response.

        Raises:
            RCConnectionError: On connection failure.
            APIError: On API-level errors.
        """
        try:
            client = await self._get_client()
            response = await client.post(
                path,
                params=params,
                json=json_data,
            )
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError as e:
            raise RCConnectionError(f"Failed to connect to {self._base_url}: {e}")
        except httpx.HTTPStatusError as e:
            try:
                error_body = e.response.json()
                message = error_body.get("message", str(e))
            except Exception:
                message = str(e)
            raise APIError(
                f"API error {e.response.status_code}: {message}",
                status_code=e.response.status_code,
            )
        except Exception as e:
            raise RustChainError(f"Unexpected error: {e}")

    async def _get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Internal GET helper.

        Args:
            path: API endpoint path.
            params: Optional query parameters.

        Returns:
            Parsed JSON response.

        Raises:
            RCConnectionError: On connection failure.
            APIError: On API-level errors.
        """
        try:
            client = await self._get_client()
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError as e:
            raise RCConnectionError(f"Failed to connect to {self._base_url}: {e}")
        except httpx.HTTPStatusError as e:
            try:
                error_body = e.response.json()
                message = error_body.get("message", str(e))
            except Exception:
                message = str(e)
            raise APIError(
                f"API error {e.response.status_code}: {message}",
                status_code=e.response.status_code,
            )
        except Exception as e:
            raise RustChainError(f"Unexpected error: {e}")

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "RustChainClient":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    # ─────────────────────────────────────────────────────────────────
    # Health & Network
    # ─────────────────────────────────────────────────────────────────

    async def health(self) -> Dict[str, Any]:
        """
        Check node health status.

        Returns:
            Health status dict with node info.
        """
        return await self._get("/health")

    async def get_epoch(self) -> Dict[str, Any]:
        """
        Get current epoch information.

        Returns:
            Dict with epoch number, start_time, end_time, etc.
        """
        return await self._get("/epoch")

    async def get_headers_tip(self) -> Dict[str, Any]:
        """
        Get the current headers tip (chain head).

        Returns:
            Dict with header height, hash, timestamp, etc.
        """
        return await self._get("/headers/tip")

    # ─────────────────────────────────────────────────────────────────
    # Miners & Attestation
    # ─────────────────────────────────────────────────────────────────

    async def get_miners(self) -> List[Dict[str, Any]]:
        """
        Get list of active miners.

        Returns:
            List of miner info dicts.
        """
        result = await self._get("/miners")
        if isinstance(result, list):
            return result
        return result.get("miners", [])

    async def get_attestation_status(self, miner_public_key: str) -> Dict[str, Any]:
        """
        Get attestation status for a miner.

        Args:
            miner_public_key: The miner's public key.

        Returns:
            Attestation status dict.
        """
        return await self._get(
            "/attestation/status",
            params={"miner_public_key": miner_public_key},
        )

    async def attest_challenge(self, miner_public_key: str) -> Dict[str, Any]:
        """
        Request an attestation challenge for a miner.

        Args:
            miner_public_key: The miner's public key.

        Returns:
            Challenge dict with challenge string and expiry.
        """
        return await self._post(
            "/attestation/challenge",
            json_data={"miner_public_key": miner_public_key},
        )

    async def attest_submit(
        self,
        miner_public_key: str,
        challenge_response: str,
        signature: str,
    ) -> Dict[str, Any]:
        """
        Submit an attestation response.

        Args:
            miner_public_key: The miner's public key.
            challenge_response: The challenge response string.
            signature: Ed25519 signature over the challenge.

        Returns:
            Submission result dict.
        """
        return await self._post(
            "/attestation/submit",
            json_data={
                "miner_public_key": miner_public_key,
                "challenge_response": challenge_response,
                "signature": signature,
            },
        )

    async def get_bounty_multiplier(self) -> Dict[str, Any]:
        """
        Get the current bounty multiplier for attestation.

        Returns:
            Bounty multiplier info.
        """
        return await self._get("/attestation/bounty_multiplier")

    # ─────────────────────────────────────────────────────────────────
    # Wallet & Balances
    # ─────────────────────────────────────────────────────────────────

    async def get_balance(self, wallet_address: str) -> Dict[str, Any]:
        """
        Get balance for a wallet address.

        Args:
            wallet_address: The RTC wallet address.

        Returns:
            Dict with balance, nonce, etc.
        """
        return await self._get(
            "/wallet/balance",
            params={"address": wallet_address},
        )

    async def get_wallet_balance(self, miner_id: str) -> Dict[str, Any]:
        """
        Get wallet balance by miner ID.

        Args:
            miner_id: The miner identifier.

        Returns:
            Dict with wallet balance info.
        """
        return await self._get(
            "/wallet/balance",
            params={"miner_id": miner_id},
        )

    async def get_wallet_history(
        self,
        wallet_address: str,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Get transaction history for a wallet.

        Args:
            wallet_address: The wallet address.
            limit: Max number of transactions to return.

        Returns:
            Dict with transactions list and metadata.
        """
        return await self._get(
            "/wallet/history",
            params={"address": wallet_address, "limit": limit},
        )

    async def wallet_transfer_with_wallet(
        self,
        wallet,
        to_address: str,
        amount: float,
        fee: float = 0,
    ) -> Dict[str, Any]:
        """
        Build and submit a signed transfer using a RustChainWallet.

        Args:
            wallet: A RustChainWallet instance.
            to_address: Recipient wallet address.
            amount: Amount to transfer in RTC.
            fee: Transaction fee in RTC.

        Returns:
            Transaction result dict.
        """
        transfer = wallet.sign_transfer(to_address, amount, fee)
        return await self.transfer_signed(
            from_address=transfer["from_address"],
            to_address=transfer["to_address"],
            amount=transfer["amount_rtc"],
            fee=transfer["fee_rtc"],
            signature=transfer["signature"],
            timestamp=transfer["nonce"],
            public_key=transfer["public_key"],
            memo=transfer.get("memo", ""),
            chain_id=transfer.get("chain_id"),
        )

    # ─────────────────────────────────────────────────────────────────
    # Transfers
    # ─────────────────────────────────────────────────────────────────

    async def transfer_signed(
        self,
        from_address: str,
        to_address: str,
        amount: float,
        fee: float,
        signature: str,
        timestamp: int,
        public_key: str = "",
        memo: str = "",
        chain_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Submit a signed transfer transaction.

        Args:
            from_address: Sender wallet address.
            to_address: Recipient wallet address.
            amount: Amount in RTC.
            fee: Transaction fee in RTC.
            signature: Hex-encoded Ed25519 signature.
            timestamp: Unique transfer nonce.
            public_key: Sender public key matching from_address.
            memo: Optional transfer memo.
            chain_id: Optional chain/network id.

        Returns:
            Transaction result dict with tx_hash, status, etc.
        """
        payload = {
            "from_address": from_address,
            "to_address": to_address,
            "amount_rtc": amount,
            "fee_rtc": fee,
            "nonce": timestamp,
            "signature": signature,
            "public_key": public_key,
        }
        if memo:
            payload["memo"] = memo
        if chain_id:
            payload["chain_id"] = chain_id

        return await self._post("/wallet/transfer/signed", json_data=payload)

    # ─────────────────────────────────────────────────────────────────
    # Beacon
    # ─────────────────────────────────────────────────────────────────

    async def beacon_submit(self, envelope: Dict) -> Dict[str, Any]:
        """
        Submit a beacon envelope.

        Args:
            envelope: Beacon envelope dict.

        Returns:
            Submission result.
        """
        return await self._post("/beacon/submit", json_data={"envelope": envelope})

    # ─────────────────────────────────────────────────────────────────
    # Governance
    # ─────────────────────────────────────────────────────────────────

    async def governance_propose(
        self,
        proposer: str,
        proposal_type: str,
        description: str,
        payload: Dict,
    ) -> Dict[str, Any]:
        """
        Submit a governance proposal.

        Args:
            proposer: Proposer's wallet address.
            proposal_type: Type of proposal (e.g. "param_change", "treasury").
            description: Human-readable description.
            payload: Proposal-specific payload dict.

        Returns:
            Proposal result with proposal_id.
        """
        return await self._post(
            "/governance/propose",
            json_data={
                "proposer": proposer,
                "proposal_type": proposal_type,
                "description": description,
                "payload": payload,
            },
        )

    async def governance_vote(
        self,
        voter: str,
        proposal_id: int,
        vote: str,
        signature: str,
    ) -> Dict[str, Any]:
        """
        Cast a vote on a governance proposal.

        Args:
            voter: Voter's wallet address.
            proposal_id: ID of the proposal.
            vote: Vote choice ("yes", "no", or "abstain").
            signature: Ed25519 signature over the vote.

        Returns:
            Vote submission result.
        """
        return await self._post(
            "/governance/vote",
            json_data={
                "voter": voter,
                "proposal_id": proposal_id,
                "vote": vote,
                "signature": signature,
            },
        )

    async def list_governance_proposals(self, status: str = None) -> List[Dict[str, Any]]:
        """
        List governance proposals.

        Args:
            status: Optional filter: "active", "passed", "rejected", "executed".

        Returns:
            List of proposal dicts.
        """
        params = {}
        if status:
            params["status"] = status
        result = await self._get("/governance/proposals", params=params)
        if isinstance(result, list):
            return result
        return result.get("proposals", [])

    # ─────────────────────────────────────────────────────────────────
    # Explorer
    # ─────────────────────────────────────────────────────────────────

    async def explorer_blocks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent blocks from the explorer.

        Args:
            limit: Number of blocks to return.

        Returns:
            List of block dicts.
        """
        result = await self._get("/explorer/blocks", params={"limit": limit})
        if isinstance(result, list):
            return result
        return result.get("blocks", [])

    async def explorer_transactions(
        self,
        address: str = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Get transactions from the explorer.

        Args:
            address: Optional address filter.
            limit: Number of transactions to return.

        Returns:
            List of transaction dicts.
        """
        params = {"limit": limit}
        if address:
            params["address"] = address
        result = await self._get("/explorer/transactions", params=params)
        if isinstance(result, list):
            return result
        return result.get("transactions", [])

    # ─────────────────────────────────────────────────────────────────
    # Epoch & Rewards
    # ─────────────────────────────────────────────────────────────────

    async def get_epoch_rewards(self, epoch_number: int) -> Dict[str, Any]:
        """
        Get reward distribution for a specific epoch.

        Args:
            epoch_number: The epoch number.

        Returns:
            Dict with reward distribution info.
        """
        return await self._get(
            "/epoch/rewards",
            params={"epoch_number": epoch_number},
        )
