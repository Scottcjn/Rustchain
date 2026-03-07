# RustChain CLI

A Rust-based command-line interface for RustChain blockchain operations.

## Features

- Check node health status
- View current epoch information
- List active miners with statistics
- Check wallet balances
- View node statistics
- Generate RTC wallet addresses
- Validate wallet address format
- Verify wallet address on network

## Installation

```bash
# Clone the repository
git clone https://github.com/sososonia-cyber/Rustchain.git
cd Rustchain/rustchain-cli

# Build
cargo build --release

# Run
./target/release/rustchain <command>
```

## Usage

```bash
# Check node health
rustchain health

# Get epoch information
rustchain epoch

# List active miners (top 10)
rustchain miners

# List specific number of miners
rustchain miners --limit 20

# Check wallet balance
rustchain balance my-wallet

# Get node statistics
rustchain stats

# Generate a new RTC wallet address
rustchain address generate

# Generate with custom prefix and length
rustchain address generate --prefix WALLET --length 24

# Validate wallet address format
rustchain address validate RTC-mywallet123

# Verify address exists on the network
rustchain address verify my-wallet
```

## Address Commands

The `address` subcommand provides wallet address utilities:

- **generate**: Generate a new RTC wallet address with random identifier
- **validate**: Validate the format of an RTC wallet address
- **verify**: Check if an address exists on the RustChain network

### Address Format

RTC wallet addresses follow the format: `PREFIX-identifier`

- Standard prefixes: RTC, WALLET, NODE, MINER
- Identifier: 3-64 alphanumeric characters, can include - and _

Examples:
- `RTC-abc123def456`
- `WALLET-my-wallet`
- `MINER-node-001`

## Bounty

This tool was built for the [RustChain Bounty Program](https://github.com/Scottcjn/rustchain-bounties/issues/674):
- **Bounty ID**: #674
- **Tier**: 1 (Utilities)
- **Features**: CLI wallet, address generator, address validator
- **Reward**: 25-50 RTC

## API Reference

- Health: `GET https://rustchain.org/health`
- Miners: `GET https://rustchain.org/api/miners`
- Epoch: `GET https://rustchain.org/epoch`
- Balance: `GET https://rustchain.org/wallet/balance?miner_id={wallet}`

## License

MIT
