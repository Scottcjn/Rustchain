"""
GitHub App Authentication Module.

Handles JWT generation for app authentication and installation token exchange.
"""

import time
from datetime import datetime, timedelta
from typing import Optional

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


class GitHubAuth:
    """
    Handles GitHub App authentication including JWT generation
    and installation token exchange.
    """

    def __init__(
        self,
        app_id: int,
        private_key: str,
        client_id: str,
        client_secret: str,
        api_base_url: str = "https://api.github.com",
    ):
        self.app_id = app_id
        self.private_key = private_key
        self.client_id = client_id
        self.client_secret = client_secret
        self.api_base_url = api_base_url.rstrip("/")

        # Token cache
        self._installation_tokens: dict[int, dict] = {}
        self._app_token: Optional[dict] = None

    def _load_private_key(self) -> bytes:
        """Load and serialize the private key."""
        key = self.private_key

        # Handle different key formats
        if "-----BEGIN" not in key:
            # Key might be base64 encoded or plain
            key = f"-----BEGIN RSA PRIVATE KEY-----\n{key}\n-----END RSA PRIVATE KEY-----"

        return key.encode("utf-8")

    def generate_jwt(self, expiration_seconds: int = 600) -> str:
        """
        Generate a JWT for GitHub App authentication.

        Args:
            expiration_seconds: Token validity period (max 600 seconds)

        Returns:
            Signed JWT token
        """
        now = int(time.time())
        expiration = min(expiration_seconds, 600)  # GitHub max is 10 minutes

        payload = {
            "iat": now,  # Issued at time
            "exp": now + expiration,  # Expiration time
            "iss": self.app_id,  # Issuer (App ID)
        }

        private_key = self._load_private_key()

        token = jwt.encode(
            payload,
            private_key,
            algorithm="RS256",
        )

        return token

    async def get_app_token(self) -> str:
        """
        Get a JWT token for app-level authentication.

        Returns:
            JWT token for app authentication
        """
        # Check if we have a valid cached token
        if self._app_token:
            if self._app_token["expires_at"] > datetime.now():
                return self._app_token["token"]

        # Generate new token
        token = self.generate_jwt()
        self._app_token = {
            "token": token,
            "expires_at": datetime.now() + timedelta(seconds=540),  # Buffer
        }

        return token

    async def get_installation_token(
        self, installation_id: int, refresh: bool = False
    ) -> str:
        """
        Get an access token for a specific installation.

        Args:
            installation_id: GitHub installation ID
            refresh: Force refresh of cached token

        Returns:
            Installation access token
        """
        # Check cache
        if not refresh and installation_id in self._installation_tokens:
            cached = self._installation_tokens[installation_id]
            if cached["expires_at"] > datetime.now():
                return cached["token"]

        # Get app JWT
        jwt_token = await self.get_app_token()

        # Exchange for installation token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base_url}/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            response.raise_for_status()
            data = response.json()

        # Cache the token
        expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
        self._installation_tokens[installation_id] = {
            "token": data["token"],
            "expires_at": expires_at,
        }

        return data["token"]

    async def get_auth_headers(
        self, installation_id: Optional[int] = None
    ) -> dict[str, str]:
        """
        Get authorization headers for API requests.

        Args:
            installation_id: Optional installation ID for installation-level auth

        Returns:
            Headers dict with Authorization
        """
        if installation_id:
            token = await self.get_installation_token(installation_id)
        else:
            token = await self.get_app_token()

        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def invalidate_token(self, installation_id: Optional[int] = None) -> None:
        """
        Invalidate cached tokens.

        Args:
            installation_id: Specific installation to invalidate, or None for all
        """
        if installation_id is None:
            self._installation_tokens.clear()
            self._app_token = None
        else:
            self._installation_tokens.pop(installation_id, None)
