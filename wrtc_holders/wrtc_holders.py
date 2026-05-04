// File: wrtc_holders/wrtc_holders.py
# SPDX-License-Identifier: MIT

import solana_client

class SolanaClient:
    def __init__(self, url: str):
        """
        Initialize the Solana client with a URL.

        Args:
            url (str): The URL of the Solana node.
        """
        if not isinstance(url, str) or not url.strip():
            raise ValueError("URL must be a non-empty string")
        self.url = url.strip()

    def get_account_info(self, address: str) -> dict:
        """
        Get the account information for a given address.

        Args:
            address (str): The address of the account.

        Returns:
            dict: The account information, or None on failure.

        Raises:
            ValueError: If address is invalid.
        """
        if not isinstance(address, str) or not address.strip():
            raise ValueError("Address must be a non-empty string")
        try:
            response = self._get_account_info_from_solana_node(address.strip())
            if response is None:
                return None
            return response.json()
        except Exception as e:
            print(f"Error fetching account info: {e}")
            return None

    def _get_account_info_from_solana_node(self, address: str):
        """
        Get the account information from the Solana node.

        Args:
            address (str): The address of the account.

        Returns:
            Response: The HTTP response from the Solana node.
        """
        return solana_client.get_account_info(self.url, address)

class WRTCHolder:
    def __init__(self, address: str, amount: int, decimals: int):
        """
        Initialize a WRTC holder.

        Args:
            address (str): The address of the holder.
            amount (int): The amount of wRTC held.
            decimals (int): The number of decimals for the token.
        """
        if not isinstance(address, str) or not address.strip():
            raise ValueError("Address must be a non-empty string")
        if not isinstance(amount, int) or amount < 0:
            raise ValueError("Amount must be a non-negative integer")
        if not isinstance(decimals, int) or decimals < 0:
            raise ValueError("Decimals must be a non-negative integer")

        self.address = address.strip()
        self.amount = amount
        self.decimals = decimals

    def normalized_balance(self) -> float:
        """
        Get the normalized balance of the holder.

        Returns:
            float: The normalized balance.
        """
        return self.amount / (10 ** self.decimals)

    def meets_threshold(self, threshold: float) -> bool:
        """
        Check if the holder's balance meets or exceeds the threshold.

        Args:
            threshold (float): The threshold to check against.

        Returns:
            bool: True if balance meets or exceeds threshold, False otherwise.

        Raises:
            ValueError: If threshold is negative.
        """
        if not isinstance(threshold, (int, float)) or threshold < 0:
            raise ValueError("Threshold must be a non-negative number")
        return self.normalized_balance() >= threshold