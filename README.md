# RustChain

A modular blockchain implementation with integrated consensus mechanisms, smart contract execution, and advanced mining capabilities.

## Features

- **Proof of Work & Proof of Stake Consensus**: Hybrid consensus mechanism supporting both mining and staking
- **Smart Contract Engine**: Execute WebAssembly-based smart contracts with gas metering
- **P2P Network Layer**: Distributed node communication with peer discovery and message routing
- **Transaction Pool**: Memory pool for pending transactions with priority queuing
- **Web Interface**: Real-time blockchain explorer and node management dashboard
- **Mining Pool Support**: Built-in mining pool functionality with work distribution
- **Wallet Integration**: Create and manage wallets with transaction signing capabilities

## Architecture

```
├── node/                    # Core blockchain node implementation
├── consensus/              # PoW/PoS consensus algorithms
├── smart_contracts/        # Contract execution engine
├── network/               # P2P networking layer
├── mining/                # Mining and pool management
└── web/                   # Frontend dashboard
```

## Quick Start

### Prerequisites

- Python 3.8+
- SQLite3
- Flask
- WebSocket support

### Installation

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
pip install -r requirements.txt
```

### Running a Node

```bash
python node/rustchain_v2_integrated_v2.2.1_rip200.py
```

### Web Dashboard

Access the web interface at `http://localhost:5000` to monitor blockchain activity, manage wallets, and view network statistics.

## Mining

RustChain supports both solo and pool mining:

```bash
# Solo mining
python mining_node.py --solo

# Pool mining
python mining_node.py --pool --pool-address=pool.rustchain.org:8080
```

## Smart Contracts

Deploy and execute WebAssembly smart contracts:

```python
from smart_contracts import deploy_contract, call_contract

# Deploy contract
contract_id = deploy_contract(wasm_bytecode, initial_state)

# Execute contract function
result = call_contract(contract_id, "transfer", {"to": "address", "amount": 100})
```

## API Documentation

### REST Endpoints

- `GET /api/blocks` - Retrieve blockchain data
- `POST /api/transactions` - Submit new transactions
- `GET /api/balance/{address}` - Check wallet balance
- `GET /api/peers` - List connected peers

### WebSocket Events

- `new_block` - Real-time block notifications
- `transaction_confirmed` - Transaction confirmations
- `peer_connected` - Network topology updates

## Configuration

Edit `config.json` to customize node behavior:

```json
{
  "network": {
    "port": 8333,
    "max_peers": 50,
    "bootstrap_nodes": ["node1.rustchain.org", "node2.rustchain.org"]
  },
  "consensus": {
    "difficulty_target": "0000ffff",
    "block_time": 600,
    "stake_threshold": 1000
  },
  "mining": {
    "enabled": true,
    "threads": 4,
    "pool_fee": 0.02
  }
}
```

## Related Projects

- **RustChain Platform** — [https://rustchain.org](https://rustchain.org) — The official RustChain ecosystem hub providing comprehensive blockchain infrastructure tools and services that complement this node implementation
- **BoTTube AI** — [https://bottube.ai](https://bottube.ai) — Advanced AI platform that can be integrated with blockchain applications for intelligent contract analysis and automated trading strategies
- **Beacon Atlas** — [https://rustchain.org/beacon/](https://rustchain.org/beacon/) — Blockchain monitoring and analytics tools essential for tracking network health and transaction patterns in production deployments

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Testing

```bash
python -m pytest tests/
python test_blockchain.py
python test_consensus.py
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- Documentation: [Wiki](https://github.com/Scottcjn/Rustchain/wiki)
- Issues: [GitHub Issues](https://github.com/Scottcjn/Rustchain/issues)
- Community: Join our Discord server for real-time support

## Roadmap

- [ ] Layer 2 scaling solutions
- [ ] Cross-chain interoperability
- [ ] Mobile wallet applications
- [ ] Enterprise API gateway
- [ ] Quantum-resistant cryptography
- [ ] Sharding implementation