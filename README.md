# RustChain

A lightweight blockchain implementation built with Python and Flask, featuring peer-to-peer networking, mining rewards, and a web interface for blockchain exploration.

## Features

- **Blockchain Core**: Complete blockchain implementation with proof-of-work consensus
- **Mining System**: CPU mining with configurable difficulty and block rewards
- **P2P Network**: Peer discovery and synchronization across network nodes
- **Web Interface**: Flask-based dashboard for blockchain exploration
- **Transaction Pool**: Mempool management for pending transactions
- **Wallet Integration**: Support for wallet addresses and balance tracking

## Quick Start

### Prerequisites

- Python 3.7+
- SQLite3 (included with Python)
- Flask and requests libraries

### Installation

1. Clone the repository:
```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
```

2. Install dependencies:
```bash
pip install flask requests
```

3. Initialize the blockchain:
```bash
python rustchain.py
```

The web interface will be available at `http://localhost:5000`

## Usage

### Running a Node

Start a blockchain node:
```bash
python node/rustchain_v2_integrated_v2.2.1_rip200.py
```

### Mining

Mining starts automatically when the node launches. Configure mining settings in the node configuration.

### Web Dashboard

Access the web interface to:
- View blockchain statistics
- Browse blocks and transactions
- Monitor mining activity
- Check wallet balances

## Network Configuration

Default network settings:
- Port: 5000 (web interface)
- P2P Port: 8333
- Mining difficulty: Auto-adjusting
- Block reward: 50 RTC

## API Endpoints

- `GET /` - Main dashboard
- `GET /blocks` - List all blocks
- `GET /block/<hash>` - Get specific block
- `GET /transactions` - View transaction pool
- `POST /mine` - Trigger mining

## Development

### File Structure

```
Rustchain/
├── node/                   # Node implementation
├── rustchain.py           # Main blockchain logic
├── requirements.txt       # Dependencies
└── README.md             # This file
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Mining Rewards

- Block reward: 50 RTC per block
- Halving: Every 210,000 blocks
- Target block time: 10 minutes

## License

This project is licensed under the MIT License. See the SPDX-License-Identifier header in source files.

## Support

For issues and questions, please open an issue on GitHub or contact the development team.

## Roadmap

- [ ] Smart contract support
- [ ] Multi-signature transactions
- [ ] Enhanced peer discovery
- [ ] Mobile wallet integration
- [ ] Cross-chain interoperability

---

Built with ❤️ by the RustChain development team
