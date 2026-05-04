// File: wrtc_holders/wrtc_holders.py
#!/usr/bin/env python3
"""
wRTC Holder Tracking

Fetches all wRTC holders for a given token mint address.
"""

import json
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from solana_client import Client
from solana.publickey import PublicKey
from solana.rpc.api import Client as SolanaClient
from solana.rpc.types import TokenAccountOpts


def get_token_holders(client: SolanaClient, token_mint: PublicKey) -> list[dict[str, float]]:
    """
    Fetches all token holders for a given token mint address.

    Args:
        client: Solana RPC client instance
        token_mint: PublicKey of the token mint

    Returns:
        List of dictionaries containing 'address' and 'amount' keys

    Raises:
        ValueError: If client is not connected or token_mint is invalid
        RuntimeError: If the RPC request fails
    """
    if not isinstance(client, SolanaClient):
        raise ValueError("client must be a Solana Client instance")
    if not isinstance(token_mint, PublicKey):
        raise ValueError("token_mint must be a PublicKey instance")

    try:
        response = client.get_token_accounts_by_mint(
            token_mint,
            TokenAccountOpts(mint=token_mint, commitment="finalized")
        )
        value = response.get("value", [])
    except Exception as e:
        raise RuntimeError(f"Failed to fetch token accounts: {e}") from e

    holders = []
    for item in value:
        try:
            pubkey = item.get("pubkey")
            account_info = item.get("account", {})
            if pubkey and account_info:
                holders.append({
                    "address": pubkey,
                    "amount": account_info.get("lamports", 0) / (10 ** 9)
                })
        except Exception as e:
            raise RuntimeError(f"Failed to process token account: {e}") from e

    return holders


def get_wrtc_holders(client: SolanaClient, token_mint: PublicKey) -> list[dict[str, float]]:
    """
    Fetches all wRTC holders for a given token mint address.

    Args:
        client: Solana RPC client instance
        token_mint: PublicKey of the token mint

    Returns:
        List of dictionaries containing 'address' and 'amount' keys

    Raises:
        ValueError: If client is not connected or token_mint is invalid
        RuntimeError: If the RPC request fails
    """
    return get_token_holders(client, token_mint)


def main():
    """Main entry point for wRTC holder tracking."""
    # Get inputs from environment
    client_url = os.environ.get("INPUT_CLIENT_URL", "")
    token_mint = os.environ.get("INPUT_TOKEN_MINT", "")

    if not all([client_url, token_mint]):
        print("⚠️ Missing required environment variables. Skipping wRTC holder tracking.")
        return

    # Create Solana RPC client instance
    client = SolanaClient(url=client_url)

    # Fetch wRTC holders
    holders = get_wrtc_holders(client, token_mint)

    # Print wRTC holders
    for holder in holders:
        print(f"Address: {holder['address']}, Amount: {holder['amount']}")