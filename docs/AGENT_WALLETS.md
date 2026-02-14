# AI Agent Vanity Wallets

This document describes the initial implementation for **bounty #30**: AI agent
vanity wallets tied to a hardware fingerprint.

## Overview

RustChain miner ids are strings; this feature mints a deterministic agent wallet
id in the format:

`RTC-<agent-name>-<hash>`

Example:

`RTC-claude-a7f3b2`

The agent wallet id can then be used as a `miner_id` for balances, payouts, and
other user-facing identifiers.

## API

### POST /agent/register

Registers a new agent for a given hardware fingerprint and Ed25519 public key.

Request:

```json
{
  "agent_name": "claude",
  "agent_pubkey_hex": "…64 hex chars…",
  "hardware_fingerprint": { "any": "json" },
  "vanity_nonce": "0"
}
```

Response:

```json
{
  "ok": true,
  "wallet_id": "RTC-claude-a7f3b2",
  "agent_name": "claude",
  "hw_hash": "…16 hex…",
  "agent_pubkey_hex": "…",
  "vanity_nonce": "0",
  "created_at": 1770000000
}
```

Notes:
- `agent_name` must be 3-20 alphanumeric chars.
- `hw_hash` is derived from canonical JSON of `hardware_fingerprint`.
- The node enforces **one agent per hardware** by `hw_hash` uniqueness.

### GET /agent/wallet/<agent_name>

Returns the most recent wallet registration for `agent_name`.

## CLI

`tools/agent_wallet_cli.py` can:
- generate an Ed25519 keypair
- compute `hw_hash` from a fingerprint JSON file
- optionally mine a vanity nonce (brute force suffix prefix)
- register the agent on a node

Example:

```bash
python tools/agent_wallet_cli.py \
  --agent claude \
  --fingerprint fingerprint.json \
  --want a7f \
  --max-tries 500000 \
  --node https://50.28.86.131 \
  --insecure
```

