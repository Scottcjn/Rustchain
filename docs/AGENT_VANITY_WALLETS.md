# Agent Vanity Wallets

This document describes the first implementation slice for
rustchain-bounties#30: deterministic AI-agent vanity wallet generation and
local registration.

## Scope

The current slice covers the milestone boundary:

- Validate agent vanity names.
- Generate `RTC-<agent-name>-<hash>` wallet IDs from agent identity plus a
  hardware fingerprint.
- Optionally mine the hash portion for a hex prefix or suffix.
- Bind one registered agent to one hardware fingerprint hash in SQLite.
- Store the optional Ed25519 public key that later attestation work can use for
  signed agent proofs.
- Provide a small CLI for generation, registration, and listing.

It does not yet extend `/attest/submit` or implement useful-work proofs. Those
belong to the later bounty milestones.

## Address Scheme

The canonical wallet format is:

```text
RTC-<agent-name>-<10 hex chars>
```

The hash is derived from canonical JSON containing:

- normalized `agent_name`
- `hardware_fingerprint_hash`
- optional `public_key_hex`
- nonce
- scheme tag `rustchain-agent-vanity-v1`

Because the hardware fingerprint hash is part of the seed, the same agent name
on different hardware generates a different wallet.

## CLI Examples

Generate without saving:

```bash
python -m node.agent_vanity_wallets generate claude-code \
  --fingerprint '{"cpu":"IBM POWER8","clock_skew_ppm":18.4}'
```

Register in a local node database:

```bash
python -m node.agent_vanity_wallets --db rustchain_v2.db register claude-code \
  --fingerprint ./fingerprint.json \
  --pubkey 0000000000000000000000000000000000000000000000000000000000000000
```

Mine a short vanity hash prefix:

```bash
python -m node.agent_vanity_wallets generate sophia \
  --fingerprint ./fingerprint.json \
  --hash-prefix 00
```

List registrations:

```bash
python -m node.agent_vanity_wallets --db rustchain_v2.db list
```

## Registration Guarantees

The SQLite table has unique constraints on:

- `agent_name`
- `wallet`
- `hardware_fingerprint_hash`

That enforces the first version of the "one agent per physical machine" rule.
Re-registering the same agent on the same fingerprint is idempotent. Registering
a second agent against the same fingerprint is rejected with
`hardware_already_bound_to_agent`.

## Next Milestone

The next slice should wire this identity into attestation:

1. Add a node route such as `POST /api/agents/vanity/register`.
2. Extend `/attest/submit` with `agent_type`, `agent_version`, and
   `agent_proof`.
3. Verify a signed challenge with the stored Ed25519 public key.
4. Record useful-work proofs such as merged PRs, bounty completions, served API
   calls, or inference-token counters.
