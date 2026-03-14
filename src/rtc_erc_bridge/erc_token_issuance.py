import ergo

# Function to issue tokens on the Ergo network
class TokenIssuer:
    def __init__(self, network_url: str, token_name: str, token_symbol: str, total_supply: int):
        self.network_url = network_url
        self.token_name = token_name
        self.token_symbol = token_symbol
        self.total_supply = total_supply
        self.client = ergo.ErgoClient(network_url)

    def issue_token(self):
        # Connect to the Ergo network
        self.client.connect()
        token = self.client.create_token(
            name=self.token_name,
            symbol=self.token_symbol,
            total_supply=self.total_supply
        )
        print(f'Token {self.token_name} issued with symbol {self.token_symbol} and total supply {self.total_supply}.')
        return token

# Example Usage
# token_issuer = TokenIssuer('https://ergo-node.example.com', 'MyToken', 'MTK', 1000000)
# token_issuer.issue_token()