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
            if not account_info:
                continue

            data = account_info.get("data", {})
            if not data:
                continue

            # Parse token amount from account data
            # Assuming UI amount is stored or can be derived from mint decimals (6 for wRTC)
            # This uses a simplified approach; real parsing may require ABI or layout knowledge
            amount_str = data.get("parsed", {}).get("info", {}).get("tokenAmount", {}).get("uiAmountString", "0")
            amount = float(amount_str)

            holders.append({
                "address": pubkey,
                "amount": amount
            })
        except (KeyError, ValueError, TypeError) as e:
            # Skip malformed account entries
            continue

    return holders


def main():
    """Main entry point for wRTC holder tracking."""
    # Get inputs from environment
    rpc_url = os.environ.get("INPUT_RPC_URL", "https://api.mainnet-beta.solana.com")
    token_mint_str = os.environ.get("INPUT_TOKEN_MINT", "wRTCrW1X9m96A9JbRUt9LoGNp9Hc9U8XcdFy23s7uJQ")

    if not rpc_url or not token_mint_str:
        print("⚠️ Missing required environment variables: INPUT_RPC_URL or INPUT_TOKEN_MINT")
        return

    try:
        client = SolanaClient(rpc_url)
        token_mint = PublicKey(token_mint_str)
    except Exception as e:
        raise ValueError(f"Invalid RPC URL or token mint address: {e}") from e

    try:
        holders = get_token_holders(client, token_mint)
        # Output as JSON to stdout
        print(json.dumps(holders))
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve or process token holders: {e}") from e