# RustChain Reward Claims Guide

**RIP-305 Track D: Claim Page + Eligibility Flow**

This guide explains how to claim your RustChain mining rewards using the web-based claims system.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Prerequisites](#prerequisites)
3. [Step-by-Step Claim Process](#step-by-step-claim-process)
4. [Eligibility Requirements](#eligibility-requirements)
5. [Troubleshooting](#troubleshooting)
6. [API Reference](#api-reference)
7. [Security Best Practices](#security-best-practices)

---

## Quick Start

1. Navigate to `/claims` on your RustChain node (Note: web UI not yet deployed — use CLI or API directly)
2. Enter your **Miner ID**
3. Click **Check Eligibility**
4. Select an **Epoch** to claim
5. Confirm your **Wallet Address**
6. Submit your claim
7. Wait for settlement (~30 minutes)

---

## Prerequisites

Before claiming rewards, ensure you have:

- ✅ A **RustChain miner** that has submitted attestations
- ✅ A valid **RTC wallet address** (starts with `RTC`)
- ✅ **Epoch participation** (mined during the epoch you're claiming)
- ✅ **Passed hardware fingerprint** validation
- ✅ **Settled epoch** (epochs settle ~2 epochs after completion)

### Getting a Wallet Address

If you don't have a wallet address:

1. Download the [RustChain Wallet](/wallet) (Note: wallet download page not yet live — use `pip install clawrtc` or build from source)
2. Generate a new address
3. Save your private key securely (never share it!)
4. Copy the public address (starts with `RTC`)

---

## Step-by-Step Claim Process

### Step 1: Identify Your Miner

**Find your Miner ID:**

Your Miner ID is shown in:
- Mining software logs
- Attestation records (`proof_of_antiquity.json`)
- Node dashboard under "Active Miners"

Example Miner ID: `n64-scott-unit1`

**Enter Miner ID:**
1. Go to `/claims` (web UI coming soon — use CLI or API directly)
2. Type or paste your Miner ID into the input field
3. Click **Check Eligibility**

### Step 2: Review Eligibility

The system will display:

- ✅ **Eligibility Status** - Whether you can claim
- 📊 **Device Architecture** - Your hardware type (e.g., `g4`, `n64_mips`)
- 🔢 **Antiquity Multiplier** - Bonus multiplier for vintage hardware
- 💰 **Registered Wallet** - Your current wallet address
- ✓ **Validation Checks** - Attestation, fingerprint, epoch participation

**If eligible:** Proceed to Step 3

**If not eligible:** Review the reason shown and resolve any issues

### Step 3: Select Epoch

**Understanding Epochs:**

- 1 Epoch = 144 blocks = ~24 hours
- Epochs must be **settled** before claiming (takes ~2 epochs)
- You can only claim epochs where you have attestations

**Select an Epoch:**

1. Use the dropdown to choose an epoch
2. View the reward amount for each epoch
3. Only unclaimed epochs are shown

### Step 4: Confirm Wallet Address

**Wallet Address Requirements:**

- Must start with `RTC`
- 43 characters total (RTC prefix + 40 hex characters)
- Alphanumeric only (no special characters)

**Update Wallet Address:**

If you need to change your wallet address:
1. Update your mining software configuration
2. Re-attest with the new wallet address
3. Wait for the attestation to be recorded

### Step 5: Submit Claim

**Before Submitting:**

- ✅ Verify the reward amount is correct
- ✅ Confirm the wallet address is accurate
- ✅ Check the confirmation box

**Submit:**

1. Click **Submit Claim**
2. Wait for signature generation (~5 seconds)
3. Note your **Claim ID** for tracking

### Step 6: Track Settlement

**Claim Status Flow:**

```
pending → verifying → approved → settled
                                    ↓
                              (reward sent)
```

**Status Meanings:**

| Status | Description |
|--------|-------------|
| `pending` | Claim submitted, waiting verification |
| `verifying` | Undergoing fraud/fleet checks |
| `approved` | Verified, queued for settlement |
| `settled` | Reward transferred to your wallet |
| `rejected` | Claim denied (see reason) |
| `failed` | Settlement failed (will retry) |

**Settlement Time:**

- Typical: 15-45 minutes
- Batch processing: Every 30 minutes
- Network congestion may cause delays

---

## Eligibility Requirements

### Required Checks

| Check | Description | How to Fix |
|-------|-------------|------------|
| **Attestation Valid** | Current attestation within 24 hours | Re-run your miner to submit fresh attestation |
| **Epoch Participation** | Attested during the epoch you're claiming | Claim a different epoch where you have attestations |
| **Fingerprint Passed** | Hardware fingerprint validation succeeded | Ensure you're running on real hardware, not a VM |
| **Wallet Registered** | Valid wallet address on file | Update your miner config with a wallet address |
| **No Pending Claim** | No existing unprocessed claim for same epoch | Wait for existing claim to settle |
| **Epoch Settled** | Epoch has completed settlement | Wait 2 epochs (~48 hours) after epoch ends |

### Common Ineligibility Reasons

#### `not_attested`

**Cause:** No valid attestation within the last 24 hours

**Fix:**
1. Check your miner is running
2. Verify network connectivity to the node
3. Check miner logs for errors
4. Re-run attestation manually if needed

#### `no_epoch_participation`

**Cause:** You didn't mine during the epoch you're trying to claim

**Fix:**
1. Select a different epoch from the dropdown
2. Check your mining history to see which epochs you participated in

#### `fingerprint_failed`

**Cause:** Hardware fingerprint validation failed (likely running in VM/emulator)

**Fix:**
1. Run on real physical hardware
2. Ensure entropy sources are available
3. Check that your CPU is supported

#### `wallet_not_registered`

**Cause:** No wallet address associated with your miner

**Fix:**
1. Update your miner configuration with a wallet address
2. Re-submit attestation
3. Wait for attestation to be recorded

#### `pending_claim_exists`

**Cause:** You already have a pending claim for this epoch

**Fix:**
1. Wait for existing claim to settle (~30 minutes)
2. Check claim status in the dashboard
3. Contact support if claim is stuck

#### `epoch_not_settled`

**Cause:** The epoch hasn't completed settlement yet

**Fix:**
1. Wait for the epoch to settle (~2 epochs after it ends)
2. Claim an older epoch instead

---

## Troubleshooting

### Claim Stuck in "pending" Status

**Possible Causes:**
- High claim volume
- Additional verification required
- System processing delay

**Solutions:**
1. Wait up to 1 hour for processing
2. Refresh the status page
3. Contact support if still pending after 2 hours

### Claim Rejected

**Common Reasons:**
- Fingerprint verification failed
- Fleet detection flagged suspicious activity
- Duplicate claim detected

**Solutions:**
1. Review the rejection reason
2. Address the underlying issue
3. Submit a new claim if applicable

### Settlement Failed

**Possible Causes:**
- Insufficient rewards pool balance
- Invalid wallet address
- Network transaction failure

**Solutions:**
1. System will automatically retry (up to 3 times)
2. Verify your wallet address is correct
3. Contact support if failure persists

### Can't Find My Miner ID

**Where to Look:**
1. Mining software logs (first line after startup)
2. `proof_of_antiquity.json` file (`miner_id` field)
3. Node dashboard → Active Miners
4. Attestation transaction history

---

## API Reference

### Check Eligibility

```http
GET /api/claims/eligibility?miner_id=<MINER_ID>&epoch=<EPOCH>
```

**Response:**
```json
{
  "eligible": true,
  "miner_id": "n64-scott-unit1",
  "epoch": 1234,
  "reward_urtc": 1500000,
  "reward_rtc": 0.015,
  "wallet_address": "RTC1abc123...",
  "checks": {
    "attestation_valid": true,
    "epoch_participation": true,
    "fingerprint_passed": true,
    "wallet_registered": true,
    "no_pending_claim": true,
    "epoch_settled": true
  }
}
```

### Submit Claim

```http
POST /api/claims/submit
Content-Type: application/json

{
  "miner_id": "n64-scott-unit1",
  "epoch": 1234,
  "wallet_address": "RTC1abc123...",
  "signature": "<Ed25519 signature>",
  "public_key": "<Ed25519 public key>"
}
```

**Response:**
```json
{
  "success": true,
  "claim_id": "claim_1234_n64-scott-unit1",
  "status": "pending",
  "submitted_at": 1741564800,
  "estimated_settlement": 1741566600,
  "reward_urtc": 1500000,
  "reward_rtc": 0.015
}
```

### Get Claim Status

```http
GET /api/claims/status/<CLAIM_ID>
```

**Response:**
```json
{
  "claim_id": "claim_1234_n64-scott-unit1",
  "miner_id": "n64-scott-unit1",
  "epoch": 1234,
  "status": "settled",
  "submitted_at": 1741564800,
  "settled_at": 1741566525,
  "reward_urtc": 1500000,
  "wallet_address": "RTC1abc123...",
  "transaction_hash": "0xabc123def456..."
}
```

### Get Claim History

```http
GET /api/claims/history?miner_id=<MINER_ID>
```

**Response:**
```json
{
  "miner_id": "n64-scott-unit1",
  "total_claims": 5,
  "total_claimed_urtc": 7500000,
  "total_claimed_rtc": 0.075,
  "claims": [
    {
      "claim_id": "claim_1234_n64-scott-unit1",
      "epoch": 1234,
      "status": "settled",
      "reward_urtc": 1500000,
      "submitted_at": 1741564800,
      "settled_at": 1741566525
    }
  ]
}
```

---

## Security Best Practices

### Protect Your Private Keys

- ⚠️ **Never share your private key** with anyone
- ⚠️ **Never enter your private key** on the claims page
- ✅ Store private keys offline (hardware wallet recommended)
- ✅ Use a dedicated wallet for mining rewards

### Verify URLs

- ✅ Always use HTTPS
- ✅ Verify the domain is correct
- ⚠️ Beware of phishing sites

### Monitor Your Claims

- ✅ Keep a record of your Claim IDs
- ✅ Track settlement status
- ✅ Report any discrepancies immediately

### Rate Limiting

The API enforces rate limits to prevent abuse:

- Eligibility checks: 10/minute per miner
- Claim submissions: 3/minute per miner
- Status checks: 30/minute per IP

---

## Support

If you need help:

1. **Check this guide** - Most issues are covered above
2. **Review error messages** - They often indicate the solution
3. **Contact support** - Open an issue on GitHub with:
   - Your Miner ID
   - Claim ID (if applicable)
   - Screenshots of the error
   - Relevant logs

---

## Technical Details

### How Rewards Are Calculated

Rewards are calculated based on:

1. **Base Reward** - Total epoch rewards / number of miners
2. **Antiquity Multiplier** - Bonus for vintage hardware (1.0x - 3.0x)
3. **Fleet Adjustments** - Penalties for suspicious fleet activity

See [RIP-200](WHITEPAPER.md#3-rip-200-round-robin-consensus) for full details.

### Settlement Process

Claims are settled in batches:

1. **Batch Window** - Every 30 minutes
2. **Minimum Batch** - 10 claims OR 30 minutes elapsed
3. **Maximum Batch** - 100 claims
4. **Transaction** - Multi-output transfer to all claimants

See [RIP-305](../rips/docs/RIP-0305-reward-claim-system.md) for full specification.

---

**Last Updated:** March 9, 2026  
**Version:** 1.0.0  
**Related:** RIP-305 Track D
