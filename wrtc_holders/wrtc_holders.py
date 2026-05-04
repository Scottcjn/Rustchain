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
            amount (int): The amount of WRTC held.
            decimals (int): The number of decimals for the WRTC amount.
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

    def get_balance(self) -> float:
        """
        Get the balance of the holder in human-readable format.

        Returns:
            float: The balance of the holder.

        Raises:
            ZeroDivisionError: If decimals is set to a negative value (prevented by constructor).
        """
        if self.decimals < 0:
            raise ZeroDivisionError("Decimals cannot be negative")
        divisor = 10 ** self.decimals
        return float(self.amount) / divisor

class WRTC:
    """
    Represents the WRTC token and provides utilities for holder management.
    """

    def __init__(self, mint_address: str, decimals: int = 9):
        """
        Initialize WRTC token configuration.

        Args:
            mint_address (str): The token mint address.
            decimals (int): Number of token decimals, default is 9.
        """
        if not isinstance(mint_address, str) or not mint_address.strip():
            raise ValueError("Mint address must be a non-empty string")
        if not isinstance(decimals, int) or decimals < 0:
            raise ValueError("Decimals must be a non-negative integer")

        self.mint_address = mint_address.strip()
        self.decimals = decimals
        self.holders = []

    def add_holder(self, holder: WRTCHolder) -> None:
        """
        Add a holder to the tracking list.

        Args:
            holder (WRTCHolder): The holder to add.

        Raises:
            TypeError: If holder is not an instance of WRTCHolder.
        """
        if not isinstance(holder, WRTCHolder):
            raise TypeError("Holder must be an instance of WRTCHolder")
        self.holders.append(holder)

    def total_supply(self) -> float:
        """
        Calculate the total tracked supply of WRTC.

        Returns:
            float: Total supply across all tracked holders.
        """
        return sum(holder.get_balance() for holder in self.holders)

    def get_top_holders(self, n: int) -> list:
        """
        Get the top N holders by balance.

        Args:
            n (int): Number of top holders to return.

        Returns:
            list[WRTCHolder]: Top N holders sorted by balance descending.
        """
        if not isinstance(n, int) or n < 0:
            raise ValueError("N must be a non-negative integer")
        return sorted(self.holders, key=lambda h: h.get_balance(), reverse=True)[:n]