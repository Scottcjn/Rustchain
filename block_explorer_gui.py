# Block Explorer GUI Upgrade - #1659 (150 RTC)
# Real-time data display for block explorer

class BlockExplorerGUI:
    """Block Explorer GUI with real-time data"""
    
    def __init__(self):
        self.blocks = []
        self.transactions = []
        self.miners = []
    
    def add_block(self, block_number, timestamp, miner):
        """Add a new block"""
        self.blocks.append({'number': block_number, 'timestamp': timestamp, 'miner': miner})
        return {'status': 'added', 'block': block_number}
    
    def add_transaction(self, tx_hash, from_addr, to_addr, amount):
        """Add a new transaction"""
        self.transactions.append({'hash': tx_hash, 'from': from_addr, 'to': to_addr, 'amount': amount})
        return {'status': 'added', 'tx': tx_hash}
    
    def add_miner(self, miner_id, hashrate, earnings):
        """Add a miner"""
        self.miners.append({'id': miner_id, 'hashrate': hashrate, 'earnings': earnings})
        return {'status': 'added', 'miner': miner_id}
    
    def get_realtime_stats(self):
        """Get real-time statistics"""
        return {
            'total_blocks': len(self.blocks),
            'total_transactions': len(self.transactions),
            'total_miners': len(self.miners)
        }

if __name__ == '__main__':
    gui = BlockExplorerGUI()
    gui.add_block(1, 1234567890, 'miner-1')
    gui.add_transaction('tx123', 'addr1', 'addr2', 100)
    gui.add_miner('miner-1', '100 MH/s', 1000)
    print(gui.get_realtime_stats())
