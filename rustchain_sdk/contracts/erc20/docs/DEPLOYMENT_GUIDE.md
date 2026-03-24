# wRTC ERC-20 Deployment Guide - Base Network

**Bounty #1510 | RIP-305 Track B**

This guide walks through the complete deployment process for the RustChain Token (wRTC) ERC-20 contract on Base.

---

## 📋 Pre-Deployment Checklist

### 1. Environment Setup

```bash
# Verify Node.js version (18+)
node --version

# Verify npm version (9+)
npm --version

# Clone and navigate to contract directory
cd contracts/erc20

# Install dependencies
npm install
```

### 2. Wallet Preparation

- [ ] Create dedicated deployment wallet (recommended)
- [ ] Fund with ETH for gas (0.01-0.05 ETH)
- [ ] Export private key securely
- [ ] Test with small transaction first

### 3. API Keys

- [ ] BaseScan API key: https://basescan.org/myapikey
- [ ] (Optional) CoinMarketCap API for gas reporting

### 4. Configuration

Create `.env` file:

```bash
cp .env.example .env
```

Edit `.env` with your values:

```bash
PRIVATE_KEY=0x...
ETHERSCAN_API_KEY=...
```

### 5. Test Deployment

**ALWAYS test on Base Sepolia first:**

```bash
npm run deploy:base-sepolia
```

Verify test deployment works before mainnet.

---

## 🚀 Deployment Process

### Step 1: Compile Contracts

```bash
npm run compile
```

Expected output:
```
Compiled 1 Solidity file successfully
```

### Step 2: Run Tests

```bash
npm test
```

Expected output:
```
✓ All tests passed (XX/XX)
```

### Step 3: Deploy to Testnet

```bash
npm run deploy:base-sepolia
```

Save the contract address from output.

### Step 4: Verify on Testnet

```bash
npm run verify:base-sepolia <CONTRACT_ADDRESS>
```

### Step 5: Test Contract

Use interaction scripts:

```bash
export WRTC_ADDRESS=<YOUR_CONTRACT>
node scripts/interact.js info
node scripts/interact.js balance <YOUR_ADDRESS>
```

### Step 6: Deploy to Mainnet

Once testnet is verified and tested:

```bash
npm run deploy:base
```

### Step 7: Verify on Mainnet

```bash
npm run verify:base <CONTRACT_ADDRESS>
```

### Step 8: Add to BaseScan

Contract should be verified automatically. If not:

1. Go to https://basescan.org/address/<CONTRACT>
2. Click "Contract" tab
3. Click "Verify and Publish"
4. Follow verification wizard

---

## 🔧 Post-Deployment Configuration

### Add Bridge Operators

```bash
# Add bridge operator (owner only)
node scripts/interact.js add-operator 0xBridgeOperatorAddress

# Verify operator was added
node scripts/interact.js info
```

### Set Up Multi-sig (Recommended)

Transfer ownership to Gnosis Safe:

```javascript
// Using ethers.js
const safeAddress = "0xYourSafeAddress";
await wrtc.transferOwnership(safeAddress);
```

### Monitor Contract

Set up alerts for:
- Large mints/burns (>100K wRTC)
- Pause/unpause events
- Bridge operator changes
- Ownership transfers

---

## 📊 Deployment Parameters

### Recommended Settings

| Parameter | Testnet | Mainnet |
|-----------|---------|---------|
| Initial Supply | 1,000,000 | 1,000,000 |
| Bridge Operator | Deployer | Multi-sig |
| Gas Price | Auto | 1 gwei |
| Timeout | 180s | 180s |

### Gas Estimates

| Operation | Gas Used | Cost @ 1 gwei |
|-----------|----------|---------------|
| Deployment | ~1,500,000 | ~0.0015 ETH |
| Transfer | ~65,000 | ~0.000065 ETH |
| Bridge Mint | ~100,000 | ~0.0001 ETH |
| Bridge Burn | ~85,000 | ~0.000085 ETH |

---

## 🔍 Verification Steps

### Automated Verification

```bash
npx hardhat verify \
  --network base \
  <CONTRACT_ADDRESS> \
  1000000000000 \
  0xBridgeOperatorAddress
```

### Manual Verification Details

If automated fails, use these parameters:

- **Contract Address**: Your deployed address
- **Compiler Version**: v0.8.20
- **Optimization**: Enabled (200 runs)
- **License**: MIT
- **Constructor Arguments**:
  ```
  Initial Supply: 1000000000000 (1M * 10^6)
  Bridge Operator: 0x...
  ```

---

## 🧪 Testing Checklist

### Functional Tests

- [ ] Token transfers work
- [ ] Approvals work
- [ ] Burning works
- [ ] Bridge mint/burn works (operator only)
- [ ] Pause/unpause works (owner only)
- [ ] Permit (EIP-2612) works

### Security Tests

- [ ] Non-operators cannot bridge mint/burn
- [ ] Non-owners cannot pause/add operators
- [ ] Transfers blocked when paused
- [ ] Zero address checks work
- [ ] Reentrancy protection works

### Integration Tests

- [ ] Contract visible on BaseScan
- [ ] Wallet can add token
- [ ] DEX can create pool
- [ ] Bridge can operate

---

## 🚨 Emergency Procedures

### Pause Contract

If security issue detected:

```bash
node scripts/interact.js pause
```

Verify paused state:

```bash
node scripts/interact.js info
```

### Unpause Contract

After issue resolved:

```bash
node scripts/interact.js unpause
```

### Revoke Bridge Operator

If operator compromised:

```bash
node scripts/interact.js remove-operator 0xCompromisedAddress
```

---

## 📝 Deployment Log Template

```markdown
## Deployment Information

**Date**: YYYY-MM-DD HH:MM:SS UTC
**Network**: Base Mainnet
**Deployer**: 0x...
**Contract**: 0x...

### Transaction Details

**Deployment Tx**: 0x...
**Block Number**: 12345678
**Gas Used**: 1,500,000
**Gas Price**: 1 gwei
**Total Cost**: 0.0015 ETH

### Configuration

**Initial Supply**: 1,000,000 wRTC
**Bridge Operator**: 0x...
**Decimals**: 6

### Verification

**BaseScan URL**: https://basescan.org/address/0x...
**Verified**: Yes/No
**Verification Tx**: 0x...

### Post-Deployment

**Ownership Transferred**: Yes/No
**New Owner**: 0x... (if applicable)
**Additional Operators**: 0x...

### Notes

[Any additional notes or observations]
```

---

## 🎯 Success Criteria

Deployment is successful when:

- ✅ Contract deployed on Base
- ✅ Contract verified on BaseScan
- ✅ All tests pass
- ✅ Token shows in wallet
- ✅ Transfers work
- ✅ Bridge operations work
- ✅ Emergency pause works
- ✅ Documentation updated

---

## 📞 Support

If issues arise:

1. Check troubleshooting section in README
2. Review test cases for examples
3. Check GitHub issues
4. Contact RustChain core team

---

**Last Updated**: 2026-03-09  
**Version**: 1.0.0  
**Bounty**: #1510
