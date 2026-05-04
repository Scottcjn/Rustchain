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
            # Assuming UI amount is stored or can be derived from mint decimals
            # Here we simplify: in practice, decode buffer or use token_program
            amount_str = data.get("parsed", {}).get("info", {}).get("tokenAmount", {}).get("uiAmountString", "0")
            amount = float(amount_str) if amount_str else 0.0

            if amount <= 0:
                continue

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
    rpc_url = os.environ.get("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
    mint_str = os.environ.get("TOKEN_MINT_ADDRESS")

    if not mint_str:
        print("⚠️ TOKEN_MINT_ADDRESS environment variable is required.")
        return

    try:
        mint_pubkey = PublicKey(mint_str)
    except ValueError as e:
        raise ValueError(f"Invalid token mint address: {mint_str}") from e

    client = SolanaClient(rpc_url)

    try:
        holders = get_token_holders(client, mint_pubkey)
        print(json.dumps(holders, indent=2))
    except Exception as e:
        print(f"❌ Failed to fetch holders: {e}")
        raise