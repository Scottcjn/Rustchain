# RustChain Dashboard — VS Code Extension

Wallet balance, miner status, and bounty board for RustChain, right in your editor.

## Features

- **💰 Wallet Balance** — RTC balance in sidebar and status bar
- **⛏️ Miner Status** — Active miner list with hardware info
- **🏆 Bounty Browser** — Browse open bounties from rustchain-bounties
- **⚡ Epoch Timer** — Current epoch info
- **🔧 Quick Actions** — Open/claim bounties with one click

## Setup

1. Install the extension
2. Open Settings → search "RustChain"
3. Set your wallet address: `rustchain.walletAddress`
4. The sidebar shows your balance automatically

## Commands

| Command | Description |
|---------|-------------|
| `RustChain: Check Balance` | Refresh wallet balance |
| `RustChain: Refresh Miner Status` | Update miner list |
| `RustChain: Refresh Bounties` | Fetch latest bounties |
| `RustChain: Open Bounty` | Open selected bounty in browser |
| `RustChain: Claim Bounty` | Open bounty issues list |

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `rustchain.walletAddress` | `""` | Your RTC wallet address |
| `rustchain.rpcUrl` | `https://rpc.rustchain.org` | RPC endpoint |
| `rustchain.refreshInterval` | `60` | Auto-refresh interval (seconds) |

## Requirements

- VS Code 1.85+
- Internet connection for API calls

## License

MIT
