# Wallet User Guide

This guide explains wallet basics, balance checks, and safe transfer practices for RustChain users.

## 1) Wallet basics

RustChain uses two public wallet identifiers:

- **Miner ID** — a human-readable `miner_id` used for mining rewards and balance checks.
- **`RTC...` address** — an Ed25519-backed wallet address that can sign native transfers.

Keep your wallet/miner id consistent across setup, mining, and balance checks.
A miner ID can receive payouts, but `POST /wallet/transfer/signed` requires an
Ed25519-backed `RTC...` wallet with the corresponding private key.

## 2) Check wallet balance

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME" | jq .
```

Expected response shape:

```json
{
  "amount_i64": 0,
  "amount_rtc": 0.0,
  "miner_id": "YOUR_WALLET_NAME"
}
```

## 3) Confirm miner is active

```bash
curl -sk https://rustchain.org/api/miners | jq .
```

If your miner does not appear:

1. Wait a few minutes after startup.
2. Confirm the same wallet/miner id was used when starting miner.
3. Check network reachability to the node.

## 4) Wallet-safe operations checklist

- Verify URLs before signing transactions.
- Never share private keys or seed phrases.
- Keep a small test transfer habit before large moves.
- Save tx IDs and timestamps for audit/recovery.

## 5) Signed transfer endpoint (advanced)

The API supports signed transfers:

- Endpoint: `POST /wallet/transfer/signed`
- Reference examples: `docs/API.md`

Only use this when you fully understand signing and key custody.

## 6) Moving funds from a miner ID into a signed wallet

If you already received RTC at a human-readable miner ID, there is **no documented
automatic self-service migration flow** that converts that miner ID into a signed
wallet. The supported user path today is:

1. Create or restore an Ed25519-backed `RTC...` wallet first.
2. Keep using the original miner ID for mining rewards and balance lookups.
3. For native transfers or the official wRTC bridge, move funds only from a wallet
   that can produce Ed25519 signatures.

Important: the bridge API in `docs/bridge-api.md` is **operator/admin-facing**, not
a public endpoint a miner can call to sweep balances from a readable miner ID.
If you have funds on a legacy miner ID and need them moved into a signed wallet,
collect proof of ownership (miner ID, payout tx, timestamps) and contact the
maintainers for an explicit operator-assisted transfer path before sending funds.

## 6) Common wallet issues

### Balance always zero

- Miner may not have completed a reward cycle yet.
- Queried `miner_id` may not match your running miner wallet.

### API SSL warning

Current docs use `curl -k` for self-signed TLS:

```bash
curl -sk https://rustchain.org/health
```

### Wrong chain/token confusion (RTC vs wRTC)

- RTC: RustChain native token
- wRTC: wrapped Solana representation
- Official wRTC mint:
  `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`

## 7) Quick support data to collect

When reporting wallet issues, include:

1. `miner_id` used
2. command run and output snippet
3. timestamp (UTC)
4. relevant tx hash (if any)
