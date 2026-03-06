# RustChain Utility Tools

A collection of utility tools for RustChain blockchain.

## Tools Included

### 1. Epoch Reward Calculator (`rustchain-epoch`)
Calculate mining rewards for RustChain epochs.

```bash
# Calculate reward
rustchain-epoch calculate -b 100 -s 75

# Get epoch info
rustchain-epoch info

# Estimate time to reward
rustchain-epoch estimate -r 10 -h 5 -s 80
```

### 2. RTC Address Generator (`rustchain-address`)
Generate and validate RTC wallet addresses.

```bash
# Generate new address
rustchain-address generate

# Validate address
rustchain-address validate rtc1abc...

# Generate from public key
rustchain-address from-pubkey <hex>
```

### 3. Config Validator (`rustchain-config`)
Parse and validate RustChain node configuration files.

```bash
# Validate config
rustchain-config validate config.yaml

# Generate template
rustchain-config generate -f yaml

# Show default path
rustchain-config default
```

## Installation

```bash
npm install -g rustchain-utils
```

## Supported Config Formats

- YAML (.yaml, .yml)
- JSON (.json)
- TOML (.toml)

## API

### Epoch Calculator
```typescript
import { calculateEpochReward, calculateHardwareBonus } from 'rustchain-utils';

const reward = calculateEpochReward(100, 75, 1.0);
const bonus = calculateHardwareBonus(75); // 2.125x
```

### Address
```typescript
import { generateAddress, validateAddress } from 'rustchain-utils';

const { address, publicKey, privateKey } = generateAddress();
const result = validateAddress('rtc1abc...');
```

### Config
```typescript
import { loadConfig, validateConfig, generateTemplate } from 'rustchain-utils';

const config = loadConfig('./config.yaml');
const result = validateConfig(config);
const template = generateTemplate('yaml');
```

## License

MIT
