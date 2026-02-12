# Wallet User Guide

This guide explains wallet basics, balance checks, and safe transfer practices for RustChain users.

## 1) Wallet basics

- In RustChain docs, wallet identity is often represented by `miner_id`.
- Keep your wallet/miner id consistent across setup, mining, and balance checks.

## 2) Check wallet balance

```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME" | jq .
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
curl -sk https://50.28.86.131/api/miners | jq .
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

## 6) Common wallet issues

### Balance always zero

- Miner may not have completed a reward cycle yet.
- Queried `miner_id` may not match your running miner wallet.

### API SSL warning

Current docs use `curl -k` for self-signed TLS:

```bash
curl -sk https://50.28.86.131/health
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
