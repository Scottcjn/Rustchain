// File: wrtc_holders/wrtc_holders.py
# SPDX-License-Identifier: MIT

import solana_client
from typing import Dict, List, Optional
from solana.publickey import PublicKey
from solana.rpc.api import Client
from solana.rpc.types import TokenAccountOpts

def get_token_holders(client: Client, token_mint: PublicKey) -> List[Dict[str, float]]:
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
    if not isinstance(client, Client):
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
            amount_data = (
                account_info
                .get("data", {})
                .get("parsed", {})
                .get("info", {})
                .get("tokenAmount", {})
            )
            ui_amount = amount_data.get("uiAmount", 0.0)
            holders.append({"address": pubkey, "amount": ui_amount})
        except Exception as e:
            raise RuntimeError(f"Failed to parse token account: {e}") from e

    return holders