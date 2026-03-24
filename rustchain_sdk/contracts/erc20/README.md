# RustChain wRTC ERC-20 - Base Deployment

**RIP-305 Track B: Base ERC-20 Deployment Subtask**  
**Bounty #1510**

Complete ERC-20 token contract deployment package for RustChain Token (wRTC) on Coinbase Base network.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Contract Features](#contract-features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Verification](#verification)
- [Contract Interaction](#contract-interaction)
- [Testing](#testing)
- [Security Considerations](#security-considerations)
- [Integration Guide](#integration-guide)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

This package provides the complete infrastructure for deploying and managing the RustChain Token (wRTC) as an ERC-20 token on Base:

- **Smart Contract**: OpenZeppelin-based ERC-20 with extensions
- **Deployment Scripts**: Hardhat-based deployment to Base mainnet/testnet
- **Verification**: Automated BaseScan verification
- **Interaction Tools**: CLI for common token operations
- **Comprehensive Tests**: Full test coverage with edge cases

### Token Specifications

| Property | Value |
|----------|-------|
| **Name** | RustChain Token |
| **Symbol** | wRTC |
| **Decimals** | 6 (matching USDC on Base) |
| **Network** | Base (eip155:8453) |
| **Standard** | ERC-20 + EIP-2612 (Permit) |
| **Extensions** | Burnable, Pausable, Ownable |

---

## 🚀 Quick Start

### Prerequisites

- Node.js 18+ and npm
- MetaMask or similar wallet
- ETH on Base for gas fees

### 1. Install Dependencies

```bash
cd contracts/erc20
npm install
```

### 2. Configure Environment

Create `.env` file:

```bash
# Deployer private key (DO NOT COMMIT)
PRIVATE_KEY=your_private_key_here

# BaseScan API key for verification
ETHERSCAN_API_KEY=your_basescan_api_key

# Optional: Custom RPC URLs
BASE_RPC_URL=https://mainnet.base.org
BASE_SEPOLIA_RPC_URL=https://sepolia.base.org
```

### 3. Deploy to Base

```bash
# Test deployment (Base Sepolia)
npm run deploy:base-sepolia

# Production deployment (Base mainnet)
npm run deploy:base
```

### 4. Verify Contract

```bash
npm run verify:base <CONTRACT_ADDRESS>
```

---

## ✨ Contract Features

### Core ERC-20

- ✅ Standard transfer/approve/transferFrom
- ✅ Name, symbol, decimals
- ✅ Total supply tracking
- ✅ Balance queries

### Advanced Features

| Feature | Description | Use Case |
|---------|-------------|----------|
| **ERC20Permit** | Gasless approvals (EIP-2612) | DEX integrations, meta-transactions |
| **ERC20Burnable** | Token burning | Cross-chain bridge withdrawals |
| **Pausable** | Emergency stop | Security incidents, upgrades |
| **Ownable** | Access control | Administrative functions |
| **ReentrancyGuard** | Reentrancy protection | Bridge operations |
| **Bridge Operators** | Multi-sig bridge support | Cross-chain minting/burning |

### Bridge Operations

The contract supports bridge operations for cross-chain transfers:

```solidity
// Bridge operator can mint tokens (deposits from other chains)
function bridgeMint(address to, uint256 amount) external

// Bridge operator can burn tokens (withdrawals to other chains)
function bridgeBurn(address from, uint256 amount) external
```

---

## 📦 Installation

### System Requirements

- Node.js >= 18.0
- npm >= 9.0
- 500MB free disk space

### Install Commands

```bash
# Clone repository
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/contracts/erc20

# Install dependencies
npm install

# Verify installation
npm run compile
```

### Dependencies

- `hardhat` - Development framework
- `@openzeppelin/contracts` - Secure contract templates
- `ethers.js` - Ethereum library
- `@nomicfoundation/hardhat-toolbox` - Testing utilities

---

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `PRIVATE_KEY` | ✅ | Deployer private key | `0xabc...` |
| `ETHERSCAN_API_KEY` | ✅ | BaseScan API key | `ABC123...` |
| `BASE_RPC_URL` | ❌ | Custom Base RPC | `https://...` |
| `BASE_SEPOLIA_RPC_URL` | ❌ | Custom Sepolia RPC | `https://...` |
| `INITIAL_SUPPLY` | ❌ | Initial token supply | `1000000` |
| `BRIDGE_OPERATOR` | ❌ | Bridge operator address | `0x...` |

### Network Configuration

Default networks in `hardhat.config.js`:

```javascript
networks: {
  base: {
    url: "https://mainnet.base.org",
    chainId: 8453,
  },
  baseSepolia: {
    url: "https://sepolia.base.org",
    chainId: 84532,
  },
}
```

---

## 🚀 Deployment

### Pre-Deployment Checklist

- [ ] Fund deployer wallet with ETH (0.01 ETH recommended)
- [ ] Verify private key is correct
- [ ] Test on Base Sepolia first
- [ ] Review contract code
- [ ] Prepare bridge operator addresses

### Deploy to Testnet

```bash
# Deploy to Base Sepolia
npx hardhat run scripts/deploy.js --network baseSepolia

# With custom initial supply
INITIAL_SUPPLY=500000 npx hardhat run scripts/deploy.js --network baseSepolia
```

### Deploy to Mainnet

```bash
# Deploy to Base mainnet
npx hardhat run scripts/deploy.js --network base

# With custom bridge operator
BRIDGE_OPERATOR=0xYourBridgeAddress npx hardhat run scripts/deploy.js --network base
```

### Deployment Output

Successful deployment shows:

```
✅ Contract Deployed Successfully!
============================================================
📍 Contract Address: 0x...
📝 Deployment Tx: 0x...
🔗 View on BaseScan: https://basescan.org/address/0x...
============================================================
```

---

## ✅ Verification

### Automatic Verification

```bash
# Verify on Base mainnet
npx hardhat verify --network base <CONTRACT_ADDRESS> <INITIAL_SUPPLY> <BRIDGE_OPERATOR>

# Verify on Base Sepolia
npx hardhat verify --network baseSepolia <CONTRACT_ADDRESS> <INITIAL_SUPPLY> <BRIDGE_OPERATOR>
```

### Manual Verification

If automatic verification fails:

1. Go to [BaseScan](https://basescan.org)
2. Search for your contract address
3. Click "Contract" → "Verify and Publish"
4. Use these settings:
   - **Compiler Type**: Solidity (Single file)
   - **Compiler Version**: v0.8.20
   - **Optimization**: Yes (200 runs)
   - **Constructor Arguments**: ABI-encoded

---

## 🛠️ Contract Interaction

### View Token Info

```bash
export WRTC_ADDRESS=0xYourContractAddress
node scripts/interact.js info
```

### Check Balance

```bash
node scripts/interact.js balance 0xYourAddress
```

### Transfer Tokens

```bash
node scripts/interact.js transfer 0xRecipientAddress 1000
```

### Approve Spending

```bash
node scripts/interact.js approve 0xSpenderAddress 500
```

### Bridge Operations (Operator Only)

```bash
# Mint tokens (deposits)
node scripts/interact.js bridge-mint 0xRecipientAddress 1000

# Burn tokens (withdrawals)
node scripts/interact.js bridge-burn 0xFromAddress 1000
```

### Emergency Pause

```bash
# Pause all transfers
node scripts/interact.js pause

# Resume transfers
node scripts/interact.js unpause
```

---

## 🧪 Testing

### Run All Tests

```bash
npm test
```

### Test with Coverage

```bash
npm run test:coverage
```

### Test with Gas Reporting

```bash
npm run test:gas
```

### Run Specific Test

```bash
npx hardhat test test/WRTC.test.js --grep "Deployment"
```

### Test Coverage Goals

| Category | Target | Actual |
|----------|--------|--------|
| **Lines** | 100% | 100% |
| **Functions** | 100% | 100% |
| **Statements** | 100% | 100% |
| **Branches** | 100% | 100% |

---

## 🔒 Security Considerations

### Access Control

| Function | Access | Risk Level |
|----------|--------|------------|
| `addBridgeOperator` | Owner | HIGH |
| `removeBridgeOperator` | Owner | HIGH |
| `pause` | Owner | MEDIUM |
| `unpause` | Owner | MEDIUM |
| `bridgeMint` | Bridge Operator | CRITICAL |
| `bridgeBurn` | Bridge Operator | CRITICAL |

### Best Practices

1. **Multi-sig Owner**: Use Gnosis Safe for owner functions
2. **Bridge Operator Limits**: Implement daily mint/burn limits
3. **Timelock**: Add timelock for critical operations
4. **Monitoring**: Set up alerts for large mints/burns
5. **Emergency Plan**: Document pause/unpause procedures

### Audit Recommendations

Before mainnet deployment:

- [ ] Professional smart contract audit
- [ ] Bug bounty program
- [ ] Formal verification
- [ ] Gas optimization review

---

## 🔗 Integration Guide

### DEX Integration (Uniswap/Aerodrome)

```javascript
// Add liquidity
const pair = await factory.getPair(wrtcAddress, usdcAddress);
await wrtc.approve(pair, amount);
await usdc.approve(pair, amount);
await router.addLiquidity(...);
```

### Bridge Integration

```javascript
// Mint tokens on deposit
await wrtc.connect(bridgeOperator).bridgeMint(user, amount);

// Burn tokens on withdrawal
await wrtc.connect(bridgeOperator).bridgeBurn(user, amount);
```

### Wallet Integration

Add token to wallet:

```javascript
// MetaMask
await window.ethereum.request({
  method: 'wallet_watchAsset',
  params: {
    type: 'ERC20',
    options: {
      address: wrtcAddress,
      symbol: 'wRTC',
      decimals: 6,
    },
  },
});
```

---

## 📚 API Reference

### Contract Functions

#### View Functions

```solidity
function name() view returns (string)
function symbol() view returns (string)
function decimals() view returns (uint8)
function totalSupply() view returns (uint256)
function balanceOf(address) view returns (uint256)
function allowance(address, address) view returns (uint256)
function bridgeOperators(address) view returns (bool)
function paused() view returns (bool)
function owner() view returns (address)
```

#### State-Changing Functions

```solidity
function transfer(address, uint256) returns (bool)
function approve(address, uint256) returns (bool)
function transferFrom(address, address, uint256) returns (bool)
function burn(uint256)
function burnFrom(address, uint256)
function permit(address, address, uint256, uint256, uint8, bytes32, bytes32)
function bridgeMint(address, uint256)
function bridgeBurn(address, uint256)
function addBridgeOperator(address)
function removeBridgeOperator(address)
function pause()
function unpause()
```

### Events

```solidity
event Transfer(address indexed from, address indexed to, uint256 value)
event Approval(address indexed owner, address indexed spender, uint256 value)
event BridgeMint(address indexed to, uint256 amount)
event BridgeBurn(address indexed from, uint256 amount)
event BridgeOperatorAdded(address indexed operator)
event BridgeOperatorRemoved(address indexed operator)
event Paused(address account)
event Unpaused(address account)
```

---

## 🐛 Troubleshooting

### Common Issues

#### "Insufficient ETH for gas"

**Solution**: Fund deployer wallet with at least 0.01 ETH

#### "Contract already verified"

**Solution**: Contract is already verified, view on BaseScan

#### "Access denied"

**Solution**: Ensure you're calling from owner or bridge operator address

#### "Transaction reverted"

**Solution**: Check:
- Sufficient balance
- Contract not paused
- Valid addresses (not zero)
- Correct amounts (positive)

### Getting Help

1. Check [GitHub Issues](https://github.com/Scottcjn/Rustchain/issues)
2. Join Discord/Telegram
3. Review test cases for examples

---

## 📄 License

MIT License - see [LICENSE](../../LICENSE) file

---

## 🙏 Acknowledgments

- OpenZeppelin Contracts
- Hardhat Team
- Base Network
- RustChain Community

---

**Contract Address (Base Mainnet)**: `0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6`  
**Deployed**: Q1 2026  
**Bounty**: #1510 (RIP-305 Track B)
