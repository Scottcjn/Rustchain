import solana_client

class SolanaClient:
    def __init__(self, url):
        self.url = url

    def get_account_info(self, address):
        try:
            response = self._get_account_info_from_solana_node(address)
            return response.json()
        except Exception as e:
            print(f"Error fetching account info: {e}")
            return None

    def _get_account_info_from_solana_node(self, address):
        return solana_client.get_account_info(self.url, address)

class WRTCHolder:
    def __init__(self, address, amount, decimals):
        self.address = address
        self.amount = amount
        self.decimals = decimals

    def get_balance(self):
        return int(self.amount) / (10 ** self.decimals)

class WRTC:
    def __init__(self, solana_client):
        self.solana_client = solana_client
        self.supply = 0

    def get_holders(self):
        holders = []
        accounts = self.solana_client.get_account_info("9w2B7q3B8vYfNz3K7j8pM8pR9jQkL5mJ2jH5kP7mN8vT")
        for account in accounts["result"]["value"]["data"]:
            if account["pubkey"] == "3n7RJanhRghRzW2PBg1UbkV9syiod8iUMugTvLzwTRkW":
                holders.append(WRTCHolder(account["pubkey"], account["lamports"], 6))
        return holders

    def get_top_holder(self):
        holders = self.get_holders()
        top_holder = max(holders, key=lambda x: x.get_balance())
        return top_holder

    def get_top_holder_balance(self):
        top_holder = self.get_top_holder()
        return top_holder.get_balance()

    def get_top_holder_percentage(self):
        top_holder = self.get_top_holder()
        return (top_holder.get_balance() / self.supply) * 100