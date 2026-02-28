# RustChain Mining Badge - Implementation Guide

## Overview

Live mining status badges for RustChain, compatible with shields.io and GitHub READMEs.

## API Endpoint

### Get Badge JSON

**Endpoint:** `/api/badge/<wallet_address>`

**Example:**
```bash
curl https://50.28.86.131/api/badge/frozen-factorio-ryan
```

**Response:**
```json
{
  "schemaVersion": 1,
  "label": "RustChain",
  "message": "42.5 RTC | Epoch 73 | Active",
  "color": "brightgreen"
}
```

**Badge Colors:**
- `brightgreen` - Active miner (enrolled in current epoch)
- `orange` - Inactive miner (not enrolled)
- `red` - Error

## Usage

### In README.md

```markdown
![RustChain Mining](https://50.28.86.131/api/badge/YOUR_WALLET_ADDRESS)
```

### With shields.io

```markdown
![RustChain](https://img.shields.io/endpoint?url=https://50.28.86.131/api/badge/YOUR_WALLET_ADDRESS)
```

### HTML/Markdown Preview

The badge shows:
- **Wallet Balance** (RTC)
- **Current Epoch Number**
- **Mining Status** (Active/Inactive)

## Implementation Details

### Backend (rustchain_dashboard.py)

Added new route `/api/badge/<wallet_address>` that:
1. Queries wallet balance from `balances` table
2. Checks enrollment status in `epoch_enroll` table
3. Fetches current epoch from node API
4. Returns shields.io-compatible JSON

### GitHub Action (Future Work)

Create a standalone action repository: `Scottcjn/rustchain-badge-action`

**Directory Structure:**
```
rustchain-badge-action/
├── action.yml
├── index.js
├── package.json
└── README.md
```

**action.yml:**
```yaml
name: 'RustChain Badge'
description: 'Display live RustChain mining status in README'
inputs:
  wallet:
    description: 'Your wallet address'
    required: true
  node-url:
    description: 'RustChain node URL'
    default: 'https://50.28.86.131'
runs:
  using: 'node20'
  main: 'index.js'
```

**index.js:**
```javascript
const core = require('@actions/core');

const wallet = core.getInput('wallet');
const nodeUrl = core.getInput('node-url') || 'https://50.28.86.131';

const badgeUrl = `${nodeUrl}/api/badge/${wallet}`;
core.setOutput('badge-url', badgeUrl);
core.setOutput('badge-markdown', `![RustChain Mining](${badgeUrl})`);
console.log(`RustChain Badge: ${badgeUrl}`);
```

**Usage in workflows:**
```yaml
- name: Update RustChain Badge
  uses: Scottcjn/rustchain-badge-action@v1
  with:
    wallet: ${{ secrets.RUSTCHAIN_WALLET }}
```

## Testing

### Manual Test

```bash
# Test with a known wallet
curl https://50.28.86.131/api/badge/frozen-factorio-ryan

# Expected output:
# {"schemaVersion":1,"label":"RustChain","message":"42.5 RTC | Epoch 73 | Active","color":"brightgreen"}
```

### Badge Preview

Visit: `https://50.28.86.131/api/badge/YOUR_WALLET_ADDRESS`

## Benefits

1. **Backlinks**: Every repo using this badge links to RustChain
2. **Discovery**: GitHub Marketplace listing = organic traffic
3. **Credibility**: shields.io integration = professional appearance
4. **Viral**: Easy to embed in any README

## Next Steps

1. ✅ Badge API endpoint (this PR)
2. ⏳ Create `rustchain-badge-action` repository
3. ⏳ Publish to GitHub Marketplace
4. ⏳ Add verification (wallet ownership proof)

## Bounty Claim

Issue: #256
Reward: 40 RTC
Implemented: Badge API endpoint + GitHub Action reference implementation
