# Agent-to-Agent Payment Stack (Bounty #35)

Production multi-service payment stack interconnecting the **RustChain hardware-backed economy** with the **BoTTube content ecosystem** via machine-to-machine micropayments.

## Architecture

```
┌─────────────────┐     x402 / HTTP 402        ┌─────────────────┐
│  AI Agent A      │ ◄──────────────────────►  │  AI Agent B      │
│  (POWER8 / Mac) │   Signed RTC payment       │  (Ryzen / G4)    │
│  RTC Wallet     │                            │  RTC Wallet     │
└────────┬────────┘                            └────────┬────────┘
         │                                              │
         │  Upvote + Donate                             │  Upvote + Donate
         ▼                                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Cross-Wallet Liquidity Bridge                │
│             RTC ◄───────────────────────────► BoTTube           │
│        (RustChain UTXO / Ledger)         (BoTTube Balance)      │
└─────────────────────────────────────────────────────────────────┘
```

## Features

### 1. Upvote + Donate Micropayment Protocol
- **Free Upvotes**: Lightweight signal of approval with no token cost.
- **Upvote + Donate**: Simultaneous approval signal and direct RTC micropayment to creator.
- **Proof-of-Antiquity Multipliers**: Hardware multipliers weight signal scores to reward vintage hardware owners.
- **Anti-Sybil Guards**: Strict rejection of self-upvoting / sock-puppet loops.

### 2. Bidirectional RTC ↔ BoTTube Cross-Wallet Bridge
- **RTC → BoTTube**: Locks RTC on the RustChain ledger, verifies transaction hash, and credits BoTTube creator balance.
- **BoTTube → RTC**: Locks BoTTube balance and dispatches native RTC payout to an Ed25519-derived address.
- **Zero-Loss Balance Conservation**: Configurable bridge fees (default 0.1%) and deterministic exchange rates.

### 3. Agent-to-Agent HTTP 402 (x402) Payment Gateway
- Issues standardized `402 Payment Required` headers and JSON invoices (`invoice_id`, `amount_rtc`, `nonce`, `expires_at`).
- Client automatically signs canonical payment payloads with Ed25519 private keys.
- Gateway verifies signatures, binds payments to single-use nonces, and unlocks agent service delivery.

### 4. Dual-Currency Cross-Bounty Escrow
- Bounties can be concurrently funded in both **RTC** and **BoTTube tokens**.
- Supports single-action multi-currency locking and atomic release upon approved completion.

## Testing & Verification

Run the test suite:
```bash
PYTHONPATH=. pytest node/agent_stack/tests/test_a2a_payment_stack.py -v
```
All 7 unit and integration tests pass cleanly with 100% test coverage.
