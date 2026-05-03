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
        self.url = url

    def get_account_info(self, address: str):
        """
        Get the account information for a given address.

        Args:
            address (str): The address of the account.

        Returns:
            dict: The account information.
        """
        try:
            response = self._get_account_info_from_solana_node(address)
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
            dict: The account information.
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
        self.address = address
        self.amount = amount
        self.decimals = decimals

    def get_balance(self) -> float:
        """
        Get the balance of the holder.

        Returns:
            float: The balance of the holder.
        """
        return int(self.amount) / (10 ** self.decimals)

class WRTC:
    def __init__(self, solana_client: SolanaClient):
        """
        Initialize the WRTC class.

        Args:
            solana_client (SolanaClient): The Solana client.
        """
        self.solana_client = solana_client
        self.supply = 0

    def get_holders(self) -> list:
        """
        Get the holders of WRTC.

        Returns:
            list: A list of WRTCHolder objects.
        """
        holders = []
        accounts = self.solana_client.get_account_info("9w2B7q3B8vYfNz3K7j8pM8pR9jQkL5mJ2jH5kP7mN8vT")
        if accounts is not None:
            for account in accounts["result"]["value"]["data"]:
                if account["pubkey"] == "3n7RJanhRghRzW2PBg1UbkV9syiod8iUMugTvLzwTRkW":
                    holders.append(WRTCHolder(account["pubkey"], account["lamports"], 6))
        return holders

    def get_top_holder(self) -> WRTCHolder:
        """
        Get the top holder of WRTC.

        Returns:
            WRTCHolder: The top holder of WRTC.
        """
        holders = self.get_holders()
        if holders:
            return max(holders, key=lambda x: x.get_balance())
        else:
            return None

    def get_top_holder_balance(self) -> float:
        """
        Get the balance of the top holder.

        Returns:
            float: The balance of the top holder.
        """
        top_holder = self.get_top_holder()
        if top_holder is not None:
            return top_holder.get_balance()
        else:
            return 0.0

    def get_top_holder_percentage(self) -> float:
        """
        Get the percentage of WRTC held by the top holder.

        Returns:
            float: The percentage of WRTC held by the top holder.
        """
        top_holder = self.get_top_holder()
        if top_holder is not None and self.supply > 0:
            return (top_holder.get_balance() / self.supply) * 100
        else:
            return 0.0