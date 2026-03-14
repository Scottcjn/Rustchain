class SpectrumTradingPair:
    def __init__(self, base_token: str, quote_token: str, initial_price: float):
        self.base_token = base_token
        self.quote_token = quote_token
        self.initial_price = initial_price
        self.order_book = []  # A list to hold market orders

    def create_trading_pair(self):
        # Logic for creating the trading pair in the Spectrum market
        print(f'Creating trading pair: {self.base_token}/{self.quote_token} at price {self.initial_price}')

    def add_order(self, order_type: str, price: float, quantity: float):
        # Logic for adding buy or sell orders to the order book
        order = {'type': order_type, 'price': price, 'quantity': quantity}
        self.order_book.append(order)
        print(f'Added {order_type} order: {order}')

    def get_order_book(self):
        return self.order_book

# Example Usage
# trading_pair = SpectrumTradingPair('MyToken', 'ERG', 0.5)
# trading_pair.create_trading_pair()
# trading_pair.add_order('buy', 0.45, 100)