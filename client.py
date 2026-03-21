"""Main async client for the RustChain SDK."""

from __future__ import annotations

from typing import Any

import httpx

from rustchain.explorer import ExplorerClient
from rustchain.exceptions import APIError, NetworkError, RustChainError, WalletError
from rustchain.models import (
    AttestationStatus,
    BalanceResponse,
    EpochInfo,
    HealthResponse,
    Miner,
    MinerListResponse,
    TransferRequest,
    TransferResponse,
)
from rustchain.wallet import validate_address, validate_signature


class RustChainClient:
    """Async client for the RustChain blockchain node API.

    Parameters
    ----------
    base_url : str
        Base URL of the RustChain node (e.g. "http://50.28.86.131:8099").
    timeout : float, optional
        Request timeout in seconds (default 30.0).
    """

    def __init__(
        self,
        base_url: str = "http://50.28.86.131:8099",
        *,
        timeout: float = 30.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._http = httpx.AsyncClient(
            base_url=self._base,
            timeout=httpx.Timeout(timeout),
            headers={
                "User-Agent": f"RustChain-Python-SDK/0.1.0",
                "Accept": "application/json",
            },
        )
        self._explorer = ExplorerClient(self._http, self._base)

    @property
    def explorer(self) -> ExplorerClient:
        """Return an ExplorerClient for browsing blocks and transactions."""
        return self._explorer

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()

    async def __aenter__(self) -> "RustChainClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> HealthResponse:
        """Check the health status of the RustChain node.

        Returns
        -------
        HealthResponse
        """
        try:
            response = await self._http.get("/health", timeout=self._timeout)
            response.raise_for_status()
            return HealthResponse(**response.json())
        except httpx.TimeoutException as e:
            raise NetworkError("Health check timed out") from e
        except httpx.HTTPStatusError as e:
            raise APIError(
                f"Health check failed: {e.response.text}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise NetworkError(f"Health check network error: {e}") from e

    # ------------------------------------------------------------------
    # Epoch
    # ------------------------------------------------------------------

    async def epoch(self) -> EpochInfo:
        """Fetch the current epoch information.

        Returns
        -------
        EpochInfo
        """
        try:
            response = await self._http.get("/epoch", timeout=self._timeout)
            response.raise_for_status()
            return EpochInfo(**response.json())
        except httpx.TimeoutException as e:
            raise NetworkError("Epoch request timed out") from e
        except httpx.HTTPStatusError as e:
            raise APIError(
                f"Epoch request failed: {e.response.text}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise NetworkError(f"Epoch request network error: {e}") from e

    # ------------------------------------------------------------------
    # Miners
    # ------------------------------------------------------------------

    async def miners(
        self,
        *,
        page: int = 1,
        per_page: int = 20,
    ) -> MinerListResponse:
        """List active miners on the network.

        Parameters
        ----------
        page : int
            Page number (1-indexed).
        per_page : int
            Results per page (max 100).

        Returns
        -------
        MinerListResponse
        """
        try:
            response = await self._http.get(
                "/api/miners",
                params={"page": page, "per_page": min(per_page, 100)},
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()

            miners = [Miner(**m) for m in data.get("miners", data)]
            total = data.get("total", len(miners))
            return MinerListResponse(
                miners=miners,
                total=total,
                page=data.get("page", page),
                per_page=data.get("per_page", per_page),
            )
        except httpx.TimeoutException as e:
            raise NetworkError("Miners request timed out") from e
        except httpx.HTTPStatusError as e:
            raise APIError(
                f"Miners request failed: {e.response.text}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise NetworkError(f"Miners request network error: {e}") from e

    # ------------------------------------------------------------------
    # Balance
    # ------------------------------------------------------------------

    async def balance(self, wallet_id: str) -> BalanceResponse:
        """Check the RTC balance for a wallet.

        Parameters
        ----------
        wallet_id : str
            The wallet address to query.

        Returns
        -------
        BalanceResponse
        """
        if not validate_address(wallet_id):
            raise WalletError(f"Invalid wallet address: {wallet_id!r}")

        try:
            response = await self._http.get(
                f"/api/balance/{wallet_id}",
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
            data.setdefault("wallet_id", wallet_id)
            return BalanceResponse(**data)
        except httpx.TimeoutException as e:
            raise NetworkError(f"Balance request timed out for {wallet_id}") from e
        except httpx.HTTPStatusError as e:
            raise APIError(
                f"Balance request failed for {wallet_id}: {e.response.text}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise NetworkError(f"Balance request network error: {e}") from e

    # ------------------------------------------------------------------
    # Transfer
    # ------------------------------------------------------------------

    async def transfer(
        self,
        from_wallet: str,
        to_wallet: str,
        amount: float,
        signature: str | bytes,
        *,
        nonce: int | None = None,
    ) -> TransferResponse:
        """Submit a signed transfer transaction.

        Parameters
        ----------
        from_wallet : str
            Sender wallet address.
        to_wallet : str
            Recipient wallet address.
        amount : float
            Amount of RTC to transfer.
        signature : str | bytes
            Ed25519 signature (base64-encoded string or raw bytes).
        nonce : int, optional
            Transaction nonce for replay protection.

        Returns
        -------
        TransferResponse
        """
        if not validate_address(from_wallet):
            raise WalletError(f"Invalid sender address: {from_wallet!r}")
        if not validate_address(to_wallet):
            raise WalletError(f"Invalid recipient address: {to_wallet!r}")
        if amount <= 0:
            raise WalletError(f"Transfer amount must be positive, got {amount}")

        if isinstance(signature, bytes):
            import base64

            sig_b64 = base64.b64encode(signature).decode("ascii")
        else:
            sig_b64 = signature

        if not validate_signature(sig_b64):
            raise WalletError("Invalid signature format")

        payload: dict[str, Any] = {
            "from_wallet": from_wallet,
            "to_wallet": to_wallet,
            "amount": amount,
            "signature": sig_b64,
        }
        if nonce is not None:
            payload["nonce"] = nonce

        try:
            response = await self._http.post(
                "/api/transfers",
                json=payload,
                timeout=self._timeout,
            )
            response.raise_for_status()
            return TransferResponse(**response.json())
        except httpx.TimeoutException as e:
            raise NetworkError("Transfer request timed out") from e
        except httpx.HTTPStatusError as e:
            raise APIError(
                f"Transfer failed: {e.response.text}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise NetworkError(f"Transfer request network error: {e}") from e

    # ------------------------------------------------------------------
    # Attestation
    # ------------------------------------------------------------------

    async def attestation_status(self, miner_id: str) -> AttestationStatus:
        """Fetch the attestation status of a miner.

        Parameters
        ----------
        miner_id : str
            The miner identifier to query.

        Returns
        -------
        AttestationStatus
        """
        try:
            response = await self._http.get(
                f"/api/miners/{miner_id}/attestation",
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
            data.setdefault("miner_id", miner_id)
            return AttestationStatus(**data)
        except httpx.TimeoutException as e:
            raise NetworkError(
                f"Attestation status request timed out for {miner_id}"
            ) from e
        except httpx.HTTPStatusError as e:
            raise APIError(
                f"Attestation status request failed for {miner_id}: {e.response.text}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise NetworkError(f"Attestation status network error: {e}") from e
