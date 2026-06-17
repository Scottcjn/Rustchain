# Wallet User Guide

RustChain wallets let you earn, store, and transfer RTC tokens.

## Wallet Types

| Type | Use Case | Setup |
|------|----------|-------|
| **Miner wallet** | Earn mining rewards | Created automatically by `install-miner.sh --wallet NAME` |
| **Desktop GUI wallet** | Manage funds visually | `wallet/rustchain_wallet_secure.py` |
| **CLI wallet** | Scripted operations | `tools/rustchain_wallet_cli.py` |
| **Agent wallet** | AI agent payments | Via Beacon protocol or SDK |

## Create a Wallet

```bash
# Via miner installer (recommended for mining)
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-wallet

# Via CLI
python3 tools/rustchain_wallet_cli.py create --name my-wallet
```

## Check Balance

```bash
curl "https://50.28.86.131/wallet/balance?miner_id=my-wallet"
```

Returns:
```json
{"miner_id": "my-wallet", "amount_rtc": 12.5, "amount_i64": 12500}
```

## Transfer RTC

```bash
python3 tools/rustchain_wallet_cli.py transfer \
  --from my-wallet \
  --to recipient-wallet \
  --amount 5.0 \
  --admin-key YOUR_KEY
```

## Backup

Wallet data is stored in `~/.rustchain/`. Back up this directory:
```bash
tar -czf rustchain-backup.tar.gz ~/.rustchain/
```

## Recovery

To restore on a new machine:
```bash
tar -xzf rustchain-backup.tar.gz -C ~/
```

## Agent Wallets

AI agents use the same wallet system. Integrate via the Python SDK:
```python
from rustchain_sdk import RustChainClient
client = RustChainClient()
balance = client.get_wallet_balance("agent-wallet")
```

For agent-to-agent payments, use the Beacon protocol with Ed25519-signed messages.

## Fees

| Operation | Fee |
|-----------|-----|
| Attestation | Free |
| Transfer | 0.0001 RTC |
| Withdrawal (Ergo) | 0.001 RTC + Ergo tx fee |
