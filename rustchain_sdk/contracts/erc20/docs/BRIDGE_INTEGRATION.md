# Bridge Integration Guide

**Bounty #1510 | RIP-305 Track B**

This guide explains how to integrate the wRTC ERC-20 contract with the BoTTube Bridge for cross-chain transfers between RustChain, Solana, and Base.

---

## 🌉 Bridge Architecture

### Overview

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│  RustChain   │◄───────►│  BoTTube     │◄───────►│    Base      │
│    (RTC)     │  Bridge │   Bridge     │  Bridge │   (wRTC)     │
│              │         │  Contracts   │         │              │
└──────────────┘         └──────────────┘         └──────────────┘
                                │
                                ▼
                         ┌──────────────┐
                         │    Solana    │
                         │   (wRTC)     │
                         │              │
                         └──────────────┘
```

### Token Flow

1. **Deposit (RTC → wRTC)**
   - User locks RTC on RustChain
   - Bridge mints equivalent wRTC on Base
   - User receives wRTC tokens

2. **Withdrawal (wRTC → RTC)**
   - User burns wRTC on Base
   - Bridge unlocks equivalent RTC on RustChain
   - User receives RTC tokens

---

## 📦 Integration Components

### 1. wRTC Contract (Base)

The ERC-20 contract deployed on Base with bridge extensions:

```solidity
// Bridge operator functions
function bridgeMint(address to, uint256 amount) external
function bridgeBurn(address from, uint256 amount) external
```

### 2. Bridge Operator

Authorized entity that can mint/burn tokens:

- Must be trusted address (multi-sig recommended)
- Called by bridge contracts
- Monitors for deposits/withdrawals

### 3. Bridge Contracts

Smart contracts that manage cross-chain transfers:

- Lock/unlock on source chain
- Mint/burn on destination chain
- Verify proofs/signatures

---

## 🔧 Integration Steps

### Step 1: Deploy wRTC Contract

```bash
cd contracts/erc20
npm install
npm run deploy:base
```

Save the contract address.

### Step 2: Configure Bridge Operator

```bash
export WRTC_ADDRESS=0xYourContractAddress

# Add bridge operator (the bridge contract address)
node scripts/interact.js add-operator 0xBridgeContractAddress
```

### Step 3: Implement Bridge Logic

#### Example: Deposit Handler (Solidity)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./WRTC.sol";

contract BridgeDepositHandler {
    WRTC public wrtc;
    address public bridgeOperator;
    
    mapping(bytes32 => bool) public processedDeposits;
    
    event DepositProcessed(
        bytes32 indexed depositId,
        address indexed recipient,
        uint256 amount
    );
    
    constructor(address _wrtcAddress, address _bridgeOperator) {
        wrtc = WRTC(_wrtcAddress);
        bridgeOperator = _bridgeOperator;
    }
    
    modifier onlyBridgeOperator() {
        require(msg.sender == bridgeOperator, "Not authorized");
        _;
    }
    
    /**
     * @dev Process deposit from RustChain
     * @param depositId Unique deposit identifier
     * @param recipient Address to receive wRTC
     * @param amount Amount to mint (in atomic units)
     */
    function processDeposit(
        bytes32 depositId,
        address recipient,
        uint256 amount
    ) external onlyBridgeOperator {
        require(!processedDeposits[depositId], "Already processed");
        require(recipient != address(0), "Invalid recipient");
        require(amount > 0, "Invalid amount");
        
        processedDeposits[depositId] = true;
        
        // Mint wRTC to recipient
        wrtc.bridgeMint(recipient, amount);
        
        emit DepositProcessed(depositId, recipient, amount);
    }
}
```

#### Example: Withdrawal Handler (Solidity)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./WRTC.sol";

contract BridgeWithdrawalHandler {
    WRTC public wrtc;
    address public bridgeOperator;
    
    mapping(bytes32 => bool) public processedWithdrawals;
    
    event WithdrawalInitiated(
        bytes32 indexed withdrawalId,
        address indexed sender,
        address destination,
        uint256 amount
    );
    
    constructor(address _wrtcAddress, address _bridgeOperator) {
        wrtc = WRTC(_wrtcAddress);
        bridgeOperator = _bridgeOperator;
    }
    
    modifier onlyBridgeOperator() {
        require(msg.sender == bridgeOperator, "Not authorized");
        _;
    }
    
    /**
     * @dev Initiate withdrawal to RustChain
     * @param withdrawalId Unique withdrawal identifier
     * @param destination Destination address on RustChain
     * @param amount Amount to burn (in atomic units)
     */
    function initiateWithdrawal(
        bytes32 withdrawalId,
        string calldata destination,
        uint256 amount
    ) external onlyBridgeOperator {
        require(!processedWithdrawals[withdrawalId], "Already processed");
        require(bytes(destination).length > 0, "Invalid destination");
        require(amount > 0, "Invalid amount");
        
        processedWithdrawals[withdrawalId] = true;
        
        // Burn wRTC from sender
        wrtc.bridgeBurn(msg.sender, amount);
        
        emit WithdrawalInitiated(withdrawalId, msg.sender, destination, amount);
    }
    
    /**
     * @dev User initiates withdrawal
     * @param destination Destination address on RustChain
     */
    function withdraw(string calldata destination, uint256 amount) external {
        bytes32 withdrawalId = keccak256(
            abi.encodePacked(msg.sender, destination, amount, block.timestamp)
        );
        
        // Transfer tokens from user to bridge
        wrtc.transferFrom(msg.sender, address(this), amount);
        
        // Approve bridge operator to burn
        wrtc.approve(bridgeOperator, amount);
        
        // Bridge operator burns the tokens
        // (This would be done via callback or separate tx)
        
        emit WithdrawalInitiated(withdrawalId, msg.sender, destination, amount);
    }
}
```

### Step 4: Off-chain Relayer

Implement off-chain service to monitor chains:

```javascript
// Example: Deposit Monitor (Node.js)
const { ethers } = require('ethers');

class BridgeRelayer {
  constructor(wrtcAddress, bridgeOperatorKey) {
    this.provider = new ethers.providers.JsonRpcProvider(BASE_RPC_URL);
    this.wallet = new ethers.Wallet(bridgeOperatorKey, this.provider);
    this.wrtc = new ethers.Contract(wrtcAddress, WRTC_ABI, this.wallet);
  }
  
  async monitorDeposits() {
    // Listen for deposit events on RustChain
    // Verify proof/signature
    // Call bridgeMint on Base
  }
  
  async monitorWithdrawals() {
    // Listen for withdrawal events on Base
    // Verify proof/signature
    // Unlock RTC on RustChain
  }
}
```

---

## 📊 Bridge Operations

### Minting (Deposits)

When user deposits RTC on RustChain:

1. Bridge detects deposit event
2. Verifies transaction finality
3. Calls `bridgeMint(recipient, amount)` on Base
4. User receives wRTC tokens

```javascript
// Bridge operator mints wRTC
const tx = await wrtc.connect(bridgeOperator).bridgeMint(
  recipientAddress,
  amount
);
await tx.wait();
```

### Burning (Withdrawals)

When user withdraws to RustChain:

1. User approves bridge to burn wRTC
2. Bridge burns tokens
3. Bridge unlocks RTC on RustChain
4. User receives RTC tokens

```javascript
// User approves bridge
await wrtc.approve(bridgeAddress, amount);

// Bridge burns tokens
const tx = await wrtc.connect(bridgeOperator).bridgeBurn(
  userAddress,
  amount
);
await tx.wait();
```

---

## 🔒 Security Considerations

### Bridge Operator Security

1. **Use Multi-sig**: Gnosis Safe for operator address
2. **Implement Limits**: Daily mint/burn limits
3. **Monitoring**: Real-time alerts for large operations
4. **Timelock**: Delay for critical operations

### Double-Spend Prevention

```solidity
// Track processed transactions
mapping(bytes32 => bool) public processedDeposits;
mapping(bytes32 => bool) public processedWithdrawals;

// Check before processing
require(!processedDeposits[depositId], "Already processed");
processedDeposits[depositId] = true;
```

### Rate Limiting

```solidity
// Daily limits
uint256 public dailyMintLimit = 100000 * 10**6; // 100K wRTC
uint256 public dailyMinted;
uint256 public lastResetDay;

function resetIfNewDay() internal {
    uint256 currentDay = block.timestamp / 1 days;
    if (currentDay > lastResetDay) {
        dailyMinted = 0;
        lastResetDay = currentDay;
    }
}

function mintWithLimit(address to, uint256 amount) external {
    resetIfNewDay();
    require(dailyMinted + amount <= dailyMintLimit, "Exceeds daily limit");
    dailyMinted += amount;
    wrtc.bridgeMint(to, amount);
}
```

---

## 📝 Integration Checklist

### Pre-Integration

- [ ] wRTC contract deployed
- [ ] Contract verified on BaseScan
- [ ] Bridge operator configured
- [ ] Test environment set up

### Testing

- [ ] Test deposits on testnet
- [ ] Test withdrawals on testnet
- [ ] Verify event emission
- [ ] Test edge cases (zero amount, invalid address)
- [ ] Test rate limiting
- [ ] Test access control

### Production

- [ ] Deploy to mainnet
- [ ] Verify all contracts
- [ ] Configure production operators
- [ ] Set up monitoring
- [ ] Document procedures
- [ ] Train operations team

---

## 🧪 Testing Guide

### Local Testing

```bash
# Start local Hardhat node
npx hardhat node

# Deploy contracts
npx hardhat run scripts/deploy.js --network localhost

# Run bridge tests
npx hardhat test test/BridgeIntegration.test.js
```

### Testnet Testing

```bash
# Deploy to Base Sepolia
npm run deploy:base-sepolia

# Test bridge operations
node scripts/test-bridge.js --network baseSepolia
```

---

## 📚 API Reference

### Bridge Events

```solidity
// Deposit processed
event DepositProcessed(
    bytes32 indexed depositId,
    address indexed recipient,
    uint256 amount
);

// Withdrawal initiated
event WithdrawalInitiated(
    bytes32 indexed withdrawalId,
    address indexed sender,
    address destination,
    uint256 amount
);
```

### Bridge Functions

```solidity
// Process deposit (mint wRTC)
function processDeposit(
    bytes32 depositId,
    address recipient,
    uint256 amount
) external;

// Initiate withdrawal (burn wRTC)
function initiateWithdrawal(
    bytes32 withdrawalId,
    string calldata destination,
    uint256 amount
) external;

// Get deposit status
function processedDeposits(bytes32 depositId) 
    external view returns (bool);

// Get withdrawal status
function processedWithdrawals(bytes32 withdrawalId) 
    external view returns (bool);
```

---

## 🔗 Example Integration: Aerodrome DEX

### Add Liquidity

```javascript
// 1. Approve router
await wrtc.approve(routerAddress, amount);

// 2. Add liquidity
await router.addLiquidity(
  wrtcAddress,
  usdcAddress,
  wrtcAmount,
  usdcAmount,
  minWrtcAmount,
  minUsdcAmount,
  recipient,
  deadline
);
```

### Create Pool

```javascript
// 1. Create pool if doesn't exist
await factory.createPair(wrtcAddress, usdcAddress);

// 2. Get pool address
const poolAddress = await factory.getPair(wrtcAddress, usdcAddress);

// 3. Add initial liquidity
await wrtc.approve(poolAddress, initialAmount);
await usdc.approve(poolAddress, initialAmount);
await pool.mint(recipient);
```

---

## 📞 Support

For integration issues:

1. Review test cases for examples
2. Check BaseScan for contract events
3. Contact RustChain bridge team
4. Open GitHub issue

---

**Last Updated**: 2026-03-09  
**Version**: 1.0.0  
**Bounty**: #1510
